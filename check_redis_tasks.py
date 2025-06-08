#!/usr/bin/env python3
"""
Check tasks in Redis conscious_state and their Planner mappings.
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
print("Checking Redis Task State")
print("=" * 60)

# Get conscious_state
try:
    state_json = r.execute_command(
        "JSON.GET", "annika:conscious_state", "$"
    )
    
    if state_json:
        state = json.loads(state_json)[0]
        
        # Count tasks by list
        task_lists = {
            "active_tasks": len(state.get("active_tasks", [])),
            "priority_tasks": len(state.get("priority_tasks", [])),
            "completed_tasks": len(state.get("completed_tasks", [])),
            "longterm_tasks": len(state.get("longterm_tasks", [])),
            "delegated_tasks": len(state.get("delegated_tasks", []))
        }
        
        total_tasks = sum(task_lists.values())
        
        print(f"\n📊 Total tasks in Redis: {total_tasks}")
        print("\nTask distribution:")
        for list_name, count in task_lists.items():
            if count > 0:
                print(f"  - {list_name}: {count}")
        
        # Check ID mappings
        print("\n🔗 Checking Planner ID mappings...")
        
        mapped_count = 0
        unmapped_count = 0
        
        # Check all tasks for external_id
        for list_name in ["active_tasks", "priority_tasks", "completed_tasks", 
                         "longterm_tasks", "delegated_tasks"]:
            tasks = state.get(list_name, [])
            for task in tasks:
                task_id = task.get("id")
                external_id = task.get("external_id")
                
                if task_id:
                    # Check if there's a Planner mapping
                    planner_id = r.get(f"annika:planner:id_map:{task_id}")
                    
                    if planner_id or external_id:
                        mapped_count += 1
                    else:
                        unmapped_count += 1
                        if unmapped_count <= 5:  # Show first 5 unmapped
                            print(
                                f"  ❌ Unmapped: {task.get('title', 'Untitled')}"
                            )
        
        print(f"\n📊 Mapping summary:")
        print(f"  ✅ Mapped to Planner: {mapped_count}")
        print(f"  ❌ Not mapped: {unmapped_count}")
        
        # Check for any orphaned mappings
        print("\n🔍 Checking for orphaned Planner mappings...")
        mapping_keys = r.keys("annika:planner:id_map:*")
        print(f"  Total mapping keys: {len(mapping_keys)}")
        
    else:
        print("❌ No conscious_state found in Redis")
        
except Exception as e:
    print(f"❌ Error reading conscious_state: {e}")

# Also check if Planner sync is configured
print("\n⚙️  Configuration:")
default_plan_id = r.get("annika:config:default_plan_id")
if default_plan_id:
    print(f"  ✅ Default plan ID configured: {default_plan_id[:8]}...")
else:
    print("  ❌ No default plan ID configured") 