"""
Microsoft Graph Metadata Manager

Manages caching and retrieval of MS Graph metadata (users, groups, plans) in Redis
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests
from azure.identity import ClientSecretCredential
from mcp_redis_config import get_redis_token_manager
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis key patterns
REDIS_USER_KEY = "annika:graph:users:{user_id}"
REDIS_GROUP_KEY = "annika:graph:groups:{group_id}"
REDIS_PLAN_KEY = "annika:graph:plans:{plan_id}"
REDIS_TASK_KEY = "annika:graph:tasks:{task_id}"
REDIS_BUCKET_KEY = "annika:graph:buckets:{bucket_id}"
REDIS_METADATA_TTL = 3600  # 1 hour cache

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
        self._init_redis_async()
    
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
        """Get or refresh Microsoft Graph access token"""
        # First try to get delegated token
        from agent_auth_manager import get_agent_token
        token = get_agent_token()
        
        if token:
            return token
        
        # Fall back to app-only token
        if (self.graph_token and self.token_expires and 
                datetime.now() < self.token_expires):
            return self.graph_token
        
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        
        if not all([tenant_id, client_id, client_secret]):
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
        return self.graph_token
    
    async def cache_user_metadata(self, user_id: str) -> Dict[str, Any]:
        """Fetch and cache user metadata from MS Graph"""
        token = self._get_graph_token()
        if not token:
            return {}
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Fetch user details
        url = (f"https://graph.microsoft.com/v1.0/users/{user_id}"
               "?$select=id,displayName,mail,userPrincipalName,"
               "jobTitle,department")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Cache in Redis
            key = REDIS_USER_KEY.format(user_id=user_id)
            await self.redis_client.setex(
                key, 
                REDIS_METADATA_TTL, 
                json.dumps(user_data)
            )
            
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
    
    async def cache_group_metadata(self, group_id: str) -> Dict[str, Any]:
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
        await self.redis_client.setex(
            key,
            REDIS_METADATA_TTL,
            json.dumps(group_data)
        )
        
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
    
    async def cache_plan_metadata(self, plan_id: str) -> Dict[str, Any]:
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
                await self.redis_client.setex(
                    bucket_key,
                    REDIS_METADATA_TTL,
                    json.dumps(bucket)
                )
        
        # Cache in Redis
        key = REDIS_PLAN_KEY.format(plan_id=plan_id)
        await self.redis_client.setex(
            key,
            REDIS_METADATA_TTL,
            json.dumps(plan_data)
        )
        
        return plan_data
    
    async def cache_task_metadata(self, task_id: str) -> Dict[str, Any]:
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
        
        # Cache in Redis
        key = REDIS_TASK_KEY.format(task_id=task_id)
        await self.redis_client.setex(
            key,
            REDIS_METADATA_TTL,
            json.dumps(task_data)
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
    ) -> Optional[Dict[str, Any]]:
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
        data = await self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        
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
    
    def get_sync_client(self):
        """Get synchronous Redis client for non-async contexts"""
        return self.redis_manager._client 