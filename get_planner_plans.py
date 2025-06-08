#!/usr/bin/env python3
"""
Get MS Planner plans for the authenticated user.
This helps find the plan ID needed for sync configuration.
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
    print("Make sure you're running from the project root")
    sys.exit(1)


def get_planner_plans():
    """List all Planner plans accessible to the user."""
    print("=" * 60)
    print("Microsoft Planner Plans")
    print("=" * 60)
    
    # Get token
    print("\nAcquiring authentication token...")
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to acquire token")
        print("Please run test_auth_config.py first to verify setup")
        return
    
    print("✅ Token acquired")
    
    # Get plans
    print("\nFetching Planner plans...")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me/planner/plans",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            plans = response.json().get("value", [])
            
            if not plans:
                print("\n❌ No Planner plans found")
                print("\nTo create a plan:")
                print("1. Go to https://planner.cloud.microsoft")
                print("2. Create a new plan")
                print("3. Run this script again")
                return
            
            print(f"\n✅ Found {len(plans)} plan(s):\n")
            
            for i, plan in enumerate(plans, 1):
                print(f"{i}. Plan: {plan.get('title', 'Untitled')}")
                print(f"   ID: {plan['id']}")
                print(f"   Owner: {plan.get('owner', 'Unknown')}")
                
                # Try to get more details
                detail_response = requests.get(
                    f"https://graph.microsoft.com/v1.0/planner/plans/"
                    f"{plan['id']}/tasks",
                    headers=headers,
                    timeout=10
                )
                
                if detail_response.status_code == 200:
                    tasks = detail_response.json().get("value", [])
                    print(f"   Tasks: {len(tasks)}")
                print()
            
            # Show configuration instructions
            print("\n" + "=" * 60)
            print("Configuration Instructions:")
            print("=" * 60)
            print("\n1. Choose a plan ID from above")
            print("\n2. Add it to your local.settings.json:")
            print('   "DEFAULT_PLANNER_PLAN_ID": "<plan-id-here>"')
            print("\n3. Or set it as environment variable:")
            print("   $env:DEFAULT_PLANNER_PLAN_ID = '<plan-id-here>'")
            print("\n4. Restart the sync service")
            
            # Optionally store in Redis
            print("\n" + "-" * 60)
            print("Want to set a default plan now? (y/n): ", end="")
            choice = input().strip().lower()
            
            if choice == 'y':
                print(
                    "\nEnter the number of the plan (1-{}): ".format(
                        len(plans)
                    ), 
                    end=""
                )
                try:
                    plan_num = int(input().strip())
                    if 1 <= plan_num <= len(plans):
                        selected_plan = plans[plan_num - 1]
                        plan_id = selected_plan['id']
                        plan_title = selected_plan.get('title', 'Untitled')
                        
                        # Store in Redis
                        try:
                            import redis
                            r = redis.Redis(
                                host='localhost',
                                port=6379,
                                password='password',
                                decode_responses=True
                            )
                            r.set("annika:config:default_plan_id", plan_id)
                            print(f"\n✅ Set default plan to: {plan_title}")
                            print(f"   ID: {plan_id}")
                            print("\nThe sync service will now use this plan.")
                        except Exception as e:
                            print(f"\n⚠️  Could not save to Redis: {e}")
                            print(
                                f"Please set DEFAULT_PLANNER_PLAN_ID = "
                                f"{plan_id}"
                            )
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Invalid input")
            
        else:
            print(f"\n❌ Failed to get plans: {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Error fetching plans: {e}")


if __name__ == "__main__":
    get_planner_plans() 