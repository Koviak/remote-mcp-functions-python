#!/usr/bin/env python3
"""
Check Planner permissions for the authenticated user.
Diagnoses why we're getting 403 errors.
"""
import sys
import requests
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_auth_manager import get_agent_token
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)


def check_planner_permissions():
    """Check detailed permissions for Planner access."""
    print("=" * 60)
    print("Planner Permissions Check")
    print("=" * 60)
    
    # Get token
    print("\nAcquiring token...")
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to acquire token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    plan_id = "fcoksV9zl0yf4y-UIs589mUAE1_w"
    
    # 1. Check user info
    print("\n1. User Information:")
    print("-" * 40)
    
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        user = response.json()
        print(f"✅ User: {user.get('displayName', 'Unknown')}")
        print(f"   Email: {user.get('mail') or user.get('userPrincipalName')}")
        print(f"   ID: {user.get('id')}")
        user_id = user.get('id')
    else:
        print(f"❌ Failed to get user info: {response.status_code}")
        return
    
    # 2. Check plan details
    print("\n2. Plan Details:")
    print("-" * 40)
    
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/planner/plans/{plan_id}",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        plan = response.json()
        print(f"✅ Plan: {plan.get('title', 'Unknown')}")
        print(f"   Owner: {plan.get('owner')}")
        container_type = plan.get('container', {}).get(
            '@odata.type', 'Unknown'
        )
        print(f"   Container: {container_type}")
        
        # Check if it's a group plan
        if 'group' in plan.get('container', {}).get('@odata.type', ''):
            group_id = plan.get('container', {}).get('containerId')
            print(f"   Group ID: {group_id}")
            
            # Check group membership
            print("\n3. Group Membership:")
            print("-" * 40)
            
            response = requests.get(
                f"https://graph.microsoft.com/v1.0/groups/{group_id}/members",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                members = response.json().get('value', [])
                member_ids = [m.get('id') for m in members]
                
                if user_id in member_ids:
                    print("✅ User IS a member of the group")
                else:
                    print("❌ User is NOT a member of the group!")
                    print("   This is likely why we're getting 403 errors")
                    
                print(f"\n   Group has {len(members)} members")
                for member in members[:5]:  # Show first 5
                    print(f"   - {member.get('displayName', 'Unknown')}")
            else:
                print(
                    f"⚠️  Could not check group membership: "
                    f"{response.status_code}"
                )
    else:
        print(f"❌ Failed to get plan details: {response.status_code}")
        print(f"   Error: {response.text}")
    
    # 4. Try to create a test task
    print("\n4. Test Task Creation:")
    print("-" * 40)
    
    test_task = {
        "planId": plan_id,
        "title": "Test Task - Permission Check"
    }
    
    response = requests.post(
        "https://graph.microsoft.com/v1.0/planner/tasks",
        headers={**headers, "Content-Type": "application/json"},
        json=test_task,
        timeout=10
    )
    
    if response.status_code == 201:
        print("✅ Successfully created test task!")
        task_id = response.json().get('id')
        
        # Clean up - delete test task
        etag = response.json().get('@odata.etag')
        del_response = requests.delete(
            f"https://graph.microsoft.com/v1.0/planner/tasks/{task_id}",
            headers={**headers, "If-Match": etag},
            timeout=10
        )
        if del_response.status_code == 204:
            print("   (Test task deleted)")
    else:
        print(f"❌ Failed to create task: {response.status_code}")
        error_detail = response.json()
        error_msg = error_detail.get('error', {}).get('message', 'Unknown')
        print(f"   Error: {error_msg}")
        
        # Check if it's a group membership issue
        if "You do not have the required permissions" in str(error_detail):
            print("\n⚠️  PERMISSION ISSUE DETECTED!")
            print(
                "   The user needs to be added to the group "
                "that owns this plan"
            )
    
    # 5. Check alternative: user's own plans
    print("\n5. Alternative Plans (owned by user):")
    print("-" * 40)
    
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/planner/plans",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        plans = response.json().get('value', [])
        user_plans = [p for p in plans if not p.get('container')]
        
        if user_plans:
            print(f"Found {len(user_plans)} personal plans:")
            for plan in user_plans:
                print(f"   - {plan.get('title')}: {plan.get('id')}")
        else:
            print("No personal plans found")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    
    print("\nThe 403 error is likely because:")
    print("1. The plan belongs to a Microsoft 365 group")
    print("2. The user is not a member of that group")
    print("\nSolutions:")
    print("1. Add the user to the group that owns the plan")
    print("2. Create a new personal plan for the user")
    print("3. Use a plan that the user already has access to")


if __name__ == "__main__":
    check_planner_permissions() 