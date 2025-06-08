#!/usr/bin/env python3
"""
Migrate tasks between MS Planner plans.
Enhanced version that shows all available plans.
"""
import sys
import requests
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
    import redis
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def get_all_plans():
    """Get all available MS Planner plans."""
    token = get_agent_token()
    if not token:
        print("❌ Failed to acquire token")
        return []
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/me/planner/plans",
        headers=headers,
        timeout=10
    )
    
    if response.status_code != 200:
        print("❌ Failed to get plans")
        return []
    
    return response.json().get("value", [])


def get_plan_tasks(plan_id):
    """Get all tasks in a plan."""
    token = get_agent_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        return response.json().get("value", [])
    return []


def migrate_task(task, to_plan_id):
    """Migrate a single task to a new plan."""
    token = get_agent_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Create new task
    new_task_data = {
        "planId": to_plan_id,
        "title": task.get("title", "Untitled"),
        "percentComplete": task.get("percentComplete", 0),
        "startDateTime": task.get("startDateTime"),
        "dueDateTime": task.get("dueDateTime"),
        "priority": task.get("priority", 5)
    }
    
    # Get task details
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
        return False, "Failed to create"
    
    new_task = create_response.json()
    new_task_id = new_task["id"]
    
    # Copy details if available
    if details_response.status_code == 200:
        details = details_response.json()
        etag = new_task.get("@odata.etag")
        
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
    
    # Update Redis mappings
    r = redis.Redis(
        host='localhost',
        port=6379,
        password='password',
        decode_responses=True
    )
    
    # Find Annika ID
    annika_id = r.get(f"annika:planner:id_map:{task_id}")
    if annika_id:
        # Update mapping
        r.set(f"annika:planner:id_map:{annika_id}", new_task_id)
        r.set(f"annika:planner:id_map:{new_task_id}", annika_id)
        r.delete(f"annika:planner:id_map:{task_id}")
    
    # Delete old task
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
        return True, "Created but couldn't delete old"
    
    return True, "Success"


def main():
    """Main function."""
    print("=" * 60)
    print("MS Planner Task Migration Tool")
    print("=" * 60)
    
    # Get all plans
    print("\n🔍 Fetching all MS Planner plans...")
    plans = get_all_plans()
    
    if not plans:
        print("❌ No plans found")
        return
    
    # Display plans with task counts
    print("\n📋 Available Plans:")
    plan_map = {}
    
    for i, plan in enumerate(plans, 1):
        plan_id = plan["id"]
        plan_title = plan["title"]
        
        # Get task count
        tasks = get_plan_tasks(plan_id)
        task_count = len(tasks)
        
        plan_map[i] = {
            "id": plan_id,
            "title": plan_title,
            "tasks": tasks
        }
        
        print(f"\n{i}. {plan_title}")
        print(f"   ID: {plan_id[:8]}...")
        print(f"   Tasks: {task_count}")
        
        # Show sample tasks
        if tasks:
            print("   Sample tasks:")
            for task in tasks[:3]:
                print(f"   - {task.get('title', 'Untitled')}")
            if task_count > 3:
                print(f"   ... and {task_count - 3} more")
    
    # Get source plan
    print("\n" + "-" * 40)
    try:
        source_num = int(input("\nSelect SOURCE plan (number): "))
        if source_num not in plan_map:
            print("❌ Invalid selection")
            return
    except ValueError:
        print("❌ Invalid input")
        return
    
    source_plan = plan_map[source_num]
    
    # Get destination plan
    try:
        dest_num = int(input("Select DESTINATION plan (number): "))
        if dest_num not in plan_map or dest_num == source_num:
            print("❌ Invalid selection")
            return
    except ValueError:
        print("❌ Invalid input")
        return
    
    dest_plan = plan_map[dest_num]
    
    # Confirm migration
    print("\n" + "=" * 60)
    print("Migration Summary:")
    print(f"FROM: {source_plan['title']} ({len(source_plan['tasks'])} tasks)")
    print(f"TO:   {dest_plan['title']}")
    print("\nThis will:")
    print("  1. Create copies of all tasks in the destination plan")
    print("  2. Update Redis ID mappings")
    print("  3. Delete the original tasks")
    
    confirm = input("\nProceed with migration? (yes/no): ").lower().strip()
    
    if confirm != 'yes':
        print("\n✅ Migration cancelled")
        return
    
    # Perform migration
    print("\n🚀 Starting migration...")
    
    migrated = 0
    failed = 0
    
    for i, task in enumerate(source_plan['tasks'], 1):
        title = task.get('title', 'Untitled')
        print(f"\n[{i}/{len(source_plan['tasks'])}] {title}")
        
        success, message = migrate_task(task, dest_plan['id'])
        
        if success:
            print(f"   ✅ {message}")
            migrated += 1
        else:
            print(f"   ❌ {message}")
            failed += 1
        
        # Rate limiting
        if i % 5 == 0:
            time.sleep(1)
    
    # Update default plan if migrating to The Bridge
    if "Bridge" in dest_plan['title'] or "Annika" == dest_plan['title']:
        r = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        r.set("annika:config:default_plan_id", dest_plan['id'])
        print(f"\n✅ Updated default plan to: {dest_plan['title']}")
    
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print(f"✅ Migrated: {migrated} tasks")
    print(f"❌ Failed: {failed} tasks")
    print("\n✨ Next steps:")
    print("  1. Restart the sync service")
    print("  2. New tasks will now sync to the destination plan")


if __name__ == "__main__":
    main() 