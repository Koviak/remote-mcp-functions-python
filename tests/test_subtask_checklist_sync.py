"""
Comprehensive E2E Test for Planner Subtask/Checklist Synchronization
====================================================================

Tests bidirectional sync of Annika subtasks ↔ Planner checklist items
using live Microsoft Graph API and Redis.

Test Coverage:
1. Create task with subtasks in Redis → Verify checklist in Planner Online
2. Update checklist in Planner Online → Verify subtasks updated in Redis
3. Add checklist item in Planner → Verify new subtask created in Redis
4. Delete checklist item in Planner → Verify subtask removed from Redis
5. Mark checklist complete in Planner → Verify subtask status in Redis
6. Create subtask in Redis → Verify checklist item in Planner
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any

import httpx
import redis.asyncio as redis

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from annika_task_adapter import AnnikaTaskAdapter

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Test state tracking
test_tasks_created = []
test_cleanup_needed = []


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def pass_test(self, name: str):
        print(f"[PASS] {name}")
        self.passed += 1
    
    def fail_test(self, name: str, reason: str):
        print(f"[FAIL] {name}: {reason}")
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"Test Summary: {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailures:")
            for error in self.errors:
                print(f"  - {error}")
        print(f"{'='*70}")
        return self.failed == 0


async def get_delegated_token() -> str:
    """Get delegated auth token from Redis using correct key format."""
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    try:
        # The token is stored with a very long scope string - scan for it
        cursor = 0
        token_keys_found = []
        while True:
            cursor, keys = await redis_client.scan(
                cursor, match="annika:tokens:agent:*", count=100
            )
            token_keys_found.extend(keys)
            
            for key in keys:
                # Skip application tokens (they have "application:" in the scope part)
                if ":application:https" in key:
                    print(f"  Skipping application token: {key[:80]}")
                    continue
                
                print(f"  Checking token key: {key[:80]}...")
                    
                token_data = await redis_client.get(key)
                if token_data:
                    try:
                        token_obj = json.loads(token_data)
                        # The field is called 'token', not 'access_token'
                        access_token = token_obj.get("token") or token_obj.get("access_token")
                        if access_token:
                            print(f"✓ Found delegated token (key length: {len(key)} chars)")
                            return access_token
                    except Exception as parse_err:
                        print(f"  Failed to parse token JSON: {parse_err}")
            
            if cursor == 0:
                break
        
        # Debug: show what we found
        print(f"DEBUG: Found {len(token_keys_found)} token keys total")
        if token_keys_found:
            print(f"DEBUG: Keys found: {[k[:80] for k in token_keys_found]}")
    finally:
        await redis_client.aclose()
    return ""


async def get_test_plan_and_bucket(token: str) -> tuple:
    """Get a test plan and bucket for creating tasks."""
    async with httpx.AsyncClient() as client:
        # Get groups first
        response = await client.get(
            f"{GRAPH_API_ENDPOINT}/me/memberOf",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        
        if response.status_code == 200:
            groups = response.json().get("value", [])
            for group in groups:
                if group.get("@odata.type") == "#microsoft.graph.group":
                    group_id = group.get("id")
                    
                    # Get plans for this group
                    plans_resp = await client.get(
                        f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15
                    )
                    
                    if plans_resp.status_code == 200:
                        plans = plans_resp.json().get("value", [])
                        if plans:
                            plan_id = plans[0]["id"]
                            
                            # Get first bucket from plan
                            buckets_resp = await client.get(
                                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets",
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=15
                            )
                            
                            if buckets_resp.status_code == 200:
                                buckets = buckets_resp.json().get("value", [])
                                if buckets:
                                    return plan_id, buckets[0]["id"]
                            
                            return plan_id, None
    
    return None, None


async def create_test_task_with_subtasks_in_redis(
    redis_client: redis.Redis,
    plan_id: str,
    bucket_id: str
) -> Dict[str, Any]:
    """Create a test task with subtasks in Redis."""
    task_id = f"Task-test-{uuid.uuid4().hex[:8]}"
    subtask1_id = f"Task-sub1-{uuid.uuid4().hex[:8]}"
    subtask2_id = f"Task-sub2-{uuid.uuid4().hex[:8]}"
    subtask3_id = f"Task-sub3-{uuid.uuid4().hex[:8]}"
    
    # Create parent task
    parent_task = {
        "id": task_id,
        "title": f"[TEST] Parent Task with Subtasks - {datetime.utcnow().isoformat()}",
        "description": "Test task to verify subtask sync to Planner checklist",
        "status": "not_started",
        "priority": "normal",
        "percent_complete": 0.0,
        "assigned_to": "Annika",
        "subtask_ids": [subtask1_id, subtask2_id, subtask3_id],
        "subtasks_created": True,
        "source": "test",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "planner_plan_id": plan_id,
        "bucket_id": bucket_id
    }
    
    # Create subtasks
    subtasks = [
        {
            "id": subtask1_id,
            "title": "Subtask 1: Research requirements",
            "description": "First checklist item",
            "status": "not_started",
            "parent_task_id": task_id,
            "source": "test",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        },
        {
            "id": subtask2_id,
            "title": "Subtask 2: Draft proposal",
            "description": "Second checklist item",
            "status": "completed",  # This one is completed
            "parent_task_id": task_id,
            "source": "test",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        },
        {
            "id": subtask3_id,
            "title": "Subtask 3: Final review",
            "description": "Third checklist item",
            "status": "in_progress",
            "parent_task_id": task_id,
            "source": "test",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
    ]
    
    # Write to Redis
    await redis_client.execute_command(
        "JSON.SET", f"annika:tasks:{task_id}", "$", json.dumps(parent_task)
    )
    
    for subtask in subtasks:
        await redis_client.execute_command(
            "JSON.SET", f"annika:tasks:{subtask['id']}", "$", json.dumps(subtask)
        )
    
    # Publish notification to trigger sync
    await redis_client.publish(
        "annika:tasks:updates",
        json.dumps({
            "action": "created",
            "task_id": task_id,
            "task": parent_task,
            "source": "test"
        })
    )
    
    test_tasks_created.append(task_id)
    test_tasks_created.extend([subtask1_id, subtask2_id, subtask3_id])
    
    return {
        "parent": parent_task,
        "subtasks": subtasks,
        "task_id": task_id,
        "subtask_ids": [subtask1_id, subtask2_id, subtask3_id]
    }


async def wait_for_planner_sync(seconds: int = 8):
    """Wait for sync service to process the task."""
    print(f"⏳ Waiting {seconds}s for Planner sync to process...")
    await asyncio.sleep(seconds)


async def get_planner_task_by_annika_id(
    redis_client: redis.Redis,
    token: str,
    annika_id: str
) -> tuple:
    """Get Planner task ID and details for an Annika task."""
    # Get Planner ID from mapping
    planner_id = await redis_client.get(f"annika:planner:id_map:{annika_id}")
    if not planner_id:
        return None, None
    
    # Get task details from Planner
    async with httpx.AsyncClient() as client:
        # Get main task
        task_resp = await client.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        
        if task_resp.status_code != 200:
            return None, None
        
        task = task_resp.json()
        
        # Get task details (includes checklist)
        details_resp = await client.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}/details",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        
        details = None
        if details_resp.status_code == 200:
            details = details_resp.json()
        
        return task, details


async def update_planner_checklist_item(
    token: str,
    planner_id: str,
    checklist_item_id: str,
    is_checked: bool,
    details_etag: str
) -> bool:
    """Update a checklist item in Planner Online."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}/details",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": details_etag,
                "Prefer": "return=representation"
            },
            json={
                "checklist": {
                    checklist_item_id: {
                        "@odata.type": "microsoft.graph.plannerChecklistItem",
                        "isChecked": is_checked
                    }
                }
            },
            timeout=15
        )
        return response.status_code in (200, 204)


async def add_planner_checklist_item(
    token: str,
    planner_id: str,
    title: str,
    details_etag: str
) -> tuple:
    """Add a new checklist item to Planner Online."""
    new_item_id = str(uuid.uuid4())
    
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}/details",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": details_etag,
                "Prefer": "return=representation"
            },
            json={
                "checklist": {
                    new_item_id: {
                        "@odata.type": "microsoft.graph.plannerChecklistItem",
                        "title": title,
                        "isChecked": False,
                        "orderHint": " !"
                    }
                }
            },
            timeout=15
        )
        
        if response.status_code == 200:
            new_details = response.json()
            return new_item_id, new_details.get("@odata.etag")
        return None, None


async def delete_planner_checklist_item(
    token: str,
    planner_id: str,
    checklist_item_id: str,
    details_etag: str
) -> bool:
    """Delete a checklist item from Planner Online."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}/details",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": details_etag
            },
            json={
                "checklist": {
                    checklist_item_id: None  # Null deletes the item
                }
            },
            timeout=15
        )
        return response.status_code in (200, 204)


async def cleanup_test_data(redis_client: redis.Redis, token: str):
    """Clean up all test data from Redis and Planner."""
    print("\n🧹 Cleaning up test data...")
    
    async with httpx.AsyncClient() as client:
        for task_id in test_tasks_created:
            # Delete from Redis
            try:
                await redis_client.delete(f"annika:tasks:{task_id}")
                print(f"  Deleted Redis task: {task_id}")
            except Exception as e:
                print(f"  Failed to delete Redis task {task_id}: {e}")
            
            # Get Planner ID and delete if exists
            try:
                planner_id = await redis_client.get(f"annika:planner:id_map:{task_id}")
                if planner_id:
                    # Get task for ETag
                    task_resp = await client.get(
                        f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10
                    )
                    
                    if task_resp.status_code == 200:
                        task = task_resp.json()
                        etag = task.get("@odata.etag")
                        
                        # Delete from Planner
                        delete_resp = await client.delete(
                            f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "If-Match": etag
                            },
                            timeout=10
                        )
                        
                        if delete_resp.status_code in (200, 204):
                            print(f"  Deleted Planner task: {planner_id}")
                    
                    # Clean up mappings
                    await redis_client.delete(
                        f"annika:planner:id_map:{task_id}",
                        f"annika:task:mapping:planner:{planner_id}",
                        f"annika:planner:etag:{planner_id}",
                        f"annika:planner:etag:{planner_id}:details"
                    )
            except Exception as e:
                print(f"  Error cleaning Planner task for {task_id}: {e}")


async def run_comprehensive_tests():
    """Run comprehensive subtask/checklist sync tests."""
    results = TestResults()
    
    print("="*70)
    print("COMPREHENSIVE PLANNER SUBTASK/CHECKLIST SYNC TEST")
    print("="*70)
    
    # Setup
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    
    token = await get_delegated_token()
    if not token:
        print("[ERROR] No delegated token available. Cannot run tests.")
        return False
    
    print(f"\n✅ Token acquired")
    
    # Use known accessible plan from the sync service logs
    plan_id = "_XVogjqO3UqnqsyWeIB2RGUADdnA"  # From startup logs
    bucket_id = None  # Let Planner assign default bucket
    
    print(f"✅ Using plan: {plan_id}")
    print(f"✅ Bucket: {bucket_id or 'Default (auto-assigned)'}")
    
    try:
        # TEST 1: Create task with subtasks in Redis → Verify checklist in Planner
        print("\n" + "-"*70)
        print("TEST 1: Redis subtasks → Planner checklist items")
        print("-"*70)
        
        test_data = await create_test_task_with_subtasks_in_redis(
            redis_client, plan_id, bucket_id
        )
        parent_id = test_data["task_id"]
        
        print(f"Created parent task: {parent_id}")
        print(f"Created 3 subtasks: {test_data['subtask_ids']}")
        
        # Wait for sync
        await wait_for_planner_sync(10)
        
        # Verify task created in Planner
        planner_task, planner_details = await get_planner_task_by_annika_id(
            redis_client, token, parent_id
        )
        
        if not planner_task:
            results.fail_test("TEST 1: Task creation", "Task not found in Planner")
        else:
            planner_id = planner_task["id"]
            print(f"✓ Task created in Planner: {planner_id}")
            
            # Verify checklist exists
            if not planner_details:
                results.fail_test("TEST 1: Checklist creation", "Task details not found")
            elif not planner_details.get("checklist"):
                results.fail_test("TEST 1: Checklist creation", "Checklist is empty")
            else:
                checklist = planner_details["checklist"]
                checklist_count = len(checklist)
                
                if checklist_count != 3:
                    results.fail_test(
                        "TEST 1: Checklist count",
                        f"Expected 3 items, got {checklist_count}"
                    )
                else:
                    results.pass_test("TEST 1: Checklist count (3 items)")
                
                # Verify one item is checked (subtask2 was completed)
                checked_items = [
                    item for item in checklist.values()
                    if item and item.get("isChecked")
                ]
                
                if len(checked_items) != 1:
                    results.fail_test(
                        "TEST 1: Checked status",
                        f"Expected 1 checked item, got {len(checked_items)}"
                    )
                else:
                    results.pass_test("TEST 1: Checked status sync")
                
                # Verify titles match
                titles = [
                    item.get("title") for item in checklist.values()
                    if item
                ]
                if "Subtask 1: Research requirements" in titles:
                    results.pass_test("TEST 1: Subtask titles synced")
                else:
                    results.fail_test("TEST 1: Subtask titles", "Titles don't match")
        
        # TEST 2: Update checklist in Planner → Verify subtasks updated in Redis
        print("\n" + "-"*70)
        print("TEST 2: Planner checklist update → Redis subtasks")
        print("-"*70)
        
        if planner_task and planner_details:
            planner_id = planner_task["id"]
            checklist = planner_details.get("checklist", {})
            details_etag = planner_details.get("@odata.etag")
            
            if checklist and details_etag:
                # Find an unchecked item and check it
                unchecked_item_id = None
                for item_id, item_data in checklist.items():
                    if item_data and not item_data.get("isChecked"):
                        unchecked_item_id = item_id
                        break
                
                if unchecked_item_id:
                    print(f"Checking item in Planner: {unchecked_item_id}")
                    success = await update_planner_checklist_item(
                        token, planner_id, unchecked_item_id, True, details_etag
                    )
                    
                    if success:
                        print("✓ Checklist item updated in Planner")
                        
                        # Wait for sync back to Redis
                        await wait_for_planner_sync(8)
                        
                        # Verify subtask marked complete in Redis
                        subtask_redis_id = f"Task-{unchecked_item_id}"
                        subtask_data = await redis_client.execute_command(
                            "JSON.GET", f"annika:tasks:{subtask_redis_id}", "$"
                        )
                        
                        if subtask_data:
                            subtask = json.loads(subtask_data)[0]
                            if subtask.get("status") == "completed":
                                results.pass_test("TEST 2: Checklist update → subtask status")
                            else:
                                results.fail_test(
                                    "TEST 2: Status sync",
                                    f"Subtask status is {subtask.get('status')}, expected 'completed'"
                                )
                        else:
                            results.fail_test("TEST 2: Subtask retrieval", "Subtask not found in Redis")
                    else:
                        results.fail_test("TEST 2: Update checklist", "Failed to update in Planner")
        
        # TEST 3: Add new checklist item in Planner → Verify new subtask in Redis
        print("\n" + "-"*70)
        print("TEST 3: Add Planner checklist item → New Redis subtask")
        print("-"*70)
        
        # Refetch details for current ETag
        if planner_task:
            planner_id = planner_task["id"]
            _, fresh_details = await get_planner_task_by_annika_id(
                redis_client, token, parent_id
            )
            
            if fresh_details:
                details_etag = fresh_details.get("@odata.etag")
                new_item_id, new_etag = await add_planner_checklist_item(
                    token, planner_id, "NEW: Dynamic checklist item added in Planner", details_etag
                )
                
                if new_item_id:
                    print(f"✓ Added checklist item in Planner: {new_item_id}")
                    test_cleanup_needed.append(f"Task-{new_item_id}")
                    
                    # Wait for sync
                    await wait_for_planner_sync(8)
                    
                    # Verify new subtask created in Redis
                    new_subtask_id = f"Task-{new_item_id}"
                    new_subtask_data = await redis_client.execute_command(
                        "JSON.GET", f"annika:tasks:{new_subtask_id}", "$"
                    )
                    
                    if new_subtask_data:
                        new_subtask = json.loads(new_subtask_data)[0]
                        if new_subtask.get("title") == "NEW: Dynamic checklist item added in Planner":
                            results.pass_test("TEST 3: New checklist item → subtask")
                        else:
                            results.fail_test(
                                "TEST 3: Title sync",
                                f"Title mismatch: {new_subtask.get('title')}"
                            )
                        
                        # Verify parent updated
                        parent_data = await redis_client.execute_command(
                            "JSON.GET", f"annika:tasks:{parent_id}", "$"
                        )
                        if parent_data:
                            parent = json.loads(parent_data)[0]
                            if new_subtask_id in parent.get("subtask_ids", []):
                                results.pass_test("TEST 3: Parent task subtask_ids updated")
                            else:
                                results.fail_test(
                                    "TEST 3: Parent update",
                                    "New subtask ID not in parent's subtask_ids"
                                )
                    else:
                        results.fail_test("TEST 3: Subtask creation", "New subtask not found in Redis")
                else:
                    results.fail_test("TEST 3: Add item", "Failed to add checklist item in Planner")
        
        # TEST 4: Delete checklist item in Planner → Verify subtask removed from Redis
        print("\n" + "-"*70)
        print("TEST 4: Delete Planner checklist item → Remove Redis subtask")
        print("-"*70)
        
        if planner_task:
            planner_id = planner_task["id"]
            _, fresh_details2 = await get_planner_task_by_annika_id(
                redis_client, token, parent_id
            )
            
            if fresh_details2 and fresh_details2.get("checklist"):
                details_etag2 = fresh_details2.get("@odata.etag")
                checklist2 = fresh_details2["checklist"]
                
                # Pick first item to delete
                item_to_delete = list(checklist2.keys())[0]
                subtask_to_delete = f"Task-{item_to_delete}"
                
                print(f"Deleting checklist item: {item_to_delete}")
                
                success = await delete_planner_checklist_item(
                    token, planner_id, item_to_delete, details_etag2
                )
                
                if success:
                    print("✓ Checklist item deleted in Planner")
                    
                    # Wait for sync
                    await wait_for_planner_sync(8)
                    
                    # Verify subtask removed from Redis
                    deleted_subtask = await redis_client.execute_command(
                        "JSON.GET", f"annika:tasks:{subtask_to_delete}", "$"
                    )
                    
                    if not deleted_subtask:
                        results.pass_test("TEST 4: Checklist delete → subtask removed")
                    else:
                        results.fail_test("TEST 4: Subtask deletion", "Subtask still exists in Redis")
                else:
                    results.fail_test("TEST 4: Delete item", "Failed to delete checklist item")
        
        # TEST 5: Create new subtask in Redis → Verify checklist item in Planner
        print("\n" + "-"*70)
        print("TEST 5: Create Redis subtask → New Planner checklist item")
        print("-"*70)
        
        new_subtask_id = f"Task-newsub-{uuid.uuid4().hex[:8]}"
        test_tasks_created.append(new_subtask_id)
        
        new_subtask = {
            "id": new_subtask_id,
            "title": "NEW: Subtask created in Redis",
            "status": "not_started",
            "parent_task_id": parent_id,
            "source": "test",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Add to Redis
        await redis_client.execute_command(
            "JSON.SET", f"annika:tasks:{new_subtask_id}", "$", json.dumps(new_subtask)
        )
        
        # Update parent's subtask_ids
        parent_data = await redis_client.execute_command(
            "JSON.GET", f"annika:tasks:{parent_id}", "$"
        )
        if parent_data:
            parent = json.loads(parent_data)[0]
            if "subtask_ids" not in parent:
                parent["subtask_ids"] = []
            parent["subtask_ids"].append(new_subtask_id)
            parent["updated_at"] = datetime.utcnow().isoformat() + "Z"
            
            await redis_client.execute_command(
                "JSON.SET", f"annika:tasks:{parent_id}", "$", json.dumps(parent)
            )
            
            # Publish update to trigger sync
            await redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "updated",
                    "task_id": parent_id,
                    "task": parent,
                    "source": "test"
                })
            )
            
            print(f"✓ Added new subtask to Redis: {new_subtask_id}")
            
            # Wait for sync
            await wait_for_planner_sync(10)
            
            # Verify checklist item added in Planner
            _, final_details = await get_planner_task_by_annika_id(
                redis_client, token, parent_id
            )
            
            if final_details and final_details.get("checklist"):
                checklist_item_id = new_subtask_id.replace("Task-", "")
                if checklist_item_id in final_details["checklist"]:
                    item = final_details["checklist"][checklist_item_id]
                    if item and item.get("title") == "NEW: Subtask created in Redis":
                        results.pass_test("TEST 5: New subtask → checklist item")
                    else:
                        results.fail_test("TEST 5: Title mismatch", f"Got: {item.get('title') if item else 'None'}")
                else:
                    results.fail_test("TEST 5: Item not found", f"Checklist item {checklist_item_id} not in Planner")
            else:
                results.fail_test("TEST 5: Details fetch", "Could not fetch updated details from Planner")
        
    finally:
        # Cleanup
        await cleanup_test_data(redis_client, token)
        await redis_client.aclose()
    
    # Print summary
    return results.summary()


if __name__ == "__main__":
    print("\n🚀 Starting comprehensive Planner subtask/checklist sync tests...")
    print(f"⏰ Timestamp: {datetime.utcnow().isoformat()}\n")
    
    success = asyncio.run(run_comprehensive_tests())
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

