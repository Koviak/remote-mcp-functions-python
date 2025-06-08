#!/usr/bin/env python3
"""
Inspect all possible task storage locations in Redis.
"""
import redis
import json

# Connect to Redis
r = redis.Redis(
    host='localhost',
    port=6379,
    password='password',
    decode_responses=True
)

print("=" * 60)
print("Inspecting All Task Storage Locations")
print("=" * 60)

# 1. Check conscious_state structure
print("\n1️⃣ Checking annika:conscious_state:")
try:
    state_json = r.execute_command(
        "JSON.GET", "annika:conscious_state", "$"
    )
    if state_json:
        state = json.loads(state_json)[0]
        # Check old structure (task_lists)
        task_lists = state.get("task_lists", {})
        if task_lists:
            print("  Found task_lists structure:")
            for list_name, list_data in task_lists.items():
                count = len(list_data.get("tasks", []))
                print(f"    - {list_name}: {count} tasks")
        
        # Check new structure (direct lists)
        direct_lists = ["active_tasks", "priority_tasks", "completed_tasks", 
                       "longterm_tasks", "delegated_tasks"]
        for list_name in direct_lists:
            if list_name in state:
                count = len(state.get(list_name, []))
                if count > 0:
                    print(f"  Found {list_name}: {count} tasks")
    else:
        print("  ❌ No conscious_state found")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 2. Check conversation-specific tasks
print("\n2️⃣ Checking conversation-specific tasks:")
conv_keys = r.keys("annika:consciousness:*:components:tasks")
print(f"  Found {len(conv_keys)} conversation task keys")
for key in conv_keys[:5]:  # Show first 5
    try:
        data_json = r.execute_command("JSON.GET", key, "$")
        if data_json:
            data = json.loads(data_json)[0]
            tasks = data.get("active_conversation", {}).get("tasks", [])
            print(f"  - {key}: {len(tasks)} tasks")
    except Exception as e:
        print(f"  - {key}: Error reading")

# 3. Check for MCP-style task keys
print("\n3️⃣ Checking MCP-style task keys:")
task_keys = r.keys("annika:tasks:*")
print(f"  Found {len(task_keys)} task keys")

# 4. Check ID mappings
print("\n4️⃣ Checking Planner ID mappings:")
mapping_keys = r.keys("annika:planner:id_map:*")
print(f"  Found {len(mapping_keys)} ID mapping keys")

# 5. Check task operation queue
print("\n5️⃣ Checking task operation queue:")
queue_length = r.llen("annika:task_ops:requests")
print(f"  Task operations in queue: {queue_length}")

# 6. Check for task operation results
print("\n6️⃣ Checking task operation results:")
result_keys = r.keys("annika:task_ops:results:*")
print(f"  Found {len(result_keys)} result keys")

# 7. Look for any other task-related keys
print("\n7️⃣ Other task-related keys:")
all_keys = r.keys("annika:*task*")
unique_patterns = set()
for key in all_keys:
    # Extract pattern
    parts = key.split(":")
    if len(parts) >= 3:
        pattern = f"{parts[0]}:{parts[1]}:{parts[2]}:*"
        unique_patterns.add(pattern)

for pattern in sorted(unique_patterns):
    if pattern not in ["annika:planner:id_map:*", "annika:task_ops:results:*"]:
        matching = len([k for k in all_keys if k.startswith(pattern[:-1])])
        print(f"  - {pattern}: {matching} keys")

print("\n" + "=" * 60) 