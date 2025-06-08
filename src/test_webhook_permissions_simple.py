#!/usr/bin/env python3
"""
Simple webhook permissions test that loads from .env file
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Load environment variables from .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Now import after setting env vars
import httpx  # noqa: E402
from azure.identity import ClientSecretCredential  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_webhook_permissions():
    """Test webhook permissions with current setup."""
    logger.info("🧪 Testing webhook permissions...")
    
    # Get credentials
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        logger.error("❌ Missing Azure AD credentials")
        return False
    
    logger.info(f"✅ Found credentials for tenant: {tenant_id}")
    logger.info(f"✅ Client ID: {client_id}")
    
    try:
        # Get app-only token
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        scope = "https://graph.microsoft.com/.default"
        token_result = credential.get_token(scope)
        
        if not token_result:
            logger.error("❌ Failed to get access token")
            return False
        
        logger.info("✅ Successfully obtained access token")
        
        # Test webhook creation for supported resources
        webhook_url = "https://agency-swarm.ngrok.app/api/graph_webhook"
        
        # Set expiration to 1 hour from now
        expiration = datetime.utcnow() + timedelta(hours=1)
        expiration_str = expiration.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        # Test multiple webhook subscriptions
        webhook_tests = [
            {
                "name": "Groups",
                "resource": "/groups",
                "clientState": "annika_groups_test"
            },
            {
                "name": "Teams Chats",
                "resource": "/chats",
                "clientState": "annika_teams_chats_test"
            }
        ]
        
        headers = {
            "Authorization": f"Bearer {token_result.token}",
            "Content-Type": "application/json"
        }
        
        success_count = 0
        created_subscriptions = []
        
        async with httpx.AsyncClient() as client:
            for test in webhook_tests:
                logger.info(f"🔄 Testing {test['name']} webhook subscription...")
                
                subscription_data = {
                    "changeType": "created,updated,deleted",
                    "notificationUrl": webhook_url,
                    "resource": test["resource"],
                    "expirationDateTime": expiration_str,
                    "clientState": test["clientState"]
                }
                
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/subscriptions",
                    json=subscription_data,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    subscription = response.json()
                    subscription_id = subscription.get('id')
                    created_subscriptions.append(subscription_id)
                    logger.info(f"✅ {test['name']} webhook subscription created!")
                    logger.info(f"   Subscription ID: {subscription_id}")
                    success_count += 1
                    
                elif response.status_code == 403:
                    logger.error(f"❌ 403 Forbidden for {test['name']} - Permission denied")
                    logger.error(f"   Response: {response.text}")
                    
                elif response.status_code == 400:
                    logger.error(f"❌ 400 Bad Request for {test['name']}")
                    logger.error(f"   Response: {response.text}")
                    
                else:
                    logger.error(f"❌ {test['name']} webhook creation failed: {response.status_code}")
                    logger.error(f"   Response: {response.text}")
            
            # Clean up created subscriptions
            if created_subscriptions:
                logger.info(f"🧹 Cleaning up {len(created_subscriptions)} test subscriptions...")
                for sub_id in created_subscriptions:
                    try:
                        delete_response = await client.delete(
                            f"https://graph.microsoft.com/v1.0/subscriptions/{sub_id}",
                            headers=headers
                        )
                        if delete_response.status_code == 204:
                            logger.info(f"✅ Cleaned up subscription {sub_id}")
                        else:
                            logger.warning(f"⚠️ Failed to clean up subscription {sub_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Error cleaning up subscription {sub_id}: {e}")
        
        # Return success if at least one webhook worked
        return success_count > 0
                
    except Exception as e:
        logger.error(f"❌ Error during webhook test: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("🚀 Starting webhook permissions test...")
    logger.info("Testing supported webhook subscriptions for Planner sync")
    
    success = await test_webhook_permissions()
    
    if success:
        logger.info("🎉 Webhook permissions test passed!")
        logger.info("✅ Group webhooks will trigger Planner polling")
        logger.info("✅ Teams webhooks ready for future integration")
    else:
        logger.error("❌ Tests failed. Check permissions and configuration.")
        
    return success


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        sys.exit(1) 