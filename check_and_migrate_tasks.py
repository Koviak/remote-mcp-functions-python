#!/usr/bin/env python3
"""
Check which MS Planner plans tasks are in and optionally migrate them.
This helps move tasks from Firefly to The Bridge.
"""
import sys
import requests
import json
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
    import redis
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

def get_all_tasks_by_plan():
    """Get all tasks organized by plan."""
    token = get_agent_token()
    if not token:
        print("❌ Failed to acquire token")
        return {}
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all plans
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/me/planner/plans",
        headers=headers,
        timeout=10
    )
    
    if response.status_code != 200:
        print("❌ Failed to get plans")
        return {}
    
    plans = response.json().get("value", [])
    tasks_by_plan = {}
    
    for plan in plans:
        plan_id = plan["id"]
        plan_title = plan["title"]
        
        # Get tasks for this plan
        task_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
            headers=headers,
            timeout=10
        )
        
        if task_response.status_code == 200:
            tasks = task_response.json().get("value", [])
            if tasks:
                tasks_by_plan[plan_title] = {
                    "plan_id": plan_id,
                    "tasks": tasks
                }
    
    return tasks_by_plan


def display_task_distribution(tasks_by_plan):
    """Display where tasks are located."""
    print("\n📊 Task Distribution by Plan:")
    print("=" * 60)
    
    total_tasks = 0
    
    for plan_name, plan_data in tasks_by_plan.items():
        task_count = len(plan_data["tasks"])
        total_tasks += task_count
        print(f"\n📁 {plan_name}")
        print(f"   Plan ID: {plan_data['plan_id'][:8]}...")
        print(f"   Tasks: {task_count}")
        
        # Show first few task titles
        for i, task in enumerate(plan_data["tasks"][:5]):
            print(f"   - {task.get('title', 'Untitled')}")
        
        if task_count > 5:
            print(f"   ... and {task_count - 5} more tasks")
    
    print(f"\n📊 Total tasks across all plans: {total_tasks}")
    return total_tasks


def migrate_task(task, from_plan_id, to_plan_id):
    """Migrate a task from one plan to another."""
    token = get_agent_token()
    if not token:
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 1. Create new task in target plan
    new_task_data = {
        "planId": to_plan_id,
        "title": task.get("title", "Untitled"),
        "percentComplete": task.get("percentComplete", 0),
        "startDateTime": task.get("startDateTime"),
        "dueDateTime": task.get("dueDateTime"),
        "priority": task.get("priority", 5)
    }
    
    # Get task details for description
    task_id = task["id"]
    details_response = requests.get(
        f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/details",
        headers=headers,
        timeout=10
    )
    
    # Create the new task
    create_response = requests.post(
        f"{GRAPH_API_ENDPOINT}/planner/tasks",
        headers=headers,
        json=new_task_data,
        timeout=10
    )
    
    if create_response.status_code != 201:
        print(f"   ❌ Failed to create task: {create_response.status_code}")
        return False
    
    new_task = create_response.json()
    new_task_id = new_task["id"]
    
    # 2. Copy task details if available
    if details_response.status_code == 200:
        details = details_response.json()
        etag = new_task.get("@odata.etag")
        
        # Update details
        details_update = {
            "description": details.get("description", ""),
            "checklist": details.get("checklist", {})
        }
        
        update_headers = headers.copy()
        update_headers["If-Match"] = etag
        
        requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{new_task_id}/details",
            headers=update_headers,
            json=details_update,
            timeout=10
        )
    
    # 3. Update Redis ID mapping
    r = redis.Redis(
        host='localhost',
        port=6379,
        password='password',
        decode_responses=True
    )
    
    # Get Annika ID from old mapping
    annika_id = r.get(f"annika:planner:id_map:{task_id}")
    if annika_id:
        # Update mapping to new Planner ID
        r.set(f"annika:planner:id_map:{annika_id}", new_task_id)
        r.set(f"annika:planner:id_map:{new_task_id}", annika_id)
        # Remove old mapping
        r.delete(f"annika:planner:id_map:{task_id}")
    
    # 4. Delete old task
    delete_headers = {
        "Authorization": f"Bearer {token}",
        "If-Match": task.get("@odata.etag")
    }
    
    delete_response = requests.delete(
        f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
        headers=delete_headers,
        timeout=10
    )
    
    if delete_response.status_code not in [204, 200]:
        print(f"   ⚠️  Created new task but failed to delete old one")
        return True
    
    return True


def main():
    """Main function."""
    print("=" * 60)
    print("MS Planner Task Distribution & Migration Tool")
    print("=" * 60)
    
    # Get all tasks by plan
    print("\n🔍 Fetching all tasks from MS Planner...")
    tasks_by_plan = get_all_tasks_by_plan()
    
    if not tasks_by_plan:
        print("❌ No tasks found or error fetching tasks")
        return
    
    # Display distribution
    total = display_task_distribution(tasks_by_plan)
    
    if total == 0:
        print("\n✅ No tasks to migrate")
        return
    
    # Check if tasks need migration
    firefly_tasks = tasks_by_plan.get("Annika_AGI_Tasks", {}).get("tasks", [])
    bridge_tasks = tasks_by_plan.get("Annika", {}).get("tasks", [])
    
    if firefly_tasks and "Annika" in tasks_by_plan:
        print("\n⚠️  Found tasks in Firefly that should be in The Bridge!")
        print(f"   Firefly (Annika_AGI_Tasks): {len(firefly_tasks)} tasks")
        print(f"   The Bridge (Annika): {len(bridge_tasks)} tasks")
        
        print("\nWould you like to migrate tasks from Firefly to The Bridge?")
        print("This will:")
        print("  1. Create copies in The Bridge plan")
        print("  2. Update Redis ID mappings")
        print("  3. Delete originals from Firefly")
        
        response = input("\nMigrate tasks? (yes/no): ").lower().strip()
        
        if response == 'yes':
            print("\n🚀 Starting migration...")
            
            source_plan_id = tasks_by_plan["Annika_AGI_Tasks"]["plan_id"]
            target_plan_id = tasks_by_plan["Annika"]["plan_id"]
            
            migrated = 0
            failed = 0
            
            for i, task in enumerate(firefly_tasks, 1):
                title = task.get("title", "Untitled")
                print(f"\n[{i}/{len(firefly_tasks)}] Migrating: {title}")
                
                if migrate_task(task, source_plan_id, target_plan_id):
                    print(f"   ✅ Successfully migrated")
                    migrated += 1
                else:
                    print(f"   ❌ Migration failed")
                    failed += 1
                
                # Small delay to avoid rate limiting
                if i % 5 == 0:
                    time.sleep(1)
            
            print("\n" + "=" * 60)
            print("Migration Complete!")
            print(f"✅ Migrated: {migrated} tasks")
            print(f"❌ Failed: {failed} tasks")
            print("\nRestart the sync service to continue syncing with The Bridge.")
        else:
            print("\n✅ No migration performed")
    else:
        print("\n✅ No migration needed - tasks appear to be in the correct plans")


if __name__ == "__main__":
    main() 