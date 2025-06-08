#!/usr/bin/env python3
"""
Find available groups or create a new one for Planner.
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


def find_or_create_group():
    """Find available groups or create one."""
    print("=" * 60)
    print("Finding/Creating Group for Planner")
    print("=" * 60)
    
    # Get token
    print("\nAcquiring token...")
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to acquire token")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Check user's groups
    print("\n1. Checking user's groups...")
    print("-" * 40)
    
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/memberOf",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        groups = response.json().get('value', [])
        m365_groups = [
            g for g in groups 
            if g.get('@odata.type') == '#microsoft.graph.group'
            and g.get('groupTypes') and 'Unified' in g.get('groupTypes', [])
        ]
        
        if m365_groups:
            print(f"Found {len(m365_groups)} Microsoft 365 groups:")
            for group in m365_groups:
                print(f"   - {group.get('displayName')}: {group.get('id')}")
                
            # Use the first group
            group_id = m365_groups[0]['id']
            group_name = m365_groups[0]['displayName']
            print(f"\n✅ Using group: {group_name}")
            
            return create_plan_in_group(token, group_id)
        else:
            print("No Microsoft 365 groups found.")
    
    # 2. Try to create a new group (requires permissions)
    print("\n2. Attempting to create a new group...")
    print("-" * 40)
    
    group_data = {
        "displayName": "Annika AGI Team",
        "description": "Team for Annika AGI task management",
        "mailEnabled": True,
        "mailNickname": "annika-agi-team",
        "securityEnabled": False,
        "groupTypes": ["Unified"]
    }
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/groups",
        headers={**headers, "Content-Type": "application/json"},
        json=group_data,
        timeout=30
    )
    
    if response.status_code == 201:
        group = response.json()
        print(f"✅ Created new group: {group['displayName']}")
        print(f"   Group ID: {group['id']}")
        
        # Wait a moment for group to be ready
        import time
        print("   Waiting for group to be ready...")
        time.sleep(5)
        
        return create_plan_in_group(token, group['id'])
    else:
        print(f"❌ Failed to create group: {response.status_code}")
        error = response.json()
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown')}")
        
        # 3. Last resort - use the existing plan's group
        print("\n3. Checking existing plan's configuration...")
        print("-" * 40)
        
        # Get the problematic plan's details
        plan_id = "fcoksV9zl0yf4y-UIs589mUAE1_w"
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            plan = response.json()
            owner = plan.get('owner')
            print(f"Existing plan owner: {owner}")
            
            # Try to create a new plan with the same owner
            return create_plan_with_owner(token, owner)
        
    return None


def create_plan_in_group(token: str, group_id: str):
    """Create a plan in a specific group."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    plan_data = {
        "owner": group_id,
        "title": "Annika AGI Tasks"
    }
    
    print(f"\nCreating plan in group {group_id}...")
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/plans",
        headers=headers,
        json=plan_data,
        timeout=10
    )
    
    if response.status_code == 201:
        plan = response.json()
        plan_id = plan['id']
        
        print(f"✅ Successfully created plan: {plan['title']}")
        print(f"   Plan ID: {plan_id}")
        
        # Save configuration
        save_plan_config(plan_id)
        return plan_id
    else:
        print(f"❌ Failed to create plan: {response.status_code}")
        error = response.json()
        print(f"   Error: {error.get('error', {}).get('message', 'Unknown')}")
        return None


def create_plan_with_owner(token: str, owner_id: str):
    """Create a plan with specific owner."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    plan_data = {
        "owner": owner_id,
        "title": "Annika AGI Tasks - New"
    }
    
    print(f"\nCreating plan with owner {owner_id}...")
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/plans",
        headers=headers,
        json=plan_data,
        timeout=10
    )
    
    if response.status_code == 201:
        plan = response.json()
        plan_id = plan['id']
        
        print(f"✅ Successfully created plan: {plan['title']}")
        print(f"   Plan ID: {plan_id}")
        
        save_plan_config(plan_id)
        return plan_id
    else:
        print(f"❌ Failed to create plan: {response.status_code}")
        return None


def save_plan_config(plan_id: str):
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
        print("\nThe sync service will now use this plan.")
        print("Restart the services to sync your tasks!")
        
    except Exception as e:
        print(f"⚠️  Error saving configuration: {e}")
        print(f"\nManually set DEFAULT_PLANNER_PLAN_ID = {plan_id}")


if __name__ == "__main__":
    find_or_create_group() 