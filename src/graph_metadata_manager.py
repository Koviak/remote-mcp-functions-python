"""
Microsoft Graph Metadata Manager

Manages caching and retrieval of MS Graph metadata in Redis
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import redis.asyncio as redis
import requests
from azure.identity import ClientSecretCredential

from agent_auth_manager import get_agent_token
from dual_auth_manager import get_application_token
from mcp_redis_config import get_redis_token_manager

logger = logging.getLogger(__name__)

# Redis key patterns
REDIS_USER_KEY = "annika:graph:users:{user_id}"
REDIS_USERS_INDEX_KEY = "annika:graph:users:index"
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

REDIS_GROUP_KEY = "annika:graph:groups:{group_id}"
REDIS_GROUPS_INDEX_KEY = "annika:graph:groups:index"
REDIS_PLAN_KEY = "annika:graph:plans:{plan_id}"
REDIS_PLANS_INDEX_KEY = "annika:graph:plans:index"
REDIS_TASK_KEY = "annika:graph:tasks:{task_id}"
REDIS_BUCKET_KEY = "annika:graph:buckets:{bucket_id}"
REDIS_METADATA_TTL = 86400  # 24 hour cache
REDIS_TASK_TTL = None  # Tasks persist indefinitely

# Pub/Sub channels
TASK_UPDATE_CHANNEL = "annika:pubsub:tasks"
METADATA_UPDATE_CHANNEL = "annika:pubsub:metadata"


class GraphMetadataManager:
    """Manages Microsoft Graph metadata in Redis"""

    def __init__(self):
        self.redis_manager = get_redis_token_manager()
        self.redis_client = None
        self.graph_token = None
        self.token_expires = None
        self.last_token_type = "unknown"
        self._init_redis_async()

    @staticmethod
    def _parse_json_result(raw: Any) -> Any:
        """Normalize RedisJSON responses into native Python objects."""
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

    async def _redis_json_get(self, key: str, path: str = "$") -> Any:
        """Retrieve and normalize a RedisJSON value."""
        if not self.redis_client:
            return None
        try:
            raw = await self.redis_client.execute_command("JSON.GET", key, path)
        except Exception as exc:
            logger.debug("RedisJSON GET failed for %s: %s", key, exc)
            return None
        return self._parse_json_result(raw)

    async def _redis_json_set(
        self, key: str, value: Any, path: str = "$", expire: Optional[int] = None
    ) -> None:
        """Store a value using RedisJSON with optional TTL."""
        if not self.redis_client:
            return
        payload = json.dumps(value)
        await self.redis_client.execute_command("JSON.SET", key, path, payload)
        if expire is not None:
            await self.redis_client.expire(key, expire)
    
    @staticmethod
    def _normalize_index_list(payload: Any) -> list[str]:
        """Normalize an index payload into a list of non-empty strings."""
        if payload is None:
            return []
        if isinstance(payload, list):
            if payload and isinstance(payload[0], list):
                payload = payload[0]
            return [
                str(item).strip()
                for item in payload
                if item not in (None, "") and str(item).strip()
            ]
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                return []
            return GraphMetadataManager._normalize_index_list(data)
        return []

    async def _update_index(self, index_key: str, identifier: str) -> None:
        """Ensure the specified metadata index tracks the given identifier."""
        if not identifier:
            return
        if not self.redis_client:
            return

        normalized = str(identifier).strip()
        if not normalized:
            return

        try:
            current = await self._redis_json_get(index_key)
            index = self._normalize_index_list(current)
            if normalized not in index:
                index.append(normalized)
                await self._redis_json_set(
                    index_key,
                    index,
                    expire=REDIS_METADATA_TTL,
                )
                logger.debug(
                    "Added %s to index %s (%s total)", normalized, index_key, len(index)
                )
        except Exception as exc:
            logger.debug(
                "Failed to update index %s for %s: %s", index_key, normalized, exc
            )

    async def _update_plans_index(self, plan_id: str) -> None:
        await self._update_index(REDIS_PLANS_INDEX_KEY, plan_id)

    async def _update_groups_index(self, group_id: str) -> None:
        await self._update_index(REDIS_GROUPS_INDEX_KEY, group_id)

    async def _update_users_index(self, user_id: str) -> None:
        await self._update_index(REDIS_USERS_INDEX_KEY, user_id)

    def _init_redis_async(self):
        """Initialize async Redis client"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_manager.config.host,
                port=self.redis_manager.config.port,
                password=self.redis_manager.config.password,
                decode_responses=True
            )
        except Exception as e:
            logger.error(f"Failed to initialize async Redis: {e}")
    
    def _get_graph_token(self) -> Optional[str]:
        """Get or refresh Microsoft Graph access token. Prefers application auth."""
        # Prefer application token so metadata has tenant-wide visibility
        try:
            token = get_application_token()
            if token:
                if self.last_token_type != "application":
                    logger.debug("Graph metadata using application token")
                self.last_token_type = "application"
                return token
        except Exception as exc:
            logger.warning(f"Failed to acquire application token for metadata: {exc}")

        # Fall back to delegated token (Annika user)
        try:
            token = get_agent_token()
            if token:
                if self.last_token_type != "delegated":
                    logger.debug("Graph metadata using delegated token fallback")
                self.last_token_type = "delegated"
                return token
        except Exception as exc:
            logger.error(f"Failed to acquire delegated token for metadata: {exc}")

        # Final fallback: direct client credential using env vars
        if (self.graph_token and self.token_expires and
                datetime.now() < self.token_expires):
            return self.graph_token

        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")

        if not all([tenant_id, client_id, client_secret]):
            logger.error("Missing Azure AD credentials for metadata Graph call")
            return None

        credential = ClientSecretCredential(
            tenant_id=tenant_id,  # type: ignore
            client_id=client_id,  # type: ignore
            client_secret=client_secret  # type: ignore
        )

        scope = "https://graph.microsoft.com/.default"
        access_token = credential.get_token(scope)
        self.graph_token = access_token.token
        self.token_expires = datetime.now() + timedelta(minutes=50)
        if self.last_token_type != "application":
            logger.debug("Graph metadata using direct application token fallback")
        self.last_token_type = "application"
        return self.graph_token
    
    async def cache_user_metadata(self, user_id: str, token: Optional[str] = None) -> dict[str, Any]:
        """Fetch and cache user metadata from MS Graph"""
        if not token:
            token = self._get_graph_token()
        if not token:
            return {}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch user details
        url = (
            f"https://graph.microsoft.com/v1.0/users/{user_id}"
            "?$select=id,displayName,mail,userPrincipalName,"
            "jobTitle,department,officeLocation,mobilePhone,businessPhones,"
            "aboutMe,givenName,surname"
        )
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Cache in Redis
            key = REDIS_USER_KEY.format(user_id=user_id)
            await self._redis_json_set(
                key,
                user_data,
                expire=REDIS_METADATA_TTL,
            )

            await self._update_users_index(user_id)
            
            # Publish update notification
            await self.redis_client.publish(
                METADATA_UPDATE_CHANNEL,
                json.dumps({
                    "type": "user_updated",
                    "id": user_id,
                    "data": user_data
                })
            )
            
            return user_data
        
        return {}
    
    async def cache_group_metadata(self, group_id: str) -> dict[str, Any]:
        """Fetch and cache group metadata including Planner plans"""
        token = self._get_graph_token()
        if not token:
            return {}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch group details
        url = (f"https://graph.microsoft.com/v1.0/groups/{group_id}"
               "?$select=id,displayName,description,mail,groupTypes")
        group_response = requests.get(url, headers=headers, timeout=10)
        
        if group_response.status_code != 200:
            return {}
        
        group_data = group_response.json()
        
        # Fetch associated Planner plans
        plans_url = (f"https://graph.microsoft.com/v1.0/groups/{group_id}"
                     "/planner/plans")
        plans_response = requests.get(
            plans_url,
            headers=headers,
            timeout=10
        )
        
        if plans_response.status_code == 200:
            group_data["plans"] = plans_response.json().get("value", [])
        
        # Cache in Redis
        key = REDIS_GROUP_KEY.format(group_id=group_id)
        await self._redis_json_set(
            key,
            group_data,
            expire=REDIS_METADATA_TTL,
        )

        await self._update_groups_index(group_id)
        
        # Cache individual plans
        for plan in group_data.get("plans", []):
            await self.cache_plan_metadata(plan["id"])
        
        # Publish notification
        await self.redis_client.publish(
            METADATA_UPDATE_CHANNEL,
            json.dumps({
                "type": "group_updated",
                "id": group_id,
                "data": group_data
            })
        )
        
        return group_data
    
    async def cache_plan_metadata(self, plan_id: str) -> dict[str, Any]:
        """Fetch and cache plan metadata"""
        token = self._get_graph_token()
        if not token:
            return {}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch plan details
        plan_url = f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}"
        plan_response = requests.get(plan_url, headers=headers, timeout=10)
        
        if plan_response.status_code != 200:
            return {}
        
        plan_data = plan_response.json()
        
        # Fetch buckets
        buckets_url = (f"https://graph.microsoft.com/v1.0/planner/plans/"
                       f"{plan_id}/buckets")
        buckets_response = requests.get(
            buckets_url,
            headers=headers,
            timeout=10
        )
        
        if buckets_response.status_code == 200:
            plan_data["buckets"] = buckets_response.json().get("value", [])
            
            # Cache buckets individually
            for bucket in plan_data["buckets"]:
                bucket_key = REDIS_BUCKET_KEY.format(bucket_id=bucket["id"])
                await self._redis_json_set(
                    bucket_key,
                    bucket,
                    expire=REDIS_METADATA_TTL,
                )
        
        # Cache in Redis
        key = REDIS_PLAN_KEY.format(plan_id=plan_id)
        await self._redis_json_set(
            key,
            plan_data,
            expire=REDIS_METADATA_TTL,
        )

        await self._update_plans_index(plan_id)
        
        return plan_data
    
    async def cache_task_metadata(self, task_id: str) -> dict[str, Any]:
        """Fetch and cache task details"""
        token = self._get_graph_token()
        if not token:
            return {}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch task details
        task_url = f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}"
        task_response = requests.get(task_url, headers=headers, timeout=10)
        
        if task_response.status_code != 200:
            return {}
        
        task_data = task_response.json()
        
        # Fetch task details for additional info
        details_url = (f"https://graph.microsoft.com/v1.0/planner/tasks/"
                       f"{task_id}/details")
        details_response = requests.get(
            details_url,
            headers=headers,
            timeout=10
        )
        
        if details_response.status_code == 200:
            task_data["details"] = details_response.json()
        
        # Cache in Redis (no expiry for tasks)
        key = REDIS_TASK_KEY.format(task_id=task_id)
        await self._redis_json_set(
            key,
            task_data,
            expire=REDIS_TASK_TTL,
        )
        
        # Publish update
        await self.redis_client.publish(
            TASK_UPDATE_CHANNEL,
            json.dumps({
                "type": "task_cached",
                "id": task_id,
                "data": task_data
            })
        )
        
        return task_data
    
    async def get_cached_metadata(
            self, resource_type: str, resource_id: str
    ) -> dict[str, Any] | None:
        """Retrieve cached metadata from Redis"""
        key_patterns = {
            "user": REDIS_USER_KEY,
            "group": REDIS_GROUP_KEY,
            "plan": REDIS_PLAN_KEY,
            "task": REDIS_TASK_KEY,
            "bucket": REDIS_BUCKET_KEY
        }
        
        if resource_type not in key_patterns:
            return None
        
        key_format = key_patterns[resource_type]
        key = key_format.format(**{f"{resource_type}_id": resource_id})
        data = await self._redis_json_get(key)

        if data is not None:
            return data
        
        # If not cached, fetch and cache
        if resource_type == "user":
            return await self.cache_user_metadata(resource_id)
        elif resource_type == "group":
            return await self.cache_group_metadata(resource_id)
        elif resource_type == "plan":
            return await self.cache_plan_metadata(resource_id)
        elif resource_type == "task":
            return await self.cache_task_metadata(resource_id)
        
        return None
    
    async def refresh_all_metadata(self):
        """Refresh all cached metadata"""
        logger.info("Starting metadata refresh...")
        
        # Get all cached keys
        patterns = [REDIS_USER_KEY, REDIS_GROUP_KEY, REDIS_PLAN_KEY]
        for pattern in patterns:
            keys = await self.redis_client.keys(pattern.format(**{
                "user_id": "*",
                "group_id": "*", 
                "plan_id": "*"
            }))
            
            for key in keys:
                # Extract ID from key
                parts = key.split(":")
                if len(parts) >= 4:
                    resource_type = parts[2]
                    resource_id = parts[3]
                    
                    if resource_type == "users":
                        await self.cache_user_metadata(resource_id)
                    elif resource_type == "groups":
                        await self.cache_group_metadata(resource_id)
                    elif resource_type == "plans":
                        await self.cache_plan_metadata(resource_id)
        
        logger.info("Metadata refresh completed")
    
    async def cache_all_users(self, page_size: int = 200) -> list[dict[str, Any]]:
        """Retrieve all users from Microsoft Graph and cache them in Redis."""
        token = self._get_graph_token()
        if not token:
            logger.error("Unable to acquire Graph token for cache_all_users")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }
        users: list[dict[str, Any]] = []
        next_url = (
            f"{GRAPH_API_ENDPOINT}/users?"
            "$select=id,displayName,mail,userPrincipalName"
            f"&$top={page_size}"
        )

        index: list[str] = []
        page = 0
        max_pages = 200

        while next_url and page < max_pages:
            page += 1
            response = requests.get(next_url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(
                    "Failed to list users (page %s): %s - %s",
                    page,
                    response.status_code,
                    response.text[:256],
                )
                break

            payload = response.json()
            page_users = payload.get("value", [])
            if not isinstance(page_users, list):
                break

            for user in page_users:
                user_id = user.get("id")
                if not user_id:
                    continue

                index.append(user_id)
                detailed: dict[str, Any] = {}
                try:
                    detailed = await self.cache_user_metadata(user_id, token=token)
                except Exception as exc:  # pragma: no cover - defensive path
                    logger.debug("Failed to hydrate user %s: %s", user_id, exc)

                record = detailed or user
                users.append(record)
                if detailed:
                    continue

                key = REDIS_USER_KEY.format(user_id=user_id)
                try:
                    await self._redis_json_set(
                        key,
                        record,
                        expire=REDIS_METADATA_TTL,
                    )
                except Exception as exc:
                    logger.debug("Failed to cache user %s: %s", user_id, exc)

            next_link = payload.get("@odata.nextLink")
            if next_link and next_link.startswith("/"):
                next_url = f"{GRAPH_API_ENDPOINT}{next_link}"
            else:
                next_url = next_link

        if next_url and page >= max_pages:
            logger.warning("User enumeration truncated after %s pages", page)

        try:
            await self._redis_json_set(
                REDIS_USERS_INDEX_KEY,
                index,
                expire=REDIS_METADATA_TTL,
            )
        except Exception as exc:
            logger.debug("Failed to write users index: %s", exc)

        logger.info("Cached %s users in Redis", len(users))
        return users
    
    async def cache_all_plans(self) -> list[dict[str, Any]]:
        """Retrieve all Planner plans and refresh the Redis cache and index."""
        token = self._get_graph_token()
        if not token:
            logger.error("Unable to acquire Graph token for cache_all_plans")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }

        plans: list[dict[str, Any]] = []
        index: list[str] = []

        next_url = f"{GRAPH_API_ENDPOINT}/groups?$select=id"
        page = 0
        max_pages = 200

        while next_url and page < max_pages:
            page += 1
            try:
                response = requests.get(next_url, headers=headers, timeout=30)
            except Exception as exc:
                logger.error("Failed to enumerate groups (page %s): %s", page, exc)
                break

            if response.status_code != 200:
                logger.error(
                    "Failed to list groups (page %s): %s - %s",
                    page,
                    response.status_code,
                    response.text[:256],
                )
                break

            payload = response.json()
            group_items = payload.get("value", [])
            if not isinstance(group_items, list):
                break

            for group in group_items:
                group_id = group.get("id")
                if not group_id:
                    continue

                plans_url = f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans"
                try:
                    plans_response = requests.get(plans_url, headers=headers, timeout=15)
                except Exception as exc:
                    logger.debug("Failed to fetch plans for group %s: %s", group_id, exc)
                    continue

                if plans_response.status_code != 200:
                    logger.debug(
                        "Planner plans fetch failed for group %s: %s - %s",
                        group_id,
                        plans_response.status_code,
                        plans_response.text[:256],
                    )
                    continue

                group_plans = plans_response.json().get("value", [])
                if not isinstance(group_plans, list):
                    continue

                for plan in group_plans:
                    plan_id = plan.get("id")
                    plan_id_str = str(plan_id).strip() if plan_id else ""
                    if not plan_id_str:
                        continue

                    if plan_id_str not in index:
                        index.append(plan_id_str)

                    detailed: dict[str, Any] | None = None
                    try:
                        detailed = await self.cache_plan_metadata(plan_id_str)
                    except Exception as exc:
                        logger.debug("Failed to cache plan %s: %s", plan_id_str, exc)

                    plans.append(detailed or plan)

            next_link = payload.get("@odata.nextLink")
            if next_link and next_link.startswith("/"):
                next_url = f"{GRAPH_API_ENDPOINT}{next_link}"
            else:
                next_url = next_link

        if next_url and page >= max_pages:
            logger.warning("Group enumeration truncated after %s pages", page)

        if index:
            try:
                await self._redis_json_set(
                    REDIS_PLANS_INDEX_KEY,
                    index,
                    expire=REDIS_METADATA_TTL,
                )
            except Exception as exc:
                logger.debug("Failed to write plans index: %s", exc)

        logger.info("Cached %s plans in Redis", len(plans))
        return plans

    def get_sync_client(self):
        """Get synchronous Redis client for non-async contexts"""
        return self.redis_manager._client
