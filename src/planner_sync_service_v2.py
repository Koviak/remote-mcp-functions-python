"""
Enhanced Planner Sync Service V2

Adapted to work with Annika's conscious_state structure.
Uses task operation queue for creating/updating tasks.
"""

import asyncio
import json
import logging
import redis.asyncio as redis
from typing import Dict, Set, Optional
from agent_auth_manager import get_agent_token
from annika_task_adapter import AnnikaTaskAdapter
import requests
import uuid

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
DOWNLOAD_INTERVAL = 30  # seconds - for polling Planner
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# New mapping keys for Annika integration
PLANNER_ID_MAP_PREFIX = "annika:planner:id_map:"


class AnnikaPlannerSync:
    """Bidirectional sync between Annika's conscious_state and MS Planner."""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.adapter = None
        self.known_planner_ids: Set[str] = set()
        self.task_etags: Dict[str, str] = {}
        self.running = False
        
    async def start(self):
        """Start the sync service."""
        logger.info("Starting Annika-Planner Sync Service V2...")
        
        # Initialize Redis connection
        self.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Initialize adapter
        self.adapter = AnnikaTaskAdapter(self.redis_client)
        
        # Set up pub/sub for monitoring changes
        self.pubsub = self.redis_client.pubsub()
        
        # Subscribe to conscious_state changes and task operations
        await self.pubsub.subscribe(
            "__keyspace@0__:annika:conscious_state",
            "__keyspace@0__:annika:task_ops:results:*",
            "annika:tasks:updates"  # Keep for compatibility
        )
        
        self.running = True
        
        # Perform initial sync of all existing tasks
        logger.info("🔄 Performing initial sync of existing tasks...")
        await self._initial_sync()
        
        # Start both sync loops
        await asyncio.gather(
            self._monitor_annika_changes(),
            self._download_from_planner_loop(),
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop the sync service."""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Sync service stopped")
    
    async def _initial_sync(self):
        """Perform initial sync of all existing Annika tasks to Planner."""
        try:
            # Get all tasks from Annika
            annika_tasks = await self.adapter.get_all_annika_tasks()
            logger.info(f"📊 Found {len(annika_tasks)} existing Annika tasks")
            
            # Count tasks by status
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for i, task in enumerate(annika_tasks, 1):
                annika_id = task.get("id")
                if not annika_id:
                    skipped_count += 1
                    continue
                
                # Check if already mapped
                planner_id = await self._get_planner_id(annika_id)
                
                if planner_id:
                    # Task already exists in Planner, update it
                    title = task.get('title', 'Untitled')
                    logger.debug(
                        f"[{i}/{len(annika_tasks)}] Updating: {title}"
                    )
                    await self._update_planner_task(planner_id, task)
                    updated_count += 1
                else:
                    # Create new task in Planner
                    title = task.get('title', 'Untitled')
                    logger.info(
                        f"[{i}/{len(annika_tasks)}] Creating: {title}"
                    )
                    await self._create_planner_task(task)
                    created_count += 1
                
                # Add small delay to avoid rate limiting
                if i % 10 == 0:
                    await asyncio.sleep(1)
            
            logger.info("✅ Initial sync complete!")
            logger.info(f"   - Created: {created_count} new tasks in Planner")
            logger.info(f"   - Updated: {updated_count} existing tasks")
            logger.info(f"   - Skipped: {skipped_count} tasks (no ID)")
            
        except Exception as e:
            logger.error(f"Error during initial sync: {e}")
            logger.info(
                "Initial sync failed, but service will continue "
                "monitoring for changes"
            )
    
    async def _monitor_annika_changes(self):
        """Monitor Annika task changes and sync to Planner."""
        logger.info("Monitoring Annika conscious_state changes...")
        
        # Get initial state
        last_state_hash = await self._get_state_hash()
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
                
            if message['type'] == 'message':
                try:
                    # Check if conscious_state changed
                    if "conscious_state" in message.get('channel', ''):
                        current_hash = await self._get_state_hash()
                        if current_hash != last_state_hash:
                            await self._sync_changes_to_planner()
                            last_state_hash = current_hash
                    
                    # Handle task operation results
                    elif "task_ops:results:" in message.get('channel', ''):
                        # A task operation completed
                        await self._sync_changes_to_planner()
                        
                except Exception as e:
                    logger.error(f"Error monitoring changes: {e}")
    
    async def _get_state_hash(self) -> Optional[str]:
        """Get a hash of the current conscious_state for change detection."""
        try:
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            if state_json:
                # Simple hash - you could use a more sophisticated approach
                return str(hash(state_json))
        except Exception:
            pass
        return None
    
    async def _sync_changes_to_planner(self):
        """Sync all Annika tasks to Planner."""
        logger.info("Syncing Annika changes to Planner...")
        
        try:
            # Get all tasks from Annika structure
            annika_tasks = await self.adapter.get_all_annika_tasks()
            
            # Track which Annika task IDs we've seen
            seen_annika_ids = set()
            
            for task in annika_tasks:
                annika_id = task.get("id")
                if not annika_id:
                    continue
                    
                seen_annika_ids.add(annika_id)
                
                # Get existing Planner ID mapping
                planner_id = await self._get_planner_id(annika_id)
                
                if planner_id:
                    # Update existing task
                    await self._update_planner_task(planner_id, task)
                else:
                    # Create new task in Planner
                    await self._create_planner_task(task)
            
            # TODO: Handle deletions - tasks that were in Planner but
            # are no longer in Annika
            
        except Exception as e:
            logger.error(f"Error syncing to Planner: {e}")
    
    async def _create_planner_task(self, annika_task: Dict):
        """Create a new task in Planner from Annika task."""
        logger.info(f"Creating Planner task: {annika_task.get('title')}")
        
        token = get_agent_token()
        if not token:
            logger.error("No token available")
            return
            
        # Convert to Planner format
        planner_data = self.adapter.annika_to_planner(annika_task)
        
        # Need to set planId - you'll need to configure this
        plan_id = await self._get_default_plan_id()
        if not plan_id:
            logger.error("No default plan ID configured")
            return
            
        planner_data["planId"] = plan_id
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/planner/tasks",
                headers=headers,
                json=planner_data,
                timeout=10
            )
            
            if response.status_code == 201:
                planner_task = response.json()
                planner_id = planner_task["id"]
                annika_id = annika_task.get("id")
                
                # Store ID mapping
                if annika_id:
                    await self._store_id_mapping(annika_id, planner_id)
                
                logger.info(f"✅ Created Planner task: {planner_id}")
                
                # Update Annika task with external_id via task operation
                await self._update_annika_task_external_id(
                    annika_task, planner_id
                )
                
            else:
                logger.error(
                    f"Failed to create Planner task: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error creating Planner task: {e}")
    
    async def _update_planner_task(self, planner_id: str, annika_task: Dict):
        """Update existing Planner task."""
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
            
            if response.status_code != 200:
                logger.error(f"Failed to get task for update: {planner_id}")
                return
                
            current_task = response.json()
            etag = current_task.get("@odata.etag")
            
            # Log which plan this task is in
            current_plan_id = current_task.get("planId")
            if current_plan_id:
                # Get plan details
                plan_response = requests.get(
                    f"{GRAPH_API_ENDPOINT}/planner/plans/{current_plan_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                if plan_response.status_code == 200:
                    plan_data = plan_response.json()
                    plan_title = plan_data.get("title", "Unknown")
                    task_title = annika_task.get('title', 'Untitled')
                    logger.info(
                        f"📍 Task '{task_title}' is in plan: {plan_title}"
                    )
            
            # Convert to Planner format
            update_data = self.adapter.annika_to_planner(annika_task)
            
            # Remove fields that can't be updated
            update_data.pop("planId", None)
            
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
            
            if response.status_code in [200, 204]:
                logger.info(f"✅ Updated Planner task: {planner_id}")
            else:
                logger.error(
                    f"Failed to update task: {response.status_code}"
                )
                
        except Exception as e:
            logger.error(f"Error updating Planner task: {e}")
    
    async def _download_from_planner_loop(self):
        """Periodically download changes from Planner."""
        logger.info("Starting Planner download loop...")
        
        # Wait a bit before first sync
        await asyncio.sleep(5)
        
        while self.running:
            try:
                await self._download_planner_changes()
                await asyncio.sleep(DOWNLOAD_INTERVAL)
            except Exception as e:
                logger.error(f"Error in download loop: {e}")
                await asyncio.sleep(60)
    
    async def _download_planner_changes(self):
        """Download changes from Planner to Annika."""
        token = get_agent_token()
        if not token:
            return
            
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            all_plans = []
            
            # Method 1: Get user's personal plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/planner/plans",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                personal_plans = response.json().get("value", [])
                all_plans.extend(personal_plans)
                logger.info(f"📋 Found {len(personal_plans)} personal plans")
            
            # Method 2: Get group plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/memberOf",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                groups = response.json().get("value", [])
                group_count = 0
                
                for item in groups:
                    if item.get("@odata.type") == "#microsoft.graph.group":
                        group_id = item.get("id")
                        
                        # Get plans for this group
                        url = f"{GRAPH_API_ENDPOINT}/groups/{group_id}"
                        plans_resp = requests.get(
                            f"{url}/planner/plans",
                            headers=headers,
                            timeout=10
                        )
                        
                        if plans_resp.status_code == 200:
                            group_plans = plans_resp.json().get("value", [])
                            if group_plans:
                                all_plans.extend(group_plans)
                                group_count += len(group_plans)
                
                logger.info(f"📋 Found {group_count} group plans")
            
            # Now check all plans for tasks
            total = len(all_plans)
            logger.info(f"📋 Checking {total} total plans for updates...")
            
            for plan in all_plans:
                plan_title = plan.get("title", "Unknown")
                plan_id = plan.get("id")
                id_preview = plan_id[:8] if plan_id else "Unknown"
                logger.info(f"🔍 Checking plan: {plan_title} ({id_preview}...)")
                await self._check_plan_tasks(plan["id"], headers)
                
        except Exception as e:
            logger.error(f"Error downloading from Planner: {e}")
    
    async def _check_plan_tasks(self, plan_id: str, headers: Dict):
        """Check tasks in a specific plan."""
        try:
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                return
                
            tasks = response.json().get("value", [])
            
            if tasks:
                logger.info(f"   Found {len(tasks)} tasks in this plan")
            
            new_tasks = 0
            updated_tasks = 0
            
            for planner_task in tasks:
                planner_id = planner_task["id"]
                task_title = planner_task.get("title", "Untitled")
                
                # Check if we know about this task
                annika_id = await self._get_annika_id(planner_id)
                
                if not annika_id:
                    # New task from Planner
                    logger.info(f"   🆕 New task from Planner: {task_title}")
                    await self._create_annika_task(planner_task)
                    new_tasks += 1
                else:
                    # Check if updated
                    current_etag = planner_task.get("@odata.etag", "")
                    if current_etag != self.task_etags.get(planner_id, ""):
                        msg = f"   🔄 Task updated in Planner: {task_title}"
                        logger.debug(msg)
                        await self._update_annika_task(annika_id, planner_task)
                        updated_tasks += 1
                        
                etag = planner_task.get("@odata.etag", "")
                self.task_etags[planner_id] = etag
            
            if new_tasks > 0 or updated_tasks > 0:
                logger.info(
                    f"   Summary: {new_tasks} new, {updated_tasks} updated"
                )
                
        except Exception as e:
            logger.error(f"Error checking plan tasks: {e}")
    
    async def _create_annika_task(self, planner_task: Dict):
        """Create task in Annika from Planner task."""
        title = planner_task.get('title', 'Untitled')
        logger.info(f"Creating Annika task from Planner: {title}")
        
        # Convert to Annika format
        annika_task = await self.adapter.planner_to_annika(planner_task)
        
        # Determine which list it belongs to
        list_type = self.adapter.determine_task_list(planner_task)
        
        # Create task operation for TaskListManager
        operation = {
            "operation_id": str(uuid.uuid4()),
            "operation_type": "create_task",
            "payload": {
                "list_type": list_type,
                "title": annika_task["title"],
                "description": annika_task.get("description", ""),
                "assigned_to": annika_task.get("assigned_to", "Annika"),
                "percent_complete": annika_task.get("percent_complete", 0),
                "due_date": annika_task.get("due_date"),
                "external_id": planner_task["id"],
                "source": "planner",
                "priority": annika_task.get("priority", "normal"),
                "status": annika_task.get("status", "not_started"),
                "notes": annika_task.get("notes", ""),
                "bucket_id": annika_task.get("bucket_id")
            }
        }
        
        # Send to task operation queue
        await self.redis_client.lpush(
            "annika:task_ops:requests",
            json.dumps(operation)
        )
        
        # Wait for result
        result_key = f"annika:task_ops:results:{operation['operation_id']}"
        
        # Poll for result (with timeout)
        for _ in range(30):  # 3 seconds max
            result = await self.redis_client.get(result_key)
            if result:
                result_data = json.loads(result)
                if result_data.get("success"):
                    created_task = result_data.get("task", {})
                    annika_id = created_task.get("id")
                    if annika_id:
                        # Store mapping
                        planner_id = planner_task["id"]
                        await self._store_id_mapping(annika_id, planner_id)
                        logger.info(f"✅ Created Annika task: {annika_id}")
                break
            await asyncio.sleep(0.1)
    
    async def _update_annika_task(self, annika_id: str, planner_task: Dict):
        """Update Annika task from Planner changes."""
        logger.info(f"Updating Annika task {annika_id} from Planner")
        
        # Convert to Annika format
        annika_updates = await self.adapter.planner_to_annika(planner_task)
        
        # Create update operation
        operation = {
            "operation_id": str(uuid.uuid4()),
            "operation_type": "update_task",
            "payload": {
                "task_id": annika_id,
                "updates": {
                    "title": annika_updates.get("title"),
                    "description": annika_updates.get("description"),
                    "percent_complete": annika_updates.get("percent_complete"),
                    "status": annika_updates.get("status"),
                    "due_date": annika_updates.get("due_date"),
                    "assigned_to": annika_updates.get("assigned_to")
                }
            }
        }
        
        # Send to task operation queue
        await self.redis_client.lpush(
            "annika:task_ops:requests",
            json.dumps(operation)
        )
        
        logger.info(f"Sent update operation for task {annika_id}")
    
    async def _update_annika_task_external_id(
        self, annika_task: Dict, planner_id: str
    ):
        """Update Annika task with Planner ID."""
        annika_id = annika_task.get("id")
        if not annika_id:
            return
            
        # Create update operation
        operation = {
            "operation_id": str(uuid.uuid4()),
            "operation_type": "update_task",
            "payload": {
                "task_id": annika_id,
                "updates": {
                    "external_id": planner_id
                }
            }
        }
        
        await self.redis_client.lpush(
            "annika:task_ops:requests",
            json.dumps(operation)
        )
    
    # ID Mapping helpers
    async def _store_id_mapping(self, annika_id: str, planner_id: str):
        """Store bidirectional ID mapping."""
        await self.redis_client.set(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            planner_id
        )
        await self.redis_client.set(
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}",
            annika_id
        )
    
    async def _get_planner_id(self, annika_id: str) -> Optional[str]:
        """Get Planner ID for Annika task."""
        return await self.redis_client.get(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}"
        )
    
    async def _get_annika_id(self, planner_id: str) -> Optional[str]:
        """Get Annika ID for Planner task."""
        return await self.redis_client.get(
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}"
        )
    
    async def _get_default_plan_id(self) -> Optional[str]:
        """Get default plan ID from configuration."""
        # You can store this in Redis or environment variable
        plan_id = await self.redis_client.get("annika:config:default_plan_id")
        if not plan_id:
            # Try to get from environment
            import os
            plan_id = os.getenv("DEFAULT_PLANNER_PLAN_ID")
        return plan_id


async def main():
    """Run the sync service."""
    sync_service = AnnikaPlannerSync()
    
    try:
        logger.info("Starting Annika-Planner Sync Service...")
        await sync_service.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        await sync_service.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main()) 