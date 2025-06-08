#!/usr/bin/env python3
"""
Set up Annika AGI plan in The Bridge group.
Verify membership and create/configure the plan.
"""
import sys
import requests
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
    import redis
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


# The Bridge group ID from earlier scan
THE_BRIDGE_GROUP_ID = "1bad3cda-4564-4a81-8919-f42b59defc3a"


def setup_the_bridge_plan():
    """Set up Annika AGI plan in The Bridge group."""
    print("=" * 60)
    print("Setting up Annika AGI in The Bridge")
    print("=" * 60)
    
    # Get token
    print("\nAcquiring token...")
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to acquire token")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Verify user is now a member of The Bridge
    print("\n1. Verifying membership in The Bridge...")
    print("-" * 40)
    
    # Get current user info
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        user = response.json()
        user_id = user.get('id')
        user_name = user.get('displayName', 'Unknown')
        print(f"User: {user_name}")
    else:
        print("❌ Failed to get user info")
        return None
    
    # Check The Bridge membership
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/groups/"
        f"{THE_BRIDGE_GROUP_ID}/members",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        members = response.json().get('value', [])
        member_ids = [m.get('id') for m in members]
        
        if user_id in member_ids:
            print("✅ Confirmed: Annika IS a member of The Bridge!")
        else:
            print("❌ Annika is NOT yet a member of The Bridge")
            print("Please add her to the group first")
            return None
    else:
        print(f"❌ Could not check membership: {response.status_code}")
        return None
    
    # 2. Check for existing plans in The Bridge
    print("\n2. Checking existing plans in The Bridge...")
    print("-" * 40)
    
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/groups/"
        f"{THE_BRIDGE_GROUP_ID}/planner/plans",
        headers=headers,
        timeout=10
    )
    
    existing_annika_plan = None
    
    if response.status_code == 200:
        plans = response.json().get('value', [])
        print(f"Found {len(plans)} existing plans in The Bridge:")
        
        for plan in plans:
            title = plan.get('title', 'Untitled')
            plan_id = plan.get('id')
            print(f"   - {title}: {plan_id}")
            
            # Check if we already have an Annika plan
            if 'Annika' in title:
                existing_annika_plan = plan
        
        if existing_annika_plan:
            print(
                f"\n✅ Found existing Annika plan: "
                f"{existing_annika_plan['title']}"
            )
            plan_id = existing_annika_plan['id']
            
            # Test we can create tasks
            if test_task_creation(token, plan_id):
                save_plan_config(plan_id, existing_annika_plan['title'])
                return plan_id
            else:
                print(
                    "⚠️  Cannot create tasks in existing plan, "
                    "creating new one..."
                )
    
    # 3. Create new plan in The Bridge
    print("\n3. Creating new plan in The Bridge...")
    print("-" * 40)
    
    plan_data = {
        "owner": THE_BRIDGE_GROUP_ID,
        "title": "Annika AGI Tasks"
    }
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/plans",
        headers={**headers, "Content-Type": "application/json"},
        json=plan_data,
        timeout=10
    )
    
    if response.status_code == 201:
        plan = response.json()
        plan_id = plan['id']
        
        print(f"✅ Successfully created plan: {plan['title']}")
        print(f"   Plan ID: {plan_id}")
        
        # Test task creation
        if test_task_creation(token, plan_id):
            save_plan_config(plan_id, plan['title'])
            return plan_id
        else:
            print("❌ Cannot create tasks in new plan")
            return None
    else:
        print(f"❌ Failed to create plan: {response.status_code}")
        error = response.json()
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown')}")
        return None


def test_task_creation(token: str, plan_id: str) -> bool:
    """Test if we can create tasks in the plan."""
    print("\nTesting task creation in plan...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    test_task = {
        "planId": plan_id,
        "title": "Test - Can be deleted"
    }
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/tasks",
        headers=headers,
        json=test_task,
        timeout=10
    )
    
    if response.status_code == 201:
        print("✅ Task creation successful!")
        
        # Clean up test task
        task = response.json()
        task_id = task['id']
        etag = task.get('@odata.etag')
        
        del_response = requests.delete(
            f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}",
            headers={**headers, "If-Match": etag},
            timeout=10
        )
        
        if del_response.status_code == 204:
            print("   (Test task cleaned up)")
        
        return True
    else:
        print(f"❌ Task creation failed: {response.status_code}")
        return False


def save_plan_config(plan_id: str, plan_title: str):
    """Save the plan ID to configuration."""
    try:
        # Save to Redis
        r = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        r.set("annika:config:default_plan_id", plan_id)
        print("\n✅ Saved to Redis")
        
        # Update local.settings.json
        settings_path = Path("src/local.settings.json")
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            
            settings['Values']['DEFAULT_PLANNER_PLAN_ID'] = plan_id
            
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            
            print("✅ Updated local.settings.json")
        
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nPlan: {plan_title}")
        print(f"Plan ID: {plan_id}")
        print("Group: The Bridge")
        print("\nThe sync service will now use The Bridge plan.")
        print("Restart the services to sync your tasks!")
        
    except Exception as e:
        print(f"⚠️  Error saving configuration: {e}")
        print(f"\nManually set DEFAULT_PLANNER_PLAN_ID = {plan_id}")


if __name__ == "__main__":
    print("This will set up Annika AGI in The Bridge group.")
    print("Making sure Annika has access...\n")
    
    plan_id = setup_the_bridge_plan()
    
    if not plan_id:
        print("\n❌ Setup failed.")
        print("Please ensure Annika is added to The Bridge group.") 