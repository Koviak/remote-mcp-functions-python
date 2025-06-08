#!/usr/bin/env python3
"""
Process pending task operations in the queue.
This simulates what TaskListManager would do.
"""
import redis
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
    import requests
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

# Connect to Redis
r = redis.Redis(
    host='localhost',
    port=6379,
    password='password',
    decode_responses=True
)

def check_task_locations():
    """Check where tasks are actually located in Planner."""
    print("=" * 60)
    print("Checking Task Locations in MS Planner")
    print("=" * 60)
    
    token = get_agent_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get ID mappings from Redis
    mapping_keys = r.keys("annika:planner:id_map:*")
    planner_ids = set()
    
    for key in mapping_keys:
        value = r.get(key)
        # Skip Annika IDs, we want Planner IDs
        if value and not value.startswith("task-"):
            planner_ids.add(value)
    
    print(f"\n📊 Found {len(planner_ids)} unique Planner task IDs in mappings")
    
    # Check which plans these tasks belong to
    plans_count = {}
    sample_tasks = {}
    
    for planner_id in list(planner_ids)[:20]:  # Check first 20
        try:
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                task = response.json()
                plan_id = task.get("planId")
                
                if plan_id:
                    # Get plan details
                    plan_response = requests.get(
                        f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
                        headers=headers,
                        timeout=10
                    )
                    
                    if plan_response.status_code == 200:
                        plan = plan_response.json()
                        plan_title = plan.get("title", "Unknown")
                        
                        if plan_title not in plans_count:
                            plans_count[plan_title] = 0
                            sample_tasks[plan_title] = []
                        
                        plans_count[plan_title] += 1
                        
                        if len(sample_tasks[plan_title]) < 3:
                            sample_tasks[plan_title].append(
                                task.get("title", "Untitled")
                            )
        except Exception as e:
            continue
    
    print("\n📍 Task Distribution (sample of first 20):")
    for plan_name, count in plans_count.items():
        print(f"\n  📁 {plan_name}: ~{count} tasks")
        print("     Sample tasks:")
        for task_title in sample_tasks[plan_name]:
            print(f"     - {task_title}")


def process_pending_operations():
    """Process pending task operations."""
    print("\n" + "=" * 60)
    print("Processing Pending Task Operations")
    print("=" * 60)
    
    queue_length = r.llen("annika:task_ops:requests")
    print(f"\n📋 Operations in queue: {queue_length}")
    
    if queue_length == 0:
        print("✅ No pending operations")
        return
    
    print("\nShowing first 10 operations:")
    
    # Peek at operations without removing them
    operations = r.lrange("annika:task_ops:requests", 0, 9)
    
    for i, op_json in enumerate(operations, 1):
        try:
            op = json.loads(op_json)
            op_type = op.get("operation_type", "unknown")
            payload = op.get("payload", {})
            
            print(f"\n[{i}] {op_type}")
            
            if op_type == "create_task":
                print(f"  Title: {payload.get('title', 'Untitled')}")
                print(f"  List: {payload.get('list_type', 'unknown')}")
                print(f"  Source: {payload.get('source', 'unknown')}")
                print(f"  External ID: {payload.get('external_id', 'None')}")
            elif op_type == "update_task":
                print(f"  Task ID: {payload.get('task_id', 'unknown')}")
                updates = payload.get("updates", {})
                if updates:
                    print(f"  Updates: {list(updates.keys())}")
        except Exception as e:
            print(f"[{i}] Error parsing operation: {e}")
    
    if queue_length > 10:
        print(f"\n... and {queue_length - 10} more operations")
    
    print("\n⚠️  These operations are stuck because TaskListManager isn't running!")
    print("They include:")
    print("  - New tasks created in Planner that need to sync to Redis")
    print("  - Updates to existing tasks")
    

def main():
    """Main function."""
    # Check where tasks currently are
    check_task_locations()
    
    # Show pending operations
    process_pending_operations()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("\n🔍 Current situation:")
    print("  1. Tasks exist in Redis task_lists structure")
    print("  2. Tasks are mapped to their original Planner location (likely Firefly)")
    print("  3. New tasks from Planner are stuck in the operation queue")
    print("  4. TaskListManager is not running to process operations")
    
    print("\n💡 To fix this:")
    print("  1. Start TaskListManager to process the queue")
    print("  2. Use the migration tool to move tasks from Firefly to The Bridge")
    print("  3. Ensure all services are running together")


if __name__ == "__main__":
    main() 