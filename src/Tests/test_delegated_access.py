"""
Test script to verify delegated access (OBO) functionality

This script tests:
1. Environment variable configuration
2. App-only authentication (works with MCP tools)
3. Delegated access pattern (limitation with MCP triggers)
"""

import os
import json
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError

def test_environment_variables():
    """Test if all required environment variables are set"""
    print("=== Testing Environment Variables ===")
    
    required_vars = [
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET", 
        "AZURE_TENANT_ID",
        "DOWNSTREAM_API_SCOPE"
    ]
    
    all_set = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"✓ {var}: {'*' * 10} (set)")
        else:
            print(f"✗ {var}: NOT SET")
            all_set = False
    
    return all_set

def test_app_only_authentication():
    """Test app-only authentication (used by MCP tools)"""
    print("\n=== Testing App-Only Authentication ===")
    
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        print("✗ Missing required credentials for app-only auth")
        return False
    
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Try to get a token for Microsoft Graph
        token = credential.get_token("https://graph.microsoft.com/.default")
        print("✓ Successfully obtained app-only token")
        print(f"  Token expires at: {token.expires_on}")
        return True
        
    except ClientAuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_delegated_access_pattern():
    """Test delegated access (OBO) pattern - shows the limitation"""
    print("\n=== Testing Delegated Access (OBO) Pattern ===")
    
    # This simulates what would happen in an MCP trigger
    print("Simulating MCP Trigger Context:")
    user_token = os.environ.get("X_MS_TOKEN_AAD_ACCESS_TOKEN")
    
    if not user_token:
        print("✗ No user token available (expected with MCP triggers)")
        print("  MCP triggers cannot access HTTP request headers")
        print("  where the X-MS-TOKEN-AAD-ACCESS-TOKEN would be")
    
    # This shows how it would work with HTTP triggers
    print("\nHow it would work with HTTP triggers:")
    print("1. Enable built-in authentication in Azure App Service")
    print("2. User authenticates and Azure adds token to request headers")
    print("3. HTTP function accesses: "
          "req.headers.get('X-MS-TOKEN-AAD-ACCESS-TOKEN')")
    print("4. Use OnBehalfOfCredential to exchange user token for "
          "downstream API token")
    
    # Demonstrate the OBO setup (even though we can't use it with MCP)
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    scope = os.environ.get("DOWNSTREAM_API_SCOPE")
    
    if all([tenant_id, client_id, client_secret, scope]):
        print("\n✓ OBO configuration is set up correctly")
        print(f"  Would request scope: {scope}")
    else:
        print("\n✗ OBO configuration is incomplete")

def main():
    """Run all tests"""
    print("Delegated Access Test Suite")
    print("=" * 50)
    
    # Test 1: Environment variables
    env_ok = test_environment_variables()
    
    # Test 2: App-only auth (what MCP tools use)
    if env_ok:
        app_only_ok = test_app_only_authentication()
    else:
        print("\n⚠️  Skipping authentication tests due to missing "
              "environment variables")
        app_only_ok = False
    
    # Test 3: Delegated access pattern
    test_delegated_access_pattern()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("-" * 50)
    
    if app_only_ok:
        print("✓ App-only authentication is working")
        print("  - MCP tools will work with this authentication")
        print("  - HTTP endpoints can use this authentication")
    else:
        print("✗ App-only authentication is not working")
        print("  - Check your Azure AD app registration")
        print("  - Verify credentials in local.settings.json")
    
    print("\n⚠️  Delegated Access (OBO) Limitation:")
    print("  - MCP triggers CANNOT use delegated access")
    print("  - Only HTTP triggers can access user tokens")
    print("  - To use delegated access, create HTTP endpoints instead")

if __name__ == "__main__":
    # Load settings from local.settings.json if running standalone
    try:
        with open("local.settings.json", "r") as f:
            settings = json.load(f)
            for key, value in settings["Values"].items():
                if key.startswith("AZURE") or key == "DOWNSTREAM_API_SCOPE":
                    if value:  # Only set if not empty
                        os.environ[key] = value
    except Exception as e:
        print(f"Note: Could not load local.settings.json: {e}")
    
    main() 