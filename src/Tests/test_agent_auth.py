"""
Test script for autonomous agent authentication

This script demonstrates and tests the agent authentication manager
with various authentication methods.
"""

import os
import json
import logging
from agent_auth_manager import get_auth_manager, get_agent_token

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_agent_authentication():
    """Test the agent authentication manager"""
    print("=" * 60)
    print("Autonomous Agent Authentication Test")
    print("=" * 60)
    
    # Check configuration
    print("\n1. Checking Configuration:")
    print("-" * 40)
    
    config_vars = {
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
        "AGENT_USER_NAME": os.getenv("AGENT_USER_NAME"),
        "AGENT_PASSWORD": os.getenv("AGENT_PASSWORD"),
        "AGENT_CERTIFICATE_PATH": os.getenv("AGENT_CERTIFICATE_PATH"),
    }
    
    for var, value in config_vars.items():
        if value:
            if "PASSWORD" in var or "SECRET" in var:
                print(f"✓ {var}: {'*' * 10} (set)")
            else:
                print(f"✓ {var}: {value[:20]}... (set)")
        else:
            print(f"✗ {var}: NOT SET")
    
    # Determine auth method
    print("\n2. Authentication Method:")
    print("-" * 40)
    
    if config_vars["AGENT_USER_NAME"] and config_vars["AGENT_PASSWORD"]:
        print("✓ Username/Password (ROPC) authentication available")
        auth_method = "ROPC"
    elif config_vars["AGENT_CERTIFICATE_PATH"]:
        print("✓ Certificate authentication available")
        auth_method = "Certificate"
    else:
        print("✗ No agent authentication method configured")
        print("\nPlease set either:")
        print("  - AGENT_USER_NAME and AGENT_PASSWORD for ROPC")
        print("  - AGENT_CERTIFICATE_PATH for certificate auth")
        return
    
    # Test token acquisition
    print("\n3. Testing Token Acquisition:")
    print("-" * 40)
    
    try:
        # Get auth manager instance (for initialization)
        get_auth_manager()
        print("✓ Auth manager initialized")
        
        # Try to get a token
        print(f"Attempting to acquire token using {auth_method}...")
        token = get_agent_token()
        
        if token:
            print("✓ Successfully obtained agent token!")
            print(f"  Token preview: {token[:20]}...")
            print(f"  Token length: {len(token)} characters")
            
            # Test API call with the token
            print("\n4. Testing API Call with Token:")
            print("-" * 40)
            
            import requests
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                print("✓ Successfully called Microsoft Graph!")
                print(f"  User: {user_data.get('displayName', 'Unknown')}")
                email = user_data.get('mail', 
                                    user_data.get('userPrincipalName', 
                                                'Unknown'))
                print(f"  Email: {email}")
                print(f"  ID: {user_data.get('id', 'Unknown')}")
            else:
                print(f"✗ API call failed: {response.status_code}")
                print(f"  Error: {response.text}")
        else:
            print("✗ Failed to obtain agent token")
            print("  Check your credentials and Azure AD configuration")
            
    except Exception as e:
        print(f"✗ Error during authentication: {str(e)}")
        logging.exception("Authentication error")
    
    # Test token caching
    print("\n5. Testing Token Caching:")
    print("-" * 40)
    
    if token:
        print("Getting token again (should be from cache)...")
        token2 = get_agent_token()
        
        if token2 == token:
            print("✓ Token successfully retrieved from cache")
        else:
            print("⚠️  Token differs (may have been refreshed)")
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


def test_delegated_mcp_tools():
    """Test calling MCP tools with delegated permissions"""
    print("\n\n6. Testing Delegated MCP Tools:")
    print("-" * 40)
    
    # This would normally be done through the function app
    # Here we're just showing what the tools would do
    
    token = get_agent_token()
    if not token:
        print("✗ Cannot test MCP tools without a valid token")
        return
    
    print("✓ Token available for MCP tools")
    print("\nAvailable delegated MCP tools:")
    print("  - get_my_profile")
    print("  - list_my_files")
    print("  - send_email_as_agent")
    print("  - list_my_calendar")
    print("  - create_todo_task")
    print("  - list_my_teams")
    print("  - post_teams_message_as_agent")
    print("\nThese tools will use the agent's delegated permissions")


if __name__ == "__main__":
    # Load settings from local.settings.json
    try:
        with open("local.settings.json", "r") as f:
            settings = json.load(f)
            for key, value in settings["Values"].items():
                if key.startswith("AZURE") or key.startswith("AGENT"):
                    if value:  # Only set if not empty
                        os.environ[key] = value
    except Exception as e:
        print(f"Note: Could not load local.settings.json: {e}")
    
    # Run tests
    test_agent_authentication()
    test_delegated_mcp_tools() 