import asyncio
import json
import logging
import os

import azure.functions as func

from Redis_Master_Manager_Client import set_json, get_redis_client


logger = logging.getLogger(__name__)


def _parse_json_result(raw):
    """Normalize RedisJSON responses into Python primitives."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.debug("Failed to decode RedisJSON payload", exc_info=True)
        return None
    if isinstance(data, list) and len(data) == 1:
        return data[0]
    return data


def _redis_json_set_sync(client, key, value, path="$", expire=None):
    """Store a value in RedisJSON with optional TTL."""
    set_json(client, key, value, path=path, expire_seconds=expire)


def _redis_json_get_sync(client, key, path="$"):
    """Retrieve a RedisJSON value and normalize the response."""
    try:
        raw = client.execute_command("JSON.GET", key, path)
    except Exception as exc:
        logger.debug("RedisJSON GET failed for %s: %s", key, exc)
        return None
    return _parse_json_result(raw)


def hello_http(req: func.HttpRequest) -> func.HttpResponse:
    """Connectivity test endpoint."""
    return func.HttpResponse(
        "Hello I am MCPTool! (HTTP endpoint)", status_code=200, mimetype="text/plain"
    )


def task_events_http(req: func.HttpRequest) -> func.HttpResponse:
    """Receive Task Manager task events and fan out to sync channels.

    Expected payload: { action: "created"|"updated", task_id: str, task: {...} }
    """
    try:
        body = req.get_json()
    except Exception:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    try:
        client = get_redis_client()

        # Record a webhook-like notification so health metrics reflect activity
        log_entry = {
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "change_type": body.get("action", "unknown"),
            "resource": "/annika/task-events",
            "resource_id": body.get("task_id"),
            "client_state": "annika_task_manager",
            "subscription_id": "local-task-events",
        }
        import json as _json
        client.lpush("annika:webhooks:notifications", _json.dumps(log_entry))
        client.expire("annika:webhooks:notifications", 3600)

        # Fan out to task updates channel after logging
        try:
            client.publish("annika:tasks:updates", _json.dumps(body))
        except Exception:
            logger.debug("Publish to annika:tasks:updates failed")

        # Optional fast-path: push to pending ops queue so uploads don't wait on listeners
        task_id = body.get("task_id") or (body.get("task") or {}).get("id")
        if task_id:
            # Mark task record with explicit pending status so upload detector triggers
            try:
                client.execute_command(
                    "JSON.SET",
                    f"annika:tasks:{task_id}",
                    "$.sync_status",
                    '"pending_sync"'
                )
            except Exception:
                logger.debug("Failed to set sync_status pending_sync for %s", task_id)

            # Queue an update operation for immediate processing by sync worker
            try:
                op = {
                    "type": "update",
                    "task_id": task_id,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                    "source": "annika_webhook",
                }
                client.lpush("annika:sync:pending", _json.dumps(op))
            except Exception:
                logger.debug("Fast-path queue push failed; listener path will handle upload")

        return func.HttpResponse("OK", status_code=200)
    except Exception as e:
        logger.error("Task events handler error: %s", e)
        return func.HttpResponse("Internal Server Error", status_code=500)


def graph_webhook_http(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Microsoft Graph webhook notifications."""
    try:
        from logging_setup import setup_logging
        setup_logging(add_console=False)
    except Exception:
        pass

    validation_token = req.params.get('validationToken')
    if validation_token:
        logger.info("Graph webhook validation request received")
        return func.HttpResponse(validation_token, status_code=200, mimetype="text/plain")

    try:
        body = req.get_json()
        notifications = body.get("value", [])
        from webhook_handler import handle_graph_webhook

        # Process notifications within a single short-lived loop to avoid
        # creating/closing a loop per notification which breaks redis.asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for notification in notifications:
                try:
                    success = loop.run_until_complete(handle_graph_webhook(notification))
                    if success:
                        logger.info(
                            f"Successfully processed webhook notification: {notification.get('changeType')} for {notification.get('resource')}"
                        )
                    else:
                        logger.warning(f"Failed to process webhook notification: {notification}")
                except Exception as e:
                    logger.error(f"Error processing individual notification: {e}")

            # Wait for all pending async tasks to complete before closing
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        finally:
            loop.close()

        return func.HttpResponse("OK", status_code=200)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)


def process_graph_notification(notification, redis_manager):
    import json as _json
    from graph_metadata_manager import GraphMetadataManager
    logger = logging.getLogger(__name__)

    resource = notification.get("resource")
    change_type = notification.get("changeType")
    resource_data = notification.get("resourceData", {})
    logger.info(f"Processing {change_type} notification for {resource}")

    redis_client = redis_manager._client
    notification_data = {
        "type": "graph_notification",
        "resource": resource,
        "changeType": change_type,
        "resourceData": resource_data,
        "subscriptionId": notification.get("subscriptionId"),
        "timestamp": notification.get("subscriptionExpirationDateTime"),
    }

    agent_user_id = os.environ.get('AGENT_USER_ID', '')
    if "/me/" in resource or f"/users/{agent_user_id}/" in resource:
        channel = "annika:notifications:user"
    elif "/groups/" in resource:
        channel = "annika:notifications:groups"
    elif "/planner/" in resource:
        channel = "annika:notifications:planner"
    else:
        channel = "annika:notifications:general"

    redis_client.publish(channel, _json.dumps(notification_data))

    manager = GraphMetadataManager()
    if "/users/" in resource:
        user_id = resource.split("/users/")[1].split("/")[0]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.cache_user_metadata(user_id))
        finally:
            loop.close()
    elif "/groups/" in resource:
        group_id = resource.split("/groups/")[1].split("/")[0]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.cache_group_metadata(group_id))
        finally:
            loop.close()

    if "/planner/tasks" in resource and change_type in ["created", "updated"]:
        sync_planner_task(resource, resource_data, redis_manager)
        task_id = resource_data.get("id")
        if task_id:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.cache_task_metadata(task_id))
            finally:
                loop.close()


def sync_planner_task(resource: str, resource_data, redis_manager):
    task_id = resource_data.get("id")
    if not task_id:
        return
    from agent_auth_manager import get_agent_token
    import requests as _requests
    token = get_agent_token()
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        response = _requests.get(
            f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            task = response.json()
            redis_client = redis_manager._client
            _redis_json_set_sync(
                redis_client,
                f"annika:planner:tasks:{task_id}",
                task,
        expire=None,
            )
            redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "updated",
                    "task_id": task_id,
                    "task": task,
                    "source": "webhook",
                }),
            )


