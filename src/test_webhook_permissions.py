#!/usr/bin/env python3
"""
Test script to verify webhook permissions are properly configured.

This script tests:
1. App-only token acquisition
2. Webhook subscription creation
3. Subscription listing
4. Subscription deletion
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from azure.identity import ClientSecretCredential

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent_auth_manager import get_agent_token  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebhookPermissionTester:
    """Test webhook permissions and functionality."""
    
    def __init__(self):
        self.app_token = None
        self.test_subscription_id = None
        
    def get_app_only_token(self) -> str:
        """Get app-only token for webhook operations."""
        try:
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            client_id = os.environ.get("AZURE_CLIENT_ID")
            client_secret = os.environ.get("AZURE_CLIENT_SECRET")
            
            if not all([tenant_id, client_id, client_secret]):
                logger.error("Missing Azure AD credentials")
                return None
            
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            scope = "https://graph.microsoft.com/.default"
            token_result = credential.get_token(scope)
            
            if token_result:
                logger.info("✅ App-only token acquired successfully")
                return token_result.token
            else:
                logger.error("❌ Failed to acquire app-only token")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error acquiring app-only token: {e}")
            return None
    
    async def test_subscription_permissions(self) -> bool:
        """Test if we can list existing subscriptions."""
        logger.info("🔍 Testing subscription read permissions...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/subscriptions",
                    headers={
                        "Authorization": f"Bearer {self.app_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    subscriptions = data.get("value", [])
                    logger.info(
                        f"✅ Successfully listed {len(subscriptions)} "
                        f"existing subscriptions"
                    )
                    return True
                elif response.status_code == 403:
                    logger.error(
                        "❌ 403 Forbidden - Missing Subscription.Read.All "
                        "permission"
                    )
                    logger.info(
                        "Add 'Subscription.Read.All' application permission "
                        "in Azure Portal"
                    )
                    return False
                else:
                    logger.error(
                        f"❌ Unexpected response: {response.status_code}"
                    )
                    logger.error(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error testing subscription permissions: {e}")
            return False
    
    async def test_webhook_creation(self) -> bool:
        """Test creating a webhook subscription."""
        logger.info("🔗 Testing webhook subscription creation...")
        
        # Use ngrok URL if available
        webhook_url = os.environ.get(
            "GRAPH_WEBHOOK_URL",
            "https://agency-swarm.ngrok.app/api/graph_webhook"
        )
        
        subscription_data = {
            "changeType": "created,updated,deleted",
            "notificationUrl": webhook_url,
            "resource": "/planner/tasks",
            "expirationDateTime": (
                datetime.utcnow() + timedelta(hours=1)
            ).isoformat() + "Z",
            "clientState": "annika_webhook_test"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/subscriptions",
                    headers={
                        "Authorization": f"Bearer {self.app_token}",
                        "Content-Type": "application/json"
                    },
                    json=subscription_data,
                    timeout=30
                )
                
                if response.status_code == 201:
                    data = response.json()
                    self.test_subscription_id = data.get("id")
                    logger.info(
                        f"✅ Successfully created test webhook subscription: "
                        f"{self.test_subscription_id}"
                    )
                    return True
                elif response.status_code == 403:
                    logger.error(
                        "❌ 403 Forbidden - Missing permissions for webhook "
                        "creation"
                    )
                    logger.info(
                        "Required permissions: Subscription.Read.All, "
                        "Group.Read.All, Tasks.ReadWrite"
                    )
                    return False
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "")
                    
                    if "notificationUrl" in error_msg:
                        logger.error(
                            "❌ 400 Bad Request - Webhook URL validation failed"
                        )
                        logger.info(f"Webhook URL: {webhook_url}")
                        logger.info(
                            "Ensure ngrok is running and URL is publicly "
                            "accessible"
                        )
                    else:
                        logger.error(f"❌ 400 Bad Request: {error_msg}")
                    
                    return False
                else:
                    logger.error(
                        f"❌ Unexpected response: {response.status_code}"
                    )
                    logger.error(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error testing webhook creation: {e}")
            return False
    
    async def cleanup_test_subscription(self):
        """Clean up the test subscription."""
        if not self.test_subscription_id:
            return
            
        logger.info("🧹 Cleaning up test subscription...")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://graph.microsoft.com/v1.0/subscriptions/"
                    f"{self.test_subscription_id}",
                    headers={
                        "Authorization": f"Bearer {self.app_token}"
                    },
                    timeout=10
                )
                
                if response.status_code == 204:
                    logger.info("✅ Test subscription cleaned up successfully")
                else:
                    logger.warning(
                        f"⚠️ Failed to clean up test subscription: "
                        f"{response.status_code}"
                    )
                    
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up test subscription: {e}")
    
    async def test_delegated_token(self) -> bool:
        """Test delegated token acquisition."""
        logger.info("🔑 Testing delegated token acquisition...")
        
        try:
            token = await asyncio.to_thread(get_agent_token)
            if token:
                logger.info("✅ Delegated token acquired successfully")
                
                # Test with a simple API call
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://graph.microsoft.com/v1.0/me",
                        headers={
                            "Authorization": f"Bearer {token}"
                        },
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        logger.info(
                            f"✅ Token verified for user: "
                            f"{user_data.get('displayName', 'Unknown')}"
                        )
                        return True
                    else:
                        logger.error(
                            f"❌ Token validation failed: "
                            f"{response.status_code}"
                        )
                        return False
            else:
                logger.error("❌ Failed to acquire delegated token")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing delegated token: {e}")
            return False
    
    async def run_all_tests(self) -> bool:
        """Run all permission tests."""
        logger.info("🚀 Starting webhook permission tests...")
        
        # Test 1: Get app-only token
        self.app_token = self.get_app_only_token()
        if not self.app_token:
            logger.error("❌ Cannot proceed without app-only token")
            return False
        
        # Test 2: Test subscription read permissions
        can_read_subscriptions = await self.test_subscription_permissions()
        
        # Test 3: Test delegated token
        has_delegated_token = await self.test_delegated_token()
        
        # Test 4: Test webhook creation (only if read permissions work)
        can_create_webhooks = False
        if can_read_subscriptions:
            can_create_webhooks = await self.test_webhook_creation()
            
            # Cleanup
            await self.cleanup_test_subscription()
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("📊 Test Results:")
        logger.info(
            f"   App-only token:      "
            f"{'✅ PASS' if self.app_token else '❌ FAIL'}"
        )
        logger.info(
            f"   Subscription read:   "
            f"{'✅ PASS' if can_read_subscriptions else '❌ FAIL'}"
        )
        logger.info(
            f"   Delegated token:     "
            f"{'✅ PASS' if has_delegated_token else '❌ FAIL'}"
        )
        logger.info(
            f"   Webhook creation:    "
            f"{'✅ PASS' if can_create_webhooks else '❌ FAIL'}"
        )
        
        all_passed = all([
            self.app_token,
            can_read_subscriptions,
            has_delegated_token,
            can_create_webhooks
        ])
        
        if all_passed:
            logger.info(
                "\n🎉 All tests passed! Webhook permissions are "
                "properly configured."
            )
            logger.info("The V5 sync service should work correctly.")
        else:
            logger.error("\n❌ Some tests failed. Check the documentation:")
            logger.info("   src/Documentation/WEBHOOK_PERMISSIONS_SETUP.md")
        
        return all_passed


async def main():
    """Main entry point."""
    tester = WebhookPermissionTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 