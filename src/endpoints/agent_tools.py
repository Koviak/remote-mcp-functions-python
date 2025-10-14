import json
import logging

import azure.functions as func


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
    """Store a JSON document using RedisJSON and optionally set TTL."""
    payload = json.dumps(value)
    client.execute_command("JSON.SET", key, path, payload)
    if expire is not None:
        client.expire(key, expire)


def _redis_json_get_sync(client, key, path="$"):
    """Read and normalize a RedisJSON value synchronously."""
    try:
        raw = client.execute_command("JSON.GET", key, path)
    except Exception as exc:
        logger.debug("RedisJSON GET failed for %s: %s", key, exc)
        return None
    return _parse_json_result(raw)


def get_metadata_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get cached metadata for users, groups, plans, or tasks from Redis."""
    try:
        resource_type = req.params.get('type')
        resource_id = req.params.get('id')
        if not resource_type or not resource_id:
            return func.HttpResponse("Missing required parameters: type and id", status_code=400)

        from mcp_redis_config import get_redis_token_manager
        redis_manager = get_redis_token_manager()
        redis_client = redis_manager._client

        key_patterns = {
            "user": f"annika:graph:users:{resource_id}",
            "group": f"annika:graph:groups:{resource_id}",
            "plan": f"annika:graph:plans:{resource_id}",
            "task": f"annika:graph:tasks:{resource_id}",
        }
        if resource_type not in key_patterns:
            return func.HttpResponse(f"Invalid resource type: {resource_type}", status_code=400)

        key = key_patterns[resource_type]
        data = _redis_json_get_sync(redis_client, key)
        if data is not None:
            return func.HttpResponse(
                json.dumps(data),
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(
            json.dumps({
                "error": "Resource not found in cache",
                "type": resource_type,
                "id": resource_id,
            }),
            status_code=404,
            mimetype="application/json",
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def create_agent_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a task from an agent and store in Redis; publish a notification."""
    try:
        from datetime import datetime
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        title = req_body.get('title')
        plan_id = req_body.get('planId')
        if not title or not plan_id:
            return func.HttpResponse("Missing required fields: title and planId", status_code=400)

        task = {
            "id": f"agent-task-{datetime.utcnow().timestamp()}",
            "title": title,
            "planId": plan_id,
            "bucketId": req_body.get('bucketId'),
            "assignedTo": req_body.get('assignedTo', []),
            "dueDate": req_body.get('dueDate'),
            "percentComplete": req_body.get('percentComplete', 0),
            "createdBy": "agent",
            "createdAt": datetime.utcnow().isoformat() + "Z",
        }

        from mcp_redis_config import get_redis_token_manager
        redis_manager = get_redis_token_manager()
        redis_client = redis_manager._client
        _redis_json_set_sync(redis_client, f"annika:tasks:{task['id']}", task)
        redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "created",
                "task_id": task.get("id"),
                "task": task,
                "source": "agent",
            }),
        )

        return func.HttpResponse(
            json.dumps({
                "status": "created",
                "task": task,
                "message": "Task will sync to Planner immediately",
            }),
            status_code=201,
            mimetype="application/json",
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


