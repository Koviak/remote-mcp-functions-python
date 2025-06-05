"""
Get Annika's Azure AD User ID

Run this script to find the correct AGENT_USER_ID for your .env file
"""

import requests
from agent_auth_manager import get_agent_token


def get_annika_user_id():
    """Get the Azure AD user ID for Annika"""
    
    # Get token using Annika's credentials
    token = get_agent_token()
    
    if not token:
        print("❌ Failed to authenticate. Check your credentials.")
        return None
    
    # Get user profile
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        user = response.json()
        print("✅ Found Annika's user information:")
        print(f"   Name: {user.get('displayName')}")
        print(f"   Email: {user.get('mail') or user.get('userPrincipalName')}")
        print(f"   User ID: {user.get('id')}")
        print("\n📝 Add this to your .env file:")
        print(f"   AGENT_USER_ID={user.get('id')}")
        return user.get('id')
    else:
        print(f"❌ Failed to get user info: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    get_annika_user_id() 