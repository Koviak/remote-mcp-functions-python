"""
Simple Subtask Sync Test - Manual Verification
==============================================

Creates a task with subtasks and shows you where to check in Planner Online.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

import redis.asyncio as redis

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")


async def create_simple_test():
    """Create a simple test task with subtasks for manual verification."""
    
    print("="*70)
    print("SIMPLE SUBTASK SYNC TEST")
    print("="*70)
    
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    
    try:
        # Create IDs
        task_id = f"Task-SUBTEST-{uuid.uuid4().hex[:6]}"
        sub1_id = f"Task-SUB1-{uuid.uuid4().hex[:6]}"
        sub2_id = f"Task-SUB2-{uuid.uuid4().hex[:6]}"
        sub3_id = f"Task-SUB3-{uuid.uuid4().hex[:6]}"
        
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        
        # Create parent task
        parent = {
            "id": task_id,
            "title": f"[SUBTEST] Verify Checklist Sync - {timestamp}",
            "description": "This task should appear in Planner with 3 checklist items",
            "status": "not_started",
            "priority": "high",
            "percent_complete": 0.0,
            "assigned_to": "Annika",
            "subtask_ids": [sub1_id, sub2_id, sub3_id],
            "subtasks_created": True,
            "source": "manual_test",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Create subtasks
        subtasks = [
            {
                "id": sub1_id,
                "title": "✓ Step 1: Initial setup",
                "status": "completed",
                "parent_task_id": task_id,
                "source": "manual_test",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            },
            {
                "id": sub2_id,
                "title": "⏳ Step 2: In progress work",
                "status": "in_progress",
                "parent_task_id": task_id,
                "source": "manual_test",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            },
            {
                "id": sub3_id,
                "title": "☐ Step 3: Not started yet",
                "status": "not_started",
                "parent_task_id": task_id,
                "source": "manual_test",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
        ]
        
        # Write to Redis
        await redis_client.execute_command(
            "JSON.SET", f"annika:tasks:{task_id}", "$", json.dumps(parent)
        )
        print(f"\n✅ Created parent task in Redis: {task_id}")
        
        for subtask in subtasks:
            await redis_client.execute_command(
                "JSON.SET", f"annika:tasks:{subtask['id']}", "$", json.dumps(subtask)
            )
            print(f"   ✅ Created subtask: {subtask['title']}")
        
        # Publish notification
        await redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "created",
                "task_id": task_id,
                "task": parent,
                "source": "manual_test"
            })
        )
        
        print(f"\n📤 Published to sync service...")
        print(f"\n⏳ Waiting 15 seconds for sync...")
        await asyncio.sleep(15)
        
        # Check if mapped to Planner
        planner_id = await redis_client.get(f"annika:planner:id_map:{task_id}")
        
        if planner_id:
            print(f"\n✅ SUCCESS! Task synced to Planner")
            print(f"   Planner ID: {planner_id}")
            print(f"\n📋 TO VERIFY CHECKLIST ITEMS:")
            print(f"   1. Open Microsoft Planner: https://tasks.office.com/")
            print(f"   2. Search for task: '{parent['title']}'")
            print(f"   3. Open the task card")
            print(f"   4. Look for 3 checklist items:")
            print(f"      - ✓ Step 1: Initial setup (CHECKED)")
            print(f"      - ⏳ Step 2: In progress work (UNCHECKED)")
            print(f"      - ☐ Step 3: Not started yet (UNCHECKED)")
            
            # Check for details ETag
            details_etag = await redis_client.get(f"annika:planner:etag:{planner_id}:details")
            if details_etag:
                print(f"\n✅ Task details ETag stored: {details_etag[:50]}...")
            else:
                print(f"\n⚠️  No task details ETag found (checklist may not have synced)")
            
        else:
            print(f"\n⚠️  Task not yet synced to Planner (may still be in queue)")
            print(f"   Check Redis key: annika:planner:id_map:{task_id}")
            print(f"   Or wait longer and check Planner for: '{parent['title']}'")
        
        print(f"\n📝 Cleanup:")
        print(f"   To remove test data, delete tasks in Planner OR run:")
        print(f"   redis-cli DEL annika:tasks:{task_id}")
        for sub in subtasks:
            print(f"   redis-cli DEL annika:tasks:{sub['id']}")
    
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    print("\n🧪 Running simple subtask sync verification test...\n")
    asyncio.run(create_simple_test())
    print("\n✅ Test complete!\n")



