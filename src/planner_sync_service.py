"""
Enhanced Planner Sync Service

- Immediate upload when agents create/update tasks (event-driven)
- Periodic download of human changes from Planner (polling)
- Agents work exclusively with Redis for speed
"""

import asyncio
import json
import logging
import redis.asyncio as redis
from datetime import datetime
from typing import Dict, Set
from agent_auth_manager import get_agent_token
import requests

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
DOWNLOAD_INTERVAL = 30  # seconds - for polling Planner
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"


class PlannerSyncService:
    """Bidirectional sync between Redis and MS Planner"""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.known_tasks: Set[str] = set()
        self.task_etags: Dict[str, str] = {}
        self.running = False
        
    async def start(self):
        """Start the sync service"""
        logger.info("Starting Enhanced Planner Sync Service...")
        
        # Initialize Redis connection
        self.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Set up pub/sub for instant uploads
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe("annika:tasks:updates")
        
        self.running = True
        
        # Start both tasks concurrently
        await asyncio.gather(
            self._upload_loop(),      # Event-driven uploads
            self._download_loop(),    # Periodic downloads
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop the sync service"""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Sync service stopped")
    
    async def _upload_loop(self):
        """Listen for agent changes and upload immediately"""
        logger.info("Upload loop started - listening for agent changes")
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
                
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    action = data.get('action')
                    source = data.get('source', '')
                    
                    # Only process agent-created events
                    if source in ['agent', 'redis', 'test-agent']:
                        if action == 'created':
                            task = data.get('task')
                            if task:
                                await self._upload_new_task(task)
                        
                        elif action == 'updated':
                            task = data.get('task')
                            if task:
                                await self._upload_task_update(task)
                        
                        elif action == 'deleted':
                            task_id = data.get('taskId')
                            if task_id:
                                await self._delete_task_from_planner(task_id)
                                
                except Exception as e:
                    logger.error(f"Error processing upload event: {e}")
    
    async def _download_loop(self):
        """Periodically download changes from Planner"""
        logger.info("Download loop started - polling Planner for changes")
        
        # Initialize known tasks
        await self._initialize_known_tasks()
        
        while self.running:
            try:
                await self._download_planner_changes()
                await asyncio.sleep(DOWNLOAD_INTERVAL)
            except Exception as e:
                logger.error(f"Error in download loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _upload_new_task(self, task: Dict):
        """Upload a new task to Planner immediately"""
        logger.info(f"Uploading new task to Planner: {task.get('title')}")
        
        token = get_agent_token()
        if not token:
            logger.error("No token available for upload")
            return
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Prepare Planner task data
        planner_task = {
            "planId": task.get("planId"),
            "title": task.get("title"),
            "assignments": {}
        }
        
        if task.get("bucketId"):
            planner_task["bucketId"] = task["bucketId"]
            
        if task.get("dueDate"):
            planner_task["dueDateTime"] = task["dueDate"] + "T00:00:00Z"
            
        if task.get("assignedTo"):
            for user_id in task["assignedTo"]:
                planner_task["assignments"][user_id] = {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !"
                }
        
        try:
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/planner/tasks",
                headers=headers,
                json=planner_task,
                timeout=10
            )
            
            if response.status_code == 201:
                planner_task_data = response.json()
                planner_id = planner_task_data["id"]
                
                # Store mapping
                redis_id = task.get("id")
                if redis_id:
                    await self.redis_client.set(
                        f"annika:task:mapping:{redis_id}",
                        planner_id
                    )
                    await self.redis_client.set(
                        f"annika:task:mapping:{planner_id}",
                        redis_id
                    )
                
                # Update task in Redis with Planner ID
                task["plannerId"] = planner_id
                await self.redis_client.set(
                    f"annika:tasks:{redis_id}",
                    json.dumps(task),
                    ex=86400  # 24 hour expiry
                )
                
                logger.info(f"✅ Task uploaded to Planner: {planner_id}")
                
                # Notify agents of successful sync
                await self.redis_client.publish(
                    "annika:tasks:sync",
                    json.dumps({
                        "action": "uploaded",
                        "redisId": redis_id,
                        "plannerId": planner_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
            else:
                logger.error(
                    f"Failed to create task in Planner: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error uploading task: {e}")
    
    async def _upload_task_update(self, task: Dict):
        """Upload task updates to Planner immediately"""
        redis_id = task.get("id")
        if not redis_id:
            return
            
        # Get Planner ID from mapping
        planner_id = await self.redis_client.get(
            f"annika:task:mapping:{redis_id}"
        )
        
        if not planner_id:
            logger.warning(f"No Planner mapping for task {redis_id}")
            # This might be a new task, try uploading it
            await self._upload_new_task(task)
            return
        
        token = get_agent_token()
        if not token:
            return
            
        try:
            # Get current task from Planner for etag
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get task for update: {planner_id}")
                return
                
            current_task = response.json()
            etag = current_task.get("@odata.etag")
            
            # Prepare update data
            update_data = {}
            
            if "title" in task:
                update_data["title"] = task["title"]
                
            if "percentComplete" in task:
                update_data["percentComplete"] = task["percentComplete"]
                
            if "dueDate" in task:
                update_data["dueDateTime"] = task["dueDate"] + "T00:00:00Z"
            
            # Update Planner
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": etag
            }
            
            response = requests.patch(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers=headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Task updated in Planner: {planner_id}")
            else:
                logger.error(
                    f"Failed to update task: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error updating task: {e}")
    
    async def _delete_task_from_planner(self, task_id: str):
        """Delete a task from Planner"""
        # Check if this is a Redis ID or Planner ID
        planner_id = None
        
        # Try as Redis ID first
        mapping = await self.redis_client.get(
            f"annika:task:mapping:{task_id}"
        )
        if mapping:
            planner_id = mapping
        else:
            # Maybe it's already a Planner ID
            planner_id = task_id
        
        if not planner_id:
            return
            
        token = get_agent_token()
        if not token:
            return
            
        try:
            # Get current task for etag
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                etag = response.json().get("@odata.etag")
                
                # Delete from Planner
                response = requests.delete(
                    f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "If-Match": etag
                    },
                    timeout=10
                )
                
                if response.status_code == 204:
                    logger.info(f"✅ Task deleted from Planner: {planner_id}")
                    
                    # Clean up mappings
                    await self.redis_client.delete(
                        f"annika:task:mapping:{task_id}",
                        f"annika:task:mapping:{planner_id}"
                    )
                    
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
    
    async def _initialize_known_tasks(self):
        """Initialize the set of known tasks from Redis"""
        try:
            # Get all task keys
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match="annika:tasks:*",
                    count=100
                )
                
                for key in keys:
                    task_id = key.split(":")[-1]
                    self.known_tasks.add(task_id)
                    
                if cursor == 0:
                    break
                    
            logger.info(
                f"Initialized with {len(self.known_tasks)} known tasks"
            )
            
        except Exception as e:
            logger.error(f"Error initializing known tasks: {e}")
    
    async def _download_planner_changes(self):
        """Download changes from Planner to Redis"""
        token = get_agent_token()
        if not token:
            return
            
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Get all plans the agent has access to
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/planner/plans",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning("Failed to get plans from Planner")
                return
                
            plans = response.json().get("value", [])
            
            for plan in plans:
                await self._check_plan_for_changes(plan["id"], headers)
                
        except Exception as e:
            logger.error(f"Error downloading from Planner: {e}")
    
    async def _check_plan_for_changes(self, plan_id: str, headers: Dict):
        """Check a specific plan for task changes"""
        try:
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                return
                
            tasks = response.json().get("value", [])
            planner_task_ids = {task["id"] for task in tasks}
            
            # Check for deleted tasks (in our tracking but not in Planner)
            for known_id in list(self.known_tasks):
                # Check if this is a planner ID we're tracking
                mapping = await self.redis_client.get(
                    f"annika:task:mapping:{known_id}"
                )
                if mapping and mapping not in planner_task_ids:
                    # Task was deleted in Planner
                    await self._handle_deleted_from_planner(known_id)
            
            # Process existing and new tasks
            for task in tasks:
                planner_id = task["id"]
                
                # Check if we have a Redis mapping
                redis_id = await self.redis_client.get(
                    f"annika:task:mapping:{planner_id}"
                )
                
                if not redis_id:
                    # This is a new task created by a human
                    await self._download_new_task(task)
                else:
                    # Check if it's been updated
                    current_etag = task.get("@odata.etag", "")
                    if current_etag != self.task_etags.get(planner_id, ""):
                        await self._download_task_update(task, redis_id)
                        
                self.task_etags[planner_id] = task.get("@odata.etag", "")
                
        except Exception as e:
            logger.error(f"Error checking plan {plan_id}: {e}")
    
    async def _handle_deleted_from_planner(self, redis_id: str):
        """Handle a task that was deleted from Planner"""
        logger.info(f"Task deleted from Planner: {redis_id}")
        
        # Remove from Redis
        await self.redis_client.delete(f"annika:tasks:{redis_id}")
        
        # Remove from tracking
        self.known_tasks.discard(redis_id)
        
        # Clean up mappings
        planner_id = await self.redis_client.get(
            f"annika:task:mapping:{redis_id}"
        )
        if planner_id:
            await self.redis_client.delete(
                f"annika:task:mapping:{redis_id}",
                f"annika:task:mapping:{planner_id}"
            )
            self.task_etags.pop(planner_id, None)
        
        # Notify agents
        await self.redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "deleted",
                "taskId": redis_id,
                "source": "planner",
                "timestamp": datetime.utcnow().isoformat()
            })
        )
    
    async def _download_new_task(self, planner_task: Dict):
        """Download a new task from Planner to Redis"""
        logger.info(
            f"New task from Planner: {planner_task.get('title')}"
        )
        
        # Create Redis task
        redis_id = f"planner-{planner_task['id']}"
        redis_task = {
            "id": redis_id,
            "plannerId": planner_task["id"],
            "title": planner_task.get("title", ""),
            "planId": planner_task.get("planId"),
            "bucketId": planner_task.get("bucketId"),
            "percentComplete": planner_task.get("percentComplete", 0),
            "createdBy": "human",
            "createdDateTime": planner_task.get("createdDateTime"),
            "assignedTo": list(planner_task.get("assignments", {}).keys())
        }
        
        # Extract due date if present
        if planner_task.get("dueDateTime"):
            redis_task["dueDate"] = planner_task["dueDateTime"].split("T")[0]
        
        # Store in Redis
        await self.redis_client.set(
            f"annika:tasks:{redis_id}",
            json.dumps(redis_task),
            ex=86400
        )
        
        # Store mapping
        await self.redis_client.set(
            f"annika:task:mapping:{redis_id}",
            planner_task["id"]
        )
        await self.redis_client.set(
            f"annika:task:mapping:{planner_task['id']}",
            redis_id
        )
        
        # Notify agents
        await self.redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "created",
                "task": redis_task,
                "source": "planner",
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        
        self.known_tasks.add(redis_id)
    
    async def _download_task_update(self, planner_task: Dict, redis_id: str):
        """Download task updates from Planner to Redis"""
        logger.info(
            f"Task updated in Planner: {planner_task.get('title')}"
        )
        
        # Get current Redis task
        redis_task_json = await self.redis_client.get(
            f"annika:tasks:{redis_id}"
        )
        
        if redis_task_json:
            redis_task = json.loads(redis_task_json)
            
            # Update fields
            redis_task["title"] = planner_task.get("title", "")
            redis_task["percentComplete"] = planner_task.get(
                "percentComplete", 0
            )
            redis_task["assignedTo"] = list(
                planner_task.get("assignments", {}).keys()
            )
            
            if planner_task.get("dueDateTime"):
                redis_task["dueDate"] = (
                    planner_task["dueDateTime"].split("T")[0]
                )
            
            # Store updated task
            await self.redis_client.set(
                f"annika:tasks:{redis_id}",
                json.dumps(redis_task),
                ex=86400
            )
            
            # Notify agents
            await self.redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "updated",
                    "task": redis_task,
                    "source": "planner",
                    "timestamp": datetime.utcnow().isoformat()
                })
            )


async def main():
    """Run the sync service"""
    service = PlannerSyncService()
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await service.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main()) 