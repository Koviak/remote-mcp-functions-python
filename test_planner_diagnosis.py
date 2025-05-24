import json
import requests
import sys
from azure.identity import ClientSecretCredential

# Load Azure AD config
print("=== Microsoft Planner Diagnostic Test ===\n")

try:
    with open("src/local.settings.json", "r") as f:
        settings = json.load(f)
        values = settings.get("Values", {})
        TENANT_ID = values.get("TENANT_ID")
        CLIENT_ID = values.get("CLIENT_ID")
        CLIENT_SECRET = values.get("CLIENT_SECRET")
except FileNotFoundError:
    print("ERROR: Could not find src/local.settings.json")
    sys.exit(1)

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

def test_api_call(url, description, headers):
    """Test an API call and return detailed results"""
    print(f"Testing: {description}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Error Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Exception: {e}")
        return None

# Get access token
print("1. Getting access token...")
try:
    token = get_access_token()
    print("✓ Successfully obtained access token\n")
except Exception as e:
    print(f"✗ Failed to get access token: {e}")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Test 1: List all groups
print("2. Testing group access...")
groups_url = f"{GRAPH_API_ENDPOINT}/groups?$filter=groupTypes/any(c:c eq 'Unified')&$select=id,displayName,description,mail"
groups_data = test_api_call(groups_url, "List Microsoft 365 groups", headers)

if not groups_data or not groups_data.get("value"):
    print("✗ No groups found or error occurred")
    sys.exit(1)

groups = groups_data["value"]
print(f"✓ Found {len(groups)} groups\n")

# Test 2: Check each group for plans
print("3. Testing plan access for each group...")
for i, group in enumerate(groups[:3], 1):  # Test first 3 groups
    group_id = group["id"]
    group_name = group["displayName"]
    
    print(f"\n--- Group {i}: {group_name} ---")
    print(f"Group ID: {group_id}")
    
    # Method 1: Try the standard plans endpoint
    plans_url = f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans"
    plans_data = test_api_call(plans_url, "Get plans via /groups/{id}/planner/plans", headers)
    
    if plans_data:
        plans = plans_data.get("value", [])
        print(f"✓ Found {len(plans)} plans using standard endpoint")
        if plans:
            for plan in plans:
                print(f"  - Plan: {plan.get('title')} (ID: {plan.get('id')})")
    else:
        print("✗ Standard endpoint failed or returned no data")
    
    # Method 2: Try direct planner endpoint
    print("\nTrying alternative endpoint...")
    alt_plans_url = f"{GRAPH_API_ENDPOINT}/planner/plans?$filter=owner eq '{group_id}'"
    alt_plans_data = test_api_call(alt_plans_url, "Get plans via /planner/plans filter", headers)
    
    if alt_plans_data:
        alt_plans = alt_plans_data.get("value", [])
        print(f"✓ Found {len(alt_plans)} plans using alternative endpoint")
        if alt_plans:
            for plan in alt_plans:
                print(f"  - Plan: {plan.get('title')} (ID: {plan.get('id')})")
    
    # Method 3: Check group details
    print("\nChecking group capabilities...")
    group_url = f"{GRAPH_API_ENDPOINT}/groups/{group_id}?$select=id,displayName,resourceProvisioningOptions,groupTypes"
    group_details = test_api_call(group_url, "Get group details", headers)
    
    if group_details:
        provisioning = group_details.get("resourceProvisioningOptions", [])
        group_types = group_details.get("groupTypes", [])
        print(f"  Group Types: {group_types}")
        print(f"  Resource Provisioning: {provisioning}")
        
        if "Team" in provisioning:
            print("  ✓ This group has Teams enabled")
        else:
            print("  ! This group may not have Teams/Planner enabled")

# Test 3: Check permissions
print("\n\n4. Testing permission levels...")

# Test if we can read all plans (requires broad permissions)
print("Testing global plan access...")
all_plans_url = f"{GRAPH_API_ENDPOINT}/planner/plans?$top=5"
all_plans_data = test_api_call(all_plans_url, "Get all plans", headers)

if all_plans_data:
    all_plans = all_plans_data.get("value", [])
    print(f"✓ Can access {len(all_plans)} plans globally")
    if all_plans:
        print("Sample plans found:")
        for plan in all_plans:
            print(f"  - {plan.get('title')} (Owner: {plan.get('owner')})")
else:
    print("✗ Cannot access plans globally - may need additional permissions")

# Test 4: Try creating a plan to test write permissions
print("\n\n5. Testing plan creation capability...")
test_group = groups[0]  # Use first group for test
test_group_id = test_group["id"]
test_group_name = test_group["displayName"]

print(f"Attempting to create test plan in group: {test_group_name}")

create_plan_url = f"{GRAPH_API_ENDPOINT}/planner/plans"
test_plan_data = {
    "owner": test_group_id,
    "title": f"Test Plan - {test_group_name} - Diagnostic"
}

try:
    response = requests.post(
        create_plan_url,
        headers=headers,
        json=test_plan_data,
        timeout=10
    )
    
    print(f"Create plan status: {response.status_code}")
    
    if response.status_code == 201:
        created_plan = response.json()
        plan_id = created_plan["id"]
        print(f"✓ Successfully created test plan: {plan_id}")
        
        # Now try to list plans again
        print("\nRe-testing plan listing after creation...")
        plans_url = f"{GRAPH_API_ENDPOINT}/groups/{test_group_id}/planner/plans"
        new_plans_data = test_api_call(plans_url, "List plans after creation", headers)
        
        if new_plans_data:
            new_plans = new_plans_data.get("value", [])
            print(f"✓ Now found {len(new_plans)} plans in the group")
            for plan in new_plans:
                print(f"  - {plan.get('title')} (ID: {plan.get('id')})")
        
        # Clean up - delete the test plan
        print(f"\nCleaning up test plan {plan_id}...")
        delete_url = f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}"
        delete_response = requests.delete(delete_url, headers=headers, timeout=10)
        print(f"Delete status: {delete_response.status_code}")
        
    else:
        print(f"✗ Failed to create plan: {response.text}")
        if response.status_code == 403:
            print("  ! Permission denied - check API permissions")
        elif response.status_code == 400:
            print("  ! Bad request - group may not support Planner")
            
except Exception as e:
    print(f"✗ Exception during plan creation: {e}")

print("\n\n=== DIAGNOSIS SUMMARY ===")
print("If no plans were found:")
print("1. Groups might not have any Planner plans created yet")
print("2. Groups might not have Planner/Teams enabled")
print("3. App permissions might be insufficient")
print("4. Try creating a plan manually in Microsoft Teams/Planner first")
print("\nRequired permissions:")
print("- Group.Read.All (to read groups)")
print("- Tasks.ReadWrite.All (to read/write plans and tasks)") 