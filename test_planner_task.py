import requests
import os
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential

# Load environment variables
load_dotenv()

# Microsoft Graph API endpoint
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def get_access_token():
    """Get access token for Microsoft Graph API"""
    tenant_id = os.environ.get("TENANT_ID")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        print("❌ Missing Azure AD credentials in environment variables")
        return None
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    try:
        token = credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    except Exception as e:
        print(f"❌ Failed to get access token: {e}")
        return None


def test_planner_access():
    """Test Planner API access and diagnose issues"""
    print("Testing Planner API Access")
    print("=" * 50)
    
    token = get_access_token()
    if not token:
        return
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Step 1: List groups to find one with Planner
    print("\n1. Finding groups with Planner...")
    filter_query = "groupTypes/any(c:c eq 'Unified')"
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/groups?$filter={filter_query}",
        headers=headers,
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to list groups: {response.status_code}")
        print(f"   {response.text}")
        return
    
    groups = response.json().get("value", [])
    print(f"✅ Found {len(groups)} Microsoft 365 groups")
    
    # Step 2: Find a group with Planner plans
    plan_found = False
    for group in groups[:5]:  # Check first 5 groups
        group_id = group["id"]
        group_name = group["displayName"]
        
        print(f"\n2. Checking group '{group_name}' for plans...")
        plans_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
            headers=headers
        )
        
        if plans_response.status_code == 200:
            plans = plans_response.json().get("value", [])
            if plans:
                print(f"✅ Found {len(plans)} plans in group '{group_name}'")
                plan_found = True
                
                # Step 3: Get tasks from the first plan
                plan = plans[0]
                plan_id = plan["id"]
                plan_title = plan["title"]
                print(f"\n3. Getting tasks from plan '{plan_title}'...")
                
                tasks_response = requests.get(
                    f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                    headers=headers
                )
                
                if tasks_response.status_code == 200:
                    tasks = tasks_response.json().get("value", [])
                    print(f"✅ Found {len(tasks)} tasks in plan")
                    
                    if tasks:
                        # Step 4: Test getting a specific task
                        task = tasks[0]
                        task_id = task["id"]
                        task_title = task["title"]
                        print(f"\n4. Testing get_task for '{task_title}' (ID: {task_id})...")
                        
                        # Test via HTTP endpoint
                        http_response = requests.get(
                            f"http://localhost:7071/api/tasks/{task_id}",
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if http_response.status_code == 200:
                            print("✅ Successfully retrieved task via HTTP endpoint")
                            print(f"   Response: {http_response.json()}")
                        else:
                            print(f"❌ HTTP endpoint failed: {http_response.status_code}")
                            print(f"   Response: {http_response.text}")
                        
                        # Test direct Graph API call
                        direct_response = requests.get(
                            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
                            headers=headers
                        )
                        
                        if direct_response.status_code == 200:
                            print("\n✅ Direct Graph API call succeeded")
                            task_data = direct_response.json()
                            print(f"   Task Title: {task_data.get('title')}")
                            print(f"   Plan ID: {task_data.get('planId')}")
                            print(f"   Bucket ID: {task_data.get('bucketId')}")
                        else:
                            print(f"\n❌ Direct Graph API call failed: {direct_response.status_code}")
                            print(f"   Response: {direct_response.text}")
                    else:
                        print("⚠️  No tasks found in plan to test")
                else:
                    print(f"❌ Failed to get tasks: {tasks_response.status_code}")
                
                break  # Found a plan, stop searching
    
    if not plan_found:
        print("\n⚠️  No Planner plans found in the checked groups")
        print("   You may need to create a plan first or check more groups")
    
    # Step 5: Test with the problematic task ID
    print("\n5. Testing the problematic task ID...")
    problem_task_id = "AAGaxfPn4Uej46oplY26sjYAKsFq"
    
    direct_response = requests.get(
        f"{GRAPH_API_ENDPOINT}/planner/tasks/{problem_task_id}",
        headers=headers
    )
    
    if direct_response.status_code == 200:
        print(f"✅ Task {problem_task_id} exists and is accessible")
    elif direct_response.status_code == 404:
        print(f"❌ Task {problem_task_id} not found (404)")
        print("   Possible reasons:")
        print("   - Task doesn't exist in your tenant")
        print("   - Task was deleted")
        print("   - Task belongs to a different organization")
        print("   - Using application permissions (delegated required)")
    elif direct_response.status_code == 403:
        print(f"❌ Access denied to task {problem_task_id} (403)")
        print("   The app doesn't have permission to access this task")
    else:
        print(f"❌ Unexpected error: {direct_response.status_code}")
        print(f"   Response: {direct_response.text}")

def check_permissions():
    """Check what permissions the app has"""
    print("\n\nChecking App Permissions")
    print("=" * 50)
    
    print("\n⚠️  Important Notes about Planner API:")
    print("1. Planner APIs only support DELEGATED permissions")
    print("2. Application permissions are NOT supported")
    print("3. You need a signed-in user context to access tasks")
    print("4. The user must have access to the plan/task")
    print("\n📋 Required delegated permissions:")
    print("   - Tasks.Read (minimum for reading)")
    print("   - Tasks.ReadWrite (for full access)")
    print("   - Group.Read.All or Group.ReadWrite.All (for group operations)")
    
    print("\n🔧 Current setup uses application permissions which won't work!")
    print("   Consider implementing delegated auth flow for Planner access")

if __name__ == "__main__":
    test_planner_access()
    check_permissions() 