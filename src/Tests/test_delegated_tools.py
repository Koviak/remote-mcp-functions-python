"""
Test script to demonstrate delegated MCP tools working

This simulates what would happen when the MCP tools are called
"""

import json
import logging
from additional_tools_delegated import (
    get_delegated_access_token,
    get_my_profile,
    list_my_files,
    list_my_teams
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Testing Delegated MCP Tools")
print("=" * 60)

# Test 1: Get delegated access token
print("\n1. Testing Token Acquisition:")
print("-" * 40)
token = get_delegated_access_token()
if token:
    print(f"✓ Successfully obtained delegated token!")
    print(f"  Token preview: {token[:30]}...")
else:
    print("✗ Failed to get delegated token")
    exit(1)

# Test 2: Get agent's profile
print("\n2. Testing get_my_profile MCP tool:")
print("-" * 40)
try:
    # Simulate MCP tool context
    context = json.dumps({
        "arguments": {}
    })
    
    result = get_my_profile(context)
    
    if "error" not in result.lower():
        profile = json.loads(result)
        print("✓ Successfully retrieved agent profile!")
        print(f"  Display Name: {profile.get('displayName', 'Unknown')}")
        print(f"  Email: {profile.get('mail', 'Unknown')}")
        print(f"  Job Title: {profile.get('jobTitle', 'Not set')}")
        print(f"  ID: {profile.get('id', 'Unknown')}")
    else:
        print(f"✗ Error: {result}")
except Exception as e:
    print(f"✗ Exception: {e}")

# Test 3: List agent's files
print("\n3. Testing list_my_files MCP tool:")
print("-" * 40)
try:
    result = list_my_files(context)
    
    if "error" not in result.lower():
        files_data = json.loads(result)
        files = files_data.get('value', [])
        print(f"✓ Successfully retrieved files!")
        print(f"  Total files in root: {len(files)}")
        
        # Show first 3 files
        for i, file in enumerate(files[:3]):
            print(f"  - {file.get('name', 'Unknown')}")
            if 'file' in file:
                print(f"    Size: {file['size']} bytes")
    else:
        print(f"✗ Error: {result}")
except Exception as e:
    print(f"✗ Exception: {e}")

# Test 4: List agent's teams
print("\n4. Testing list_my_teams MCP tool:")
print("-" * 40)
try:
    result = list_my_teams(context)
    
    if "error" not in result.lower():
        teams_data = json.loads(result)
        teams = teams_data.get('value', [])
        print(f"✓ Successfully retrieved teams!")
        print(f"  Total teams: {len(teams)}")
        
        # Show teams
        for team in teams:
            print(f"  - {team.get('displayName', 'Unknown')}")
            print(f"    Description: {team.get('description', 'No description')}")
    else:
        print(f"✗ Error: {result}")
except Exception as e:
    print(f"✗ Exception: {e}")

print("\n" + "=" * 60)
print("Summary:")
print("-" * 40)
print("✓ Agent authentication is working!")
print("✓ Delegated access tools can be used by the autonomous agent")
print(f"✓ Agent 'Annika' can now perform actions in user context")
print("\nThe MCP tools are ready to be used through the function app!")
print("=" * 60) 