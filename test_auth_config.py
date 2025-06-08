#!/usr/bin/env python3
"""
Test authentication configuration for Planner sync.
Run this to verify your auth setup before starting services.
"""
import os
import sys
import traceback
from pathlib import Path

# Add src to path before importing from it
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Now we can import from src
try:
    from agent_auth_manager import get_agent_token
    import requests
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root")
    sys.exit(1)


def test_auth_config():
    """Test authentication configuration."""
    print("=" * 60)
    print("Authentication Configuration Test")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Checking Environment Variables:")
    print("-" * 40)
    
    required_vars = {
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID"),
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID"),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET"),
        "AGENT_USER_NAME": os.getenv("AGENT_USER_NAME"),
        "AGENT_PASSWORD": os.getenv("AGENT_PASSWORD"),
    }
    
    missing = []
    for var, value in required_vars.items():
        if value:
            if "PASSWORD" in var or "SECRET" in var:
                print(f"✅ {var}: {'*' * 10} (set)")
            else:
                print(f"✅ {var}: {value[:20]}...")
        else:
            print(f"❌ {var}: NOT SET")
            missing.append(var)
    
    if missing:
        print("\n❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease set these in your local.settings.json")
        return False
    
    # Try to acquire token
    print("\n2. Testing Token Acquisition:")
    print("-" * 40)
    
    try:
        print("Attempting to acquire token...")
        token = get_agent_token()
        
        if token:
            print("✅ Successfully acquired token!")
            print(f"   Token preview: {token[:30]}...")
            
            # Test the token
            print("\n3. Testing Token with Microsoft Graph:")
            print("-" * 40)
            
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                print("✅ Token is valid!")
                print(
                    f"   User: {user_data.get('displayName', 'Unknown')}"
                )
                email = (user_data.get('mail') or 
                         user_data.get('userPrincipalName'))
                print(f"   Email: {email}")
                print(f"   ID: {user_data.get('id')}")
                
                # Test Planner access
                print("\n4. Testing Planner Access:")
                print("-" * 40)
                
                response = requests.get(
                    "https://graph.microsoft.com/v1.0/me/planner/plans",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    plans = response.json().get("value", [])
                    print(
                        f"✅ Can access Planner! Found {len(plans)} plans"
                    )
                    if plans:
                        title = plans[0].get('title', 'Unknown')
                        print(f"   First plan: {title}")
                else:
                    print(
                        f"❌ Cannot access Planner: {response.status_code}"
                    )
                    print(f"   Error: {response.text}")
                
                return True
            else:
                print(
                    f"❌ Token validation failed: {response.status_code}"
                )
                print(f"   Error: {response.text}")
                
        else:
            print("❌ Failed to acquire token")
            print("\nPossible issues:")
            print("1. Check AGENT_USER_NAME and AGENT_PASSWORD are correct")
            print(
                "2. Ensure 'Allow public client flows' is enabled "
                "in Azure AD app"
            )
            print("3. Verify user has necessary permissions")
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        traceback.print_exc()
    
    return False


if __name__ == "__main__":
    print("This will test your authentication configuration.\n")
    
    if test_auth_config():
        print("\n✅ Authentication is properly configured!")
        print("You should be able to run the sync service now.")
    else:
        print("\n❌ Authentication configuration has issues.")
        print(
            "Please fix the issues above before running the sync service."
        ) 