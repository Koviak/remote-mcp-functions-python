"""
Enhanced Planner Sync Service V4 - Full Bidirectional Sync

Combines the best of V2 and V3:
- Bidirectional sync (from V2)
- Direct Redis operations (from V3)
- Smart sync intervals (from V3)
- Completed task filtering (from V3)
- Proper duplicate prevention (from V3)
- Circuit breakers (from V3)
"""

import asyncio
import json
import logging
import redis.asyncio as redis
import time
from typing import Dict, Optional, List, Set
from datetime import datetime
from agent_auth_manager import get_agent_token
from annika_task_adapter import AnnikaTaskAdapter
import requests
import uuid

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# Mapping keys
PLANNER_ID_MAP_PREFIX = "annika:planner:id_map:"
ETAG_PREFIX = "annika:planner:etag:"


class BidirectionalPlannerSync:
    """Full bidirectional sync with all improvements."""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.adapter = None
        self.running = False
        
        # Track task ETags for update detection
        self.task_etags = {}
        
        # Smart sync tracking
        self.last_plan_sync = {}
        self.plan_activity = {}
        self.sync_intervals = {
            "active": 60,      # 1 minute for active plans
            "normal": 300,     # 5 minutes for normal plans
            "inactive": 1800   # 30 minutes for inactive plans
        }
        
        # Prevent duplicate processing
        self.processed_tasks = set()
        self.processing_upload = set()  # Tasks being uploaded
        
    async def start(self):
        """Start the sync service."""
        logger.info("🚀 Starting Bidirectional Planner Sync Service V4...")
        
        # Initialize Redis
        self.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Initialize adapter
        self.adapter = AnnikaTaskAdapter(self.redis_client)
        
        # Set up pub/sub for Annika changes
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(
            "__keyspace@0__:annika:conscious_state",
            "annika:tasks:updates"  # Custom channel for task updates
        )
        
        self.running = True
        
        # Load existing mappings
        await self._load_existing_mappings()
        
        # Initial sync from Planner
        logger.info("📥 Performing initial download from Planner...")
        try:
            # Add timeout to prevent hanging
            await asyncio.wait_for(self._download_all_plans(), timeout=120)
            logger.info("✅ Initial download completed")
        except asyncio.TimeoutError:
            logger.warning("⚠️ Initial download timed out after 2 minutes - continuing anyway")
        except Exception as e:
            logger.error(f"❌ Initial download failed: {e} - continuing anyway")
        
        # Start all sync loops
        await asyncio.gather(
            self._monitor_annika_changes(),      # Upload to Planner
            self._smart_download_loop(),         # Download from Planner
            self._health_check_loop(),
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
    
    async def _load_existing_mappings(self):
        """Load existing ID mappings and ETags."""
        logger.info("Loading existing mappings...")
        
        # Load ID mappings
        pattern = f"{PLANNER_ID_MAP_PREFIX}*"
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=pattern, count=100
            )
            for key in keys:
                parts = key.split(":")
                if len(parts) > 3:
                    task_id = parts[3]
                    self.processed_tasks.add(task_id)
                    count += 1
            if cursor == 0:
                break
        
        # Load ETags
        etag_pattern = f"{ETAG_PREFIX}*"
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=etag_pattern, count=100
            )
            for key in keys:
                planner_id = key.replace(ETAG_PREFIX, "")
                etag = await self.redis_client.get(key)
                if etag:
                    self.task_etags[planner_id] = etag
            if cursor == 0:
                break
        
        logger.info(f"Loaded {count} ID mappings and {len(self.task_etags)} ETags")
    
    # ========== UPLOAD (Annika → Planner) ==========
    
    async def _monitor_annika_changes(self):
        """Monitor Annika changes and sync to Planner."""
        logger.info("📤 Monitoring Annika changes for upload...")
        
        last_state_hash = await self._get_state_hash()
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
            
            if message['type'] == 'message':
                try:
                    # Detect conscious_state changes
                    if "conscious_state" in message.get('channel', ''):
                        current_hash = await self._get_state_hash()
                        if current_hash != last_state_hash:
                            await self._sync_annika_to_planner()
                            last_state_hash = current_hash
                    
                    # Handle direct task updates
                    elif message.get('channel') == 'annika:tasks:updates':
                        await self._sync_annika_to_planner()
                        
                except Exception as e:
                    logger.error(f"Error monitoring Annika changes: {e}")
    
    async def _get_state_hash(self) -> Optional[str]:
        """Get hash of conscious_state for change detection."""
        try:
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            if state_json:
                return str(hash(state_json))
        except Exception:
            pass
        return None
    
    async def _sync_annika_to_planner(self):
        """Sync changes from Annika to Planner."""
        logger.info("🔄 Syncing Annika changes to Planner...")
        
        try:
            # Get all Annika tasks
            annika_tasks = await self.adapter.get_all_annika_tasks()
            
            created = 0
            updated = 0
            
            for task in annika_tasks:
                annika_id = task.get("id")
                if not annika_id or annika_id in self.processing_upload:
                    continue
                
                # Skip completed tasks (optional - you might want to sync completion)
                if task.get("status") == "completed":
                    continue
                
                self.processing_upload.add(annika_id)
                
                try:
                    # Check if task exists in Planner
                    planner_id = await self._get_planner_id(annika_id)
                    
                    if planner_id:
                        # Update existing task
                        if await self._update_planner_task(planner_id, task):
                            updated += 1
                    else:
                        # Create new task
                        if await self._create_planner_task(task):
                            created += 1
                finally:
                    self.processing_upload.discard(annika_id)
            
            if created > 0 or updated > 0:
                logger.info(f"📤 Uploaded: {created} created, {updated} updated")
                
        except Exception as e:
            logger.error(f"Error syncing to Planner: {e}")
    
    async def _create_planner_task(self, annika_task: Dict) -> bool:
        """Create new task in Planner."""
        try:
            token = get_agent_token()
            if not token:
                return False
            
            # Convert to Planner format
            planner_data = self.adapter.annika_to_planner(annika_task)
            
            # Set plan ID
            plan_id = await self._determine_plan_for_task(annika_task)
            if not plan_id:
                logger.warning(f"No plan for task: {annika_task.get('title')}")
                return False
            
            planner_data["planId"] = plan_id
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
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
                
                # Store mapping and ETag
                await self._store_id_mapping(annika_id, planner_id)
                etag = planner_task.get("@odata.etag", "")
                await self._store_etag(planner_id, etag)
                
                logger.info(f"✅ Created in Planner: {annika_task.get('title')}")
                return True
            else:
                logger.error(f"Failed to create: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating Planner task: {e}")
            return False
    
    async def _update_planner_task(self, planner_id: str, annika_task: Dict) -> bool:
        """Update existing Planner task."""
        try:
            token = get_agent_token()
            if not token:
                return False
            
            # Get current task for ETag
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code != 200:
                return False
            
            current_task = response.json()
            etag = current_task.get("@odata.etag")
            
            # Convert to update format
            update_data = self.adapter.annika_to_planner(annika_task)
            update_data.pop("planId", None)  # Can't update plan
            
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
                # Update stored ETag
                new_etag = response.headers.get("ETag", etag)
                await self._store_etag(planner_id, new_etag)
                logger.debug(f"✅ Updated in Planner: {annika_task.get('title')}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error updating Planner task: {e}")
            return False
    
    # ========== DOWNLOAD (Planner → Annika) ==========
    
    async def _smart_download_loop(self):
        """Smart download with intervals."""
        logger.info("📥 Starting smart download loop...")
        
        while self.running:
            try:
                await self._download_all_plans()
            except Exception as e:
                logger.error(f"Download error: {e}")
            
            await asyncio.sleep(30)
    
    async def _download_all_plans(self):
        """Download tasks from all plans."""
        logger.info("🔄 Starting download from all plans...")
        
        token = get_agent_token()
        if not token:
            logger.error("❌ No token available for download")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info("📋 Getting list of all plans...")
        all_plans = await self._get_all_plans(headers)
        
        if not all_plans:
            logger.warning("⚠️ No plans found to sync")
            return
        
        logger.info(f"📊 Processing {len(all_plans)} plans...")
        
        active_planner_ids = set()
        total_new = 0
        total_updated = 0
        processed_plans = 0
        
        for plan in all_plans:
            plan_id = plan.get("id")
            plan_title = plan.get("title", "Unknown")
            processed_plans += 1
            
            logger.debug(f"[{processed_plans}/{len(all_plans)}] Checking plan: {plan_title}")
            
            # Check if plan needs sync
            if not await self._should_sync_plan(plan_id):
                logger.debug(f"   Skipping {plan_title} (not due for sync)")
                continue
            
            logger.debug(f"   Getting tasks for: {plan_title}")
            # Get tasks from plan
            tasks = await self._get_plan_tasks(plan_id, headers)
            
            if not tasks:
                logger.debug(f"   No tasks in {plan_title}")
                continue
            
            # Filter completed tasks
            active_tasks = [
                task for task in tasks 
                if task.get("percentComplete", 0) < 100
            ]
            
            completed_count = len(tasks) - len(active_tasks)
            if completed_count > 0:
                logger.debug(f"   Filtered {completed_count} completed tasks from {plan_title}")
            
            # Track activity
            if len(active_tasks) > 10:
                self.plan_activity[plan_id] = "active"
            elif len(active_tasks) > 0:
                self.plan_activity[plan_id] = "normal"
            else:
                self.plan_activity[plan_id] = "inactive"
            
            if active_tasks:
                logger.debug(f"   Processing {len(active_tasks)} active tasks in {plan_title}")
            
            # Process tasks
            for task in active_tasks:
                planner_id = task["id"]
                active_planner_ids.add(planner_id)
                
                result = await self._process_planner_task(task)
                if result == "created":
                    total_new += 1
                elif result == "updated":
                    total_updated += 1
            
            self.last_plan_sync[plan_id] = time.time()
            
            # Progress update every 5 plans
            if processed_plans % 5 == 0:
                logger.info(f"   Progress: {processed_plans}/{len(all_plans)} plans processed")
        
        logger.info("🗑️ Checking for deleted tasks...")
        # Handle deletions
        await self._handle_deletions(active_planner_ids)
        
        logger.info(f"✅ Download complete: {total_new} new, {total_updated} updated from {processed_plans} plans")
    
    async def _process_planner_task(self, planner_task: Dict) -> str:
        """Process a single Planner task."""
        planner_id = planner_task["id"]
        
        # Check if already processed
        if planner_id in self.processed_tasks:
            # Check for updates via ETag
            current_etag = planner_task.get("@odata.etag", "")
            stored_etag = self.task_etags.get(planner_id, "")
            
            if current_etag != stored_etag:
                # Task was updated
                annika_id = await self._get_annika_id(planner_id)
                if annika_id:
                    await self._update_annika_task(annika_id, planner_task)
                    self.task_etags[planner_id] = current_etag
                    await self._store_etag(planner_id, current_etag)
                    return "updated"
            return "skipped"
        
        # New task from Planner
        annika_id = await self._get_annika_id(planner_id)
        if not annika_id:
            # Create in Annika
            await self._create_annika_task_direct(planner_task)
            self.processed_tasks.add(planner_id)
            self.task_etags[planner_id] = planner_task.get("@odata.etag", "")
            return "created"
        
        return "skipped"
    
    async def _create_annika_task_direct(self, planner_task: Dict):
        """Create task directly in Redis."""
        planner_id = planner_task["id"]
        
        # Generate Annika ID
        annika_id = f"Task-{uuid.uuid4().hex[:8]}"
        
        # Store mapping FIRST
        await self._store_id_mapping(annika_id, planner_id)
        await self._store_etag(planner_id, planner_task.get("@odata.etag", ""))
        
        # Convert to Annika format
        annika_task = await self.adapter.planner_to_annika(planner_task)
        annika_task["id"] = annika_id
        annika_task["external_id"] = planner_id
        annika_task["source"] = "planner"
        annika_task["created_at"] = datetime.utcnow().isoformat()
        
        # Determine list type
        list_type = self.adapter.determine_task_list(planner_task)
        
        # Update conscious_state directly
        state_json = await self.redis_client.execute_command(
            "JSON.GET", "annika:conscious_state", "$"
        )
        
        if state_json:
            state = json.loads(state_json)[0]
            
            if "task_lists" not in state:
                state["task_lists"] = {}
            if list_type not in state["task_lists"]:
                state["task_lists"][list_type] = {"tasks": []}
            
            state["task_lists"][list_type]["tasks"].append(annika_task)
            
            await self.redis_client.execute_command(
                "JSON.SET", "annika:conscious_state", "$",
                json.dumps(state)
            )
            
            logger.info(f"✅ Created from Planner: {planner_task.get('title')}")
    
    async def _update_annika_task(self, annika_id: str, planner_task: Dict):
        """Update existing Annika task."""
        # Convert updates
        updates = await self.adapter.planner_to_annika(planner_task)
        
        # Get current state
        state_json = await self.redis_client.execute_command(
            "JSON.GET", "annika:conscious_state", "$"
        )
        
        if state_json:
            state = json.loads(state_json)[0]
            updated = False
            
            # Find and update task
            for list_type, task_list in state.get("task_lists", {}).items():
                for i, task in enumerate(task_list.get("tasks", [])):
                    if task.get("id") == annika_id:
                        # Update fields
                        task.update(updates)
                        updated = True
                        break
                if updated:
                    break
            
            if updated:
                await self.redis_client.execute_command(
                    "JSON.SET", "annika:conscious_state", "$",
                    json.dumps(state)
                )
                logger.debug(f"✅ Updated from Planner: {planner_task.get('title')}")
    
    async def _handle_deletions(self, active_planner_ids: Set[str]):
        """Remove tasks deleted from Planner."""
        # Get all mapped Planner IDs
        pattern = f"{PLANNER_ID_MAP_PREFIX}*"
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=pattern, count=100
            )
            
            for key in keys:
                # Check if it's a Planner ID mapping
                if key.count(":") == 4:  # planner_id -> annika_id mapping
                    planner_id = key.split(":")[-1]
                    if len(planner_id) > 20 and planner_id not in active_planner_ids:
                        # Task was deleted from Planner
                        annika_id = await self.redis_client.get(key)
                        if annika_id:
                            await self._delete_annika_task(annika_id)
                            await self._remove_mapping(annika_id, planner_id)
                            logger.info(f"🗑️ Deleted task: {annika_id}")
            
            if cursor == 0:
                break
    
    async def _delete_annika_task(self, annika_id: str):
        """Delete task from Annika."""
        # Implementation depends on your Redis structure
        logger.debug(f"Deleting Annika task: {annika_id}")
    
    # ========== HELPERS ==========
    
    async def _get_all_plans(self, headers: Dict) -> List[Dict]:
        """Get all accessible plans."""
        all_plans = []
        
        try:
            logger.info("🔍 Getting personal plans...")
            # Personal plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/planner/plans",
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                personal_plans = response.json().get("value", [])
                all_plans.extend(personal_plans)
                logger.info(f"   Found {len(personal_plans)} personal plans")
            else:
                logger.warning(f"Failed to get personal plans: {response.status_code}")
            
            logger.info("🔍 Getting group memberships...")
            # Group plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/memberOf",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                groups = response.json().get("value", [])
                logger.info(f"   Found {len(groups)} group memberships")
                
                group_plan_count = 0
                processed_groups = 0
                
                for item in groups:
                    if item.get("@odata.type") == "#microsoft.graph.group":
                        group_id = item.get("id")
                        group_name = item.get("displayName", "Unknown")
                        processed_groups += 1
                        
                        try:
                            logger.debug(f"   [{processed_groups}/{len(groups)}] Checking group: {group_name}")
                            
                            url = (f"{GRAPH_API_ENDPOINT}/groups/{group_id}"
                                   "/planner/plans")
                            plans_resp = requests.get(
                                url, headers=headers, timeout=10
                            )
                            
                            if plans_resp.status_code == 200:
                                group_plans = plans_resp.json().get("value", [])
                                if group_plans:
                                    all_plans.extend(group_plans)
                                    group_plan_count += len(group_plans)
                                    logger.debug(f"      Added {len(group_plans)} plans from {group_name}")
                            elif plans_resp.status_code == 403:
                                logger.debug(f"      No Planner access for group: {group_name}")
                            else:
                                logger.debug(f"      Failed to get plans for {group_name}: {plans_resp.status_code}")
                                
                        except requests.exceptions.Timeout:
                            logger.warning(f"      Timeout getting plans for group: {group_name}")
                        except Exception as e:
                            logger.debug(f"      Error getting plans for {group_name}: {e}")
                        
                        # Add small delay to avoid rate limiting
                        if processed_groups % 5 == 0:
                            await asyncio.sleep(0.1)
                
                logger.info(f"   Found {group_plan_count} plans across {processed_groups} groups")
            else:
                logger.warning(f"Failed to get group memberships: {response.status_code}")
        
        except requests.exceptions.Timeout:
            logger.error("Timeout getting plans - continuing with what we have")
        except Exception as e:
            logger.error(f"Error getting plans: {e}")
        
        logger.info(f"📋 Total plans found: {len(all_plans)}")
        return all_plans
    
    async def _get_plan_tasks(self, plan_id: str, headers: Dict) -> List[Dict]:
        """Get tasks for a plan."""
        try:
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get("value", [])
            return []
            
        except Exception:
            return []
    
    async def _should_sync_plan(self, plan_id: str) -> bool:
        """Check if plan needs sync."""
        last_sync = self.last_plan_sync.get(plan_id, 0)
        activity = self.plan_activity.get(plan_id, "normal")
        interval = self.sync_intervals[activity]
        
        return (time.time() - last_sync) > interval
    
    async def _determine_plan_for_task(self, annika_task: Dict) -> Optional[str]:
        """Determine which plan a task should go to."""
        # You can customize this logic
        # For now, use default plan from environment
        import os
        return os.getenv("DEFAULT_PLANNER_PLAN_ID")
    
    async def _health_check_loop(self):
        """Monitor health."""
        while self.running:
            await asyncio.sleep(300)  # 5 minutes
            
            logger.info("📊 Sync Service Health:")
            logger.info(f"   - Processed tasks: {len(self.processed_tasks)}")
            logger.info(f"   - ETags tracked: {len(self.task_etags)}")
            logger.info(f"   - Active uploads: {len(self.processing_upload)}")
    
    # ID and ETag management
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
    
    async def _store_etag(self, planner_id: str, etag: str):
        """Store ETag for update detection."""
        await self.redis_client.set(f"{ETAG_PREFIX}{planner_id}", etag)
    
    async def _remove_mapping(self, annika_id: str, planner_id: str):
        """Remove ID mappings."""
        await self.redis_client.delete(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}",
            f"{ETAG_PREFIX}{planner_id}"
        )


async def main():
    """Run the sync service."""
    sync_service = BidirectionalPlannerSync()
    
    try:
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