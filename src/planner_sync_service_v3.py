"""
Enhanced Planner Sync Service V3

Major improvements:
1. Direct Redis operations (no queue dependency)
2. Filters out completed tasks
3. Circuit breaker pattern
4. Smart sync intervals
5. Proper duplicate prevention
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import redis.asyncio as redis
import requests

from agent_auth_manager import get_agent_token
from annika_task_adapter import AnnikaTaskAdapter

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# Mapping keys
PLANNER_ID_MAP_PREFIX = "annika:planner:id_map:"


class CircuitBreaker:
    """Circuit breaker to prevent endless failures."""
    
    def __init__(self, failure_threshold=5, timeout=60, name="default"):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
        self.name = name
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
                logger.info(f"Circuit breaker {self.name} attempting reset")
            else:
                raise Exception(f"Circuit breaker {self.name} is open")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.name} reset successfully")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(
                    f"Circuit breaker {self.name} opened after "
                    f"{self.failure_count} failures"
                )
            raise e


class SmartPlannerSync:
    """Smart sync service with proper error handling and optimization."""
    
    def __init__(self):
        self.redis_client = None
        self.adapter = None
        self.running = False
        
        # Circuit breakers for different operations
        self.create_breaker = CircuitBreaker(name="create_tasks")
        self.update_breaker = CircuitBreaker(name="update_tasks")
        self.download_breaker = CircuitBreaker(name="download")
        
        # Smart sync tracking
        self.last_plan_sync = {}  # plan_id -> timestamp
        self.plan_activity = {}   # plan_id -> activity level
        self.sync_intervals = {
            "active": 60,      # 1 minute for active plans
            "normal": 300,     # 5 minutes for normal plans
            "inactive": 1800   # 30 minutes for inactive plans
        }
        
        # Cache for processed tasks (prevent re-processing)
        self.processed_tasks = set()
        self.failed_tasks = {}  # task_id -> failure count
        
    async def start(self):
        """Start the sync service."""
        logger.info("🚀 Starting Smart Planner Sync Service V3...")
        
        # Initialize Redis
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        await self.redis_client.ping()
        
        # Initialize adapter
        self.adapter = AnnikaTaskAdapter(self.redis_client)
        
        self.running = True
        
        # Load existing mappings to prevent duplicates
        await self._load_existing_mappings()
        
        # Start sync loops
        await asyncio.gather(
            self._smart_download_loop(),
            self._health_check_loop(),
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop the sync service."""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Sync service stopped")
    
    async def _load_existing_mappings(self):
        """Load existing ID mappings to processed_tasks set."""
        logger.info("Loading existing ID mappings...")
        
        pattern = f"{PLANNER_ID_MAP_PREFIX}*"
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=pattern, count=100
            )
            
            for key in keys:
                # Extract the ID from the key
                parts = key.split(":")
                if len(parts) > 3:
                    task_id = parts[3]
                    self.processed_tasks.add(task_id)
                    count += 1
            
            if cursor == 0:
                break
        
        logger.info(f"Loaded {count} existing task mappings")
    
    async def _smart_download_loop(self):
        """Smart download loop with per-plan intervals."""
        logger.info("Starting smart download loop...")
        
        while self.running:
            try:
                await self.download_breaker.call(self._smart_sync_all_plans)
            except Exception as e:
                logger.error(f"Download loop error: {e}")
            
            # Short sleep before next check
            await asyncio.sleep(30)
    
    async def _smart_sync_all_plans(self):
        """Sync all plans with smart intervals."""
        token = get_agent_token()
        if not token:
            logger.warning("No token available, skipping sync")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get all accessible plans
        all_plans = await self._get_all_plans(headers)
        
        if not all_plans:
            logger.warning("No plans found")
            return
        
        logger.info(f"📋 Found {len(all_plans)} total plans")
        
        # Sync each plan based on its activity level
        synced_count = 0
        skipped_count = 0
        
        for plan in all_plans:
            plan_id = plan.get("id")
            plan_title = plan.get("title", "Unknown")
            
            # Check if this plan needs syncing
            if await self._should_sync_plan(plan_id):
                logger.info(f"🔄 Syncing plan: {plan_title}")
                await self._sync_plan_tasks(plan_id, plan_title, headers)
                synced_count += 1
                
                # Update last sync time
                self.last_plan_sync[plan_id] = time.time()
            else:
                skipped_count += 1
        
        logger.info(
            f"📊 Sync complete: {synced_count} synced, "
            f"{skipped_count} skipped"
        )
    
    async def _get_all_plans(self, headers: Dict) -> List[Dict]:
        """Get all accessible plans (personal + group)."""
        all_plans = []
        
        try:
            # Personal plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/planner/plans",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                all_plans.extend(response.json().get("value", []))
            
            # Group plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/memberOf",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                groups = response.json().get("value", [])
                
                for item in groups:
                    if item.get("@odata.type") == "#microsoft.graph.group":
                        group_id = item.get("id")
                        
                        url = (f"{GRAPH_API_ENDPOINT}/groups/{group_id}"
                               "/planner/plans")
                        plans_resp = requests.get(
                            url,
                            headers=headers,
                            timeout=10
                        )
                        
                        if plans_resp.status_code == 200:
                            all_plans.extend(plans_resp.json().get("value", []))
        
        except Exception as e:
            logger.error(f"Error getting plans: {e}")
        
        return all_plans
    
    async def _should_sync_plan(self, plan_id: str) -> bool:
        """Determine if a plan needs syncing based on activity."""
        last_sync = self.last_plan_sync.get(plan_id, 0)
        
        # Determine activity level (default to normal)
        activity = self.plan_activity.get(plan_id, "normal")
        interval = self.sync_intervals[activity]
        
        return (time.time() - last_sync) > interval
    
    async def _sync_plan_tasks(self, plan_id: str, plan_title: str, headers: Dict):
        """Sync tasks for a specific plan."""
        try:
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get tasks for plan {plan_title}")
                return
            
            tasks = response.json().get("value", [])
            
            # Filter out completed tasks
            active_tasks = [
                task for task in tasks 
                if task.get("percentComplete", 0) < 100
            ]
            
            completed_count = len(tasks) - len(active_tasks)
            
            if completed_count > 0:
                logger.info(
                    f"   Filtered out {completed_count} completed tasks"
                )
            
            if not active_tasks:
                logger.info(f"   No active tasks in {plan_title}")
                return
            
            logger.info(
                f"   Processing {len(active_tasks)} active tasks "
                f"in {plan_title}"
            )
            
            # Track plan activity based on task count
            if len(active_tasks) > 10:
                self.plan_activity[plan_id] = "active"
            elif len(active_tasks) > 0:
                self.plan_activity[plan_id] = "normal"
            else:
                self.plan_activity[plan_id] = "inactive"
            
            # Process each active task
            new_count = 0
            updated_count = 0
            skipped_count = 0
            
            for task in active_tasks:
                result = await self._process_single_task(task)
                if result == "created":
                    new_count += 1
                elif result == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
            
            if new_count > 0 or updated_count > 0:
                logger.info(
                    f"   ✅ {new_count} new, {updated_count} updated, "
                    f"{skipped_count} skipped"
                )
        
        except Exception as e:
            logger.error(f"Error syncing plan {plan_title}: {e}")
    
    async def _process_single_task(self, planner_task: Dict) -> str:
        """Process a single task, return status."""
        planner_id = planner_task["id"]
        task_title = planner_task.get("title", "Untitled")
        
        # Check if already processed recently
        if planner_id in self.processed_tasks:
            return "skipped"
        
        # Check if this task has failed too many times
        if self.failed_tasks.get(planner_id, 0) >= 3:
            logger.debug(f"Skipping failed task: {task_title}")
            return "skipped"
        
        try:
            # Check if task already exists
            annika_id = await self._get_annika_id(planner_id)
            
            if not annika_id:
                # Create new task
                await self.create_breaker.call(
                    self._create_annika_task_direct,
                    planner_task
                )
                self.processed_tasks.add(planner_id)
                return "created"
            else:
                # Task exists - check if needs update (future enhancement)
                self.processed_tasks.add(planner_id)
                return "skipped"
        
        except Exception as e:
            logger.error(f"Error processing task {task_title}: {e}")
            self.failed_tasks[planner_id] = self.failed_tasks.get(planner_id, 0) + 1
            return "failed"
    
    async def _create_annika_task_direct(self, planner_task: Dict):
        """Create task directly in Redis (no queue)."""
        planner_id = planner_task["id"]
        task_title = planner_task.get("title", "Untitled")
        
        logger.info(f"Creating task directly: {task_title}")
        
        # Generate Annika ID
        annika_id = f"Task-{uuid.uuid4().hex[:8]}"
        
        # Store ID mapping FIRST (prevents duplicates)
        await self._store_id_mapping(annika_id, planner_id)
        
        # Convert to Annika format
        annika_task = await self.adapter.planner_to_annika(planner_task)
        annika_task["id"] = annika_id
        annika_task["external_id"] = planner_id
        annika_task["source"] = "planner"
        annika_task["created_at"] = datetime.utcnow().isoformat()
        
        # Determine which list it belongs to
        list_type = self.adapter.determine_task_list(planner_task)
        
        # Get current conscious_state
        state_json = await self.redis_client.execute_command(
            "JSON.GET", "annika:conscious_state", "$"
        )
        
        if state_json:
            state = json.loads(state_json)[0]
            
            # Ensure the task list exists
            if "task_lists" not in state:
                state["task_lists"] = {}
            if list_type not in state["task_lists"]:
                state["task_lists"][list_type] = {"tasks": []}
            
            # Add the task
            state["task_lists"][list_type]["tasks"].append(annika_task)
            
            # Save back to Redis
            await self.redis_client.execute_command(
                "JSON.SET", "annika:conscious_state", "$",
                json.dumps(state)
            )
            
            logger.info(
                f"✅ Created task in Redis: {annika_id} -> {list_type}"
            )
        else:
            logger.error("No conscious_state found in Redis!")
    
    async def _health_check_loop(self):
        """Monitor health and report statistics."""
        while self.running:
            await asyncio.sleep(300)  # Every 5 minutes
            
            # Report statistics
            logger.info("📊 Sync Service Health Check:")
            logger.info(f"   - Processed tasks: {len(self.processed_tasks)}")
            logger.info(f"   - Failed tasks: {len(self.failed_tasks)}")
            logger.info(f"   - Circuit breakers:")
            logger.info(f"     - Create: {self.create_breaker.state}")
            logger.info(f"     - Update: {self.update_breaker.state}")
            logger.info(f"     - Download: {self.download_breaker.state}")
            
            # Clear old processed tasks (older than 1 hour)
            # This prevents memory growth while maintaining dedup
            if len(self.processed_tasks) > 1000:
                self.processed_tasks.clear()
                await self._load_existing_mappings()
    
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


async def main():
    """Run the sync service."""
    sync_service = SmartPlannerSync()
    
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