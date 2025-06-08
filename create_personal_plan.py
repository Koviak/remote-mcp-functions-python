#!/usr/bin/env python3
"""
Create a new personal Planner plan for Annika.
This ensures we have full permissions to create tasks.
"""
import sys
import requests
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
    import redis
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


def create_personal_plan():
    """Create a new personal plan with full permissions."""
    print("=" * 60)
    print("Creating Personal Planner Plan")
    print("=" * 60)
    
    # Get token
    print("\nAcquiring token...")
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to acquire token")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Create a new plan
    print("\nCreating new personal plan...")
    
    plan_title = f"Annika AGI Tasks - {datetime.now().strftime('%Y-%m-%d')}"
    
    plan_data = {
        "title": plan_title
    }
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/plans",
        headers=headers,
        json=plan_data,
        timeout=10
    )
    
    if response.status_code == 201:
        plan = response.json()
        plan_id = plan['id']
        
        print(f"✅ Successfully created plan: {plan_title}")
        print(f"   Plan ID: {plan_id}")
        
        # Test creating a task
        print("\nTesting task creation...")
        
        test_task = {
            "planId": plan_id,
            "title": "Welcome to Annika AGI Tasks!"
        }
        
        task_response = requests.post(
            "https://graph.microsoft.com/v1.0/planner/tasks",
            headers=headers,
            json=test_task,
            timeout=10
        )
        
        if task_response.status_code == 201:
            print("✅ Test task created successfully!")
            
            # Save the plan ID to Redis and settings
            print("\nSaving configuration...")
            
            try:
                # Save to Redis
                r = redis.Redis(
                    host='localhost',
                    port=6379,
                    password='password',
                    decode_responses=True
                )
                r.set("annika:config:default_plan_id", plan_id)
                print("✅ Saved to Redis")
                
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
                print(f"\nNew plan created: {plan_title}")
                print(f"Plan ID: {plan_id}")
                print("\nThe sync service will now use this plan.")
                print("Restart the services to sync your tasks!")
                
                return plan_id
                
            except Exception as e:
                print(f"⚠️  Error saving configuration: {e}")
                print(f"\nManually set DEFAULT_PLANNER_PLAN_ID = {plan_id}")
                return plan_id
        else:
            print(f"❌ Failed to create test task: {task_response.status_code}")
            print("But the plan was created successfully.")
            return plan_id
    else:
        print(f"❌ Failed to create plan: {response.status_code}")
        error = response.json()
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown')}")
        return None


if __name__ == "__main__":
    print("This will create a new personal Planner plan.")
    print("You'll have full permissions to create and manage tasks.\n")
    
    plan_id = create_personal_plan()
    
    if not plan_id:
        print("\n❌ Failed to create plan.")
        print("Please check your permissions and try again.") 