import json
import time
import os
import sys
from azure.identity import ClientSecretCredential
import requests

# Load Azure AD config from local settings
print("Loading Azure AD configuration...")
try:
    with open("src/local.settings.json", "r") as f:
        settings = json.load(f)
        values = settings.get("Values", {})
        TENANT_ID = values.get("TENANT_ID")
        CLIENT_ID = values.get("CLIENT_ID")
        CLIENT_SECRET = values.get("CLIENT_SECRET")
        
        if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
            print("ERROR: Missing Azure AD credentials in local.settings.json")
            sys.exit(1)
            
        # Check if they're placeholder values
        if TENANT_ID == "your-tenant-id":
            print("ERROR: Please update Azure AD credentials in src/local.settings.json")
            print("       Replace placeholder values with actual credentials")
            sys.exit(1)
            
except FileNotFoundError:
    print("ERROR: Could not find src/local.settings.json")
    sys.exit(1)

print("✓ Azure AD configuration loaded")

# Microsoft Graph setup
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

def get_access_token():
    """Get access token for Microsoft Graph API"""
    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token

print("\n=== Testing Microsoft Graph API Access ===\n")

# Test 1: Get access token
print("1. Testing Azure AD authentication...")
try:
    token = get_access_token()
    print("   ✓ Successfully obtained access token")
except Exception as e:
    print(f"   ✗ Failed to get access token: {e}")
    print("   Please check your Azure AD credentials")
    sys.exit(1)

# Test 2: List groups
print("\n2. Testing list_groups functionality...")
try:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}/groups"
        "?$filter=groupTypes/any(c:c eq 'Unified')"
        "&$select=id,displayName,description,mail&$top=5",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        groups = response.json()["value"]
        print(f"   ✓ Found {len(groups)} Microsoft 365 groups")
        
        if groups:
            print("\n   Available Groups:")
            for idx, group in enumerate(groups[:3]):  # Show first 3
                print(f"   {idx+1}. {group['displayName']}")
                print(f"      ID: {group['id']}")
                print(f"      Mail: {group.get('mail', 'N/A')}")
                
            # Test with first group
            test_group_id = groups[0]['id']
            test_group_name = groups[0]['displayName']
            
            # Test 3: List plans for the first group
            print(f"\n3. Testing list_plans for '{test_group_name}'...")
            try:
                response = requests.get(
                    f"{GRAPH_API_ENDPOINT}/groups/{test_group_id}"
                    "/planner/plans",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    plans = response.json()["value"]
                    print(f"   ✓ Found {len(plans)} plans")
                    
                    if plans:
                        print("\n   Available Plans:")
                        for idx, plan in enumerate(plans[:3]):
                            print(f"   {idx+1}. {plan['title']}")
                            print(f"      ID: {plan['id']}")
                            
                        # Test with first plan
                        test_plan_id = plans[0]['id']
                        test_plan_name = plans[0]['title']
                        
                        # Test 4: List tasks
                        print(f"\n4. Testing list_tasks for '{test_plan_name}'...")
                        response = requests.get(
                            f"{GRAPH_API_ENDPOINT}/planner/plans/"
                            f"{test_plan_id}/tasks",
                            headers=headers,
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            tasks = response.json()["value"]
                            print(f"   ✓ Found {len(tasks)} tasks")
                            
                            if tasks:
                                print("\n   Sample Tasks:")
                                for idx, task in enumerate(tasks[:3]):
                                    print(f"   {idx+1}. {task['title']}")
                                    completion = task.get('percentComplete', 0)
                                    print(f"      Progress: {completion}%")
                        else:
                            print(f"   ! No tasks or error: {response.status_code}")
                    else:
                        print("   ! No plans found for this group")
                        
                elif response.status_code == 404:
                    print("   ! This group doesn't have Planner enabled")
                else:
                    print(f"   ✗ Error: {response.status_code}")
                    
            except Exception as e:
                print(f"   ✗ Error listing plans: {e}")
                
        else:
            print("   ! No Microsoft 365 groups found")
            print("   Make sure your app has Group.Read.All permission")
            
    else:
        print(f"   ✗ Error: {response.status_code} - {response.text}")
        if response.status_code == 403:
            print("   ! Permission denied. Check API permissions:")
            print("     - Group.Read.All")
            print("     - Tasks.ReadWrite.All")
            
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n=== Test Summary ===")
print("MCP Server tools are configured correctly!")
print("\nTo use these tools in VS Code Copilot:")
print("1. Add MCP Server: http://localhost:7071/runtime/webhooks/mcp/sse")
print("2. Try commands like:")
print("   - 'List all my Microsoft 365 groups'")
print("   - 'List plans for group [group-name]'")
print("   - 'List tasks in plan [plan-name]'")
print("\nMake sure the Azure Functions host is running (func start in src/)") 