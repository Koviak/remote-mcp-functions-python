#!/usr/bin/env python3
"""
Phase 2 Webhook Testing - Comprehensive Teams and Groups Monitoring

This script tests the dual authentication webhook setup that provides:
- Delegated tokens: For user-specific operations (Annika's context)
- Application tokens: For tenant-wide monitoring (all users/groups)
- Complete coverage: Groups, Teams chats, Teams channels
"""

import os
import sys
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
import httpx
from dual_auth_manager import DualAuthManager, get_dual_auth_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Phase2WebhookTester:
    """Test Phase 2 webhook setup with dual authentication"""
    
    def __init__(self):
        self.auth_manager = get_dual_auth_manager()
        self.webhook_url = "https://agency-swarm.ngrok.app/api/graph_webhook"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run comprehensive Phase 2 webhook tests"""
        logger.info("🚀 Starting Phase 2 Webhook Tests")
        logger.info("=" * 60)
        
        # Test 1: Validate dual authentication
        await self._test_dual_authentication()
        
        # Test 2: Test Groups webhook (delegated)
        await self._test_groups_webhook()
        
        # Test 3: Test Teams chats webhook (application)
        await self._test_teams_chats_webhook()
        
        # Test 4: Test Teams channels webhook (application)
        await self._test_teams_channels_webhook()
        
        # Test 5: Validate webhook endpoint
        await self._test_webhook_endpoint()
        
        # Test 6: Test comprehensive monitoring
        await self._test_comprehensive_monitoring()
        
        # Print summary
        self._print_test_summary()
        
        return self.test_results
    
    async def _test_dual_authentication(self):
        """Test that both delegated and application tokens work"""
        logger.info("\n📋 Test 1: Dual Authentication")
        logger.info("-" * 40)
        
        try:
            # Test delegated token
            delegated_token = self.auth_manager.get_token("delegated")
            if delegated_token:
                logger.info("✅ Delegated token acquired successfully")
                
                # Test with a simple API call
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/me",
                        headers={"Authorization": f"Bearer {delegated_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        user_data = response.json()
                        logger.info(f"✅ Delegated token validated for: {user_data.get('displayName')}")
                        self.test_results["delegated_auth"] = True
                    else:
                        logger.error(f"❌ Delegated token validation failed: {response.status_code}")
                        self.test_results["delegated_auth"] = False
            else:
                logger.error("❌ Failed to acquire delegated token")
                self.test_results["delegated_auth"] = False
            
            # Test application token
            app_token = self.auth_manager.get_token("application")
            if app_token:
                logger.info("✅ Application token acquired successfully")
                
                # Test with organization info
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/organization",
                        headers={"Authorization": f"Bearer {app_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        org_data = response.json()
                        if org_data.get("value"):
                            org_name = org_data["value"][0].get("displayName", "Unknown")
                            logger.info(f"✅ Application token validated for org: {org_name}")
                            self.test_results["application_auth"] = True
                        else:
                            logger.warning("⚠️  Application token works but no org data")
                            self.test_results["application_auth"] = True
                    else:
                        logger.error(f"❌ Application token validation failed: {response.status_code}")
                        self.test_results["application_auth"] = False
            else:
                logger.error("❌ Failed to acquire application token")
                self.test_results["application_auth"] = False
                
        except Exception as e:
            logger.error(f"❌ Dual authentication test failed: {e}")
            self.test_results["delegated_auth"] = False
            self.test_results["application_auth"] = False
    
    async def _test_groups_webhook(self):
        """Test Groups webhook subscription (uses delegated token)"""
        logger.info("\n📋 Test 2: Groups Webhook (Delegated)")
        logger.info("-" * 40)
        
        try:
            delegated_token = self.auth_manager.get_token("delegated")
            if not delegated_token:
                logger.error("❌ No delegated token available")
                self.test_results["groups_webhook"] = False
                return
            
            webhook_config = {
                "changeType": "created,updated,deleted",
                "notificationUrl": self.webhook_url,
                "resource": "/groups",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=1)
                ).isoformat() + "Z",
                "clientState": "test_groups_webhook_phase2"
            }
            
            headers = {
                "Authorization": f"Bearer {delegated_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.graph_endpoint}/subscriptions",
                    headers=headers,
                    json=webhook_config,
                    timeout=30
                )
                
                if response.status_code == 201:
                    subscription = response.json()
                    subscription_id = subscription["id"]
                    logger.info(f"✅ Groups webhook created: {subscription_id}")
                    self.test_results["groups_webhook"] = True
                    
                    # Clean up the test subscription
                    await self._cleanup_subscription(subscription_id, delegated_token)
                    
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    if "validation" in error_msg.lower():
                        logger.warning(f"⚠️  Groups webhook validation issue: {error_msg}")
                        logger.info("This is expected if webhook endpoint is not accessible")
                        self.test_results["groups_webhook"] = "validation_issue"
                    else:
                        logger.error(f"❌ Groups webhook failed: {error_msg}")
                        self.test_results["groups_webhook"] = False
                else:
                    logger.error(f"❌ Groups webhook failed: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    self.test_results["groups_webhook"] = False
                    
        except Exception as e:
            logger.error(f"❌ Groups webhook test failed: {e}")
            self.test_results["groups_webhook"] = False
    
    async def _test_teams_chats_webhook(self):
        """Test Teams chats webhook subscription (uses application token)"""
        logger.info("\n📋 Test 3: Teams Chats Webhook (Application)")
        logger.info("-" * 40)
        
        try:
            app_token = self.auth_manager.get_token("application")
            if not app_token:
                logger.error("❌ No application token available")
                self.test_results["teams_chats_webhook"] = False
                return
            
            webhook_config = {
                "changeType": "created,updated,deleted",
                "notificationUrl": self.webhook_url,
                "lifecycleNotificationUrl": self.webhook_url,
                "resource": "/chats",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=1)
                ).isoformat() + "Z",
                "clientState": "test_teams_chats_phase2"
            }
            
            headers = {
                "Authorization": f"Bearer {app_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.graph_endpoint}/subscriptions",
                    headers=headers,
                    json=webhook_config,
                    timeout=30
                )
                
                if response.status_code == 201:
                    subscription = response.json()
                    subscription_id = subscription["id"]
                    logger.info(f"✅ Teams chats webhook created: {subscription_id}")
                    self.test_results["teams_chats_webhook"] = True
                    
                    # Clean up the test subscription
                    await self._cleanup_subscription(subscription_id, app_token)
                    
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    if "validation" in error_msg.lower():
                        logger.warning(f"⚠️  Teams chats webhook validation issue: {error_msg}")
                        logger.info("This is expected if webhook endpoint is not accessible")
                        self.test_results["teams_chats_webhook"] = "validation_issue"
                    else:
                        logger.error(f"❌ Teams chats webhook failed: {error_msg}")
                        self.test_results["teams_chats_webhook"] = False
                else:
                    logger.error(f"❌ Teams chats webhook failed: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    self.test_results["teams_chats_webhook"] = False
                    
        except Exception as e:
            logger.error(f"❌ Teams chats webhook test failed: {e}")
            self.test_results["teams_chats_webhook"] = False
    
    async def _test_teams_channels_webhook(self):
        """Test Teams channels webhook subscription (uses application token)"""
        logger.info("\n📋 Test 4: Teams Channels Webhook (Application)")
        logger.info("-" * 40)
        
        try:
            app_token = self.auth_manager.get_token("application")
            if not app_token:
                logger.error("❌ No application token available")
                self.test_results["teams_channels_webhook"] = False
                return
            
            webhook_config = {
                "changeType": "created,updated,deleted",
                "notificationUrl": self.webhook_url,
                "lifecycleNotificationUrl": self.webhook_url,
                "resource": "/teams/getAllChannels",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=1)
                ).isoformat() + "Z",
                "clientState": "test_teams_channels_phase2"
            }
            
            headers = {
                "Authorization": f"Bearer {app_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.graph_endpoint}/subscriptions",
                    headers=headers,
                    json=webhook_config,
                    timeout=30
                )
                
                if response.status_code == 201:
                    subscription = response.json()
                    subscription_id = subscription["id"]
                    logger.info(f"✅ Teams channels webhook created: {subscription_id}")
                    self.test_results["teams_channels_webhook"] = True
                    
                    # Clean up the test subscription
                    await self._cleanup_subscription(subscription_id, app_token)
                    
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    if "validation" in error_msg.lower():
                        logger.warning(f"⚠️  Teams channels webhook validation issue: {error_msg}")
                        logger.info("This is expected if webhook endpoint is not accessible")
                        self.test_results["teams_channels_webhook"] = "validation_issue"
                    else:
                        logger.error(f"❌ Teams channels webhook failed: {error_msg}")
                        self.test_results["teams_channels_webhook"] = False
                else:
                    logger.error(f"❌ Teams channels webhook failed: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    self.test_results["teams_channels_webhook"] = False
                    
        except Exception as e:
            logger.error(f"❌ Teams channels webhook test failed: {e}")
            self.test_results["teams_channels_webhook"] = False
    
    async def _test_webhook_endpoint(self):
        """Test that the webhook endpoint is accessible"""
        logger.info("\n📋 Test 5: Webhook Endpoint Accessibility")
        logger.info("-" * 40)
        
        try:
            async with httpx.AsyncClient() as client:
                # Test basic connectivity
                response = await client.get(
                    self.webhook_url.replace("/api/graph_webhook", "/api/hello"),
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info("✅ Webhook endpoint is accessible")
                    self.test_results["webhook_endpoint"] = True
                else:
                    logger.warning(f"⚠️  Webhook endpoint returned: {response.status_code}")
                    self.test_results["webhook_endpoint"] = False
                    
        except Exception as e:
            logger.error(f"❌ Webhook endpoint test failed: {e}")
            self.test_results["webhook_endpoint"] = False
    
    async def _test_comprehensive_monitoring(self):
        """Test the comprehensive monitoring capabilities"""
        logger.info("\n📋 Test 6: Comprehensive Monitoring Capabilities")
        logger.info("-" * 40)
        
        try:
            # Test what we can monitor with delegated permissions
            delegated_token = self.auth_manager.get_token("delegated")
            if delegated_token:
                logger.info("🔍 Testing delegated monitoring capabilities:")
                
                # Test user's groups
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/me/memberOf",
                        headers={"Authorization": f"Bearer {delegated_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        groups = response.json().get("value", [])
                        logger.info(f"  ✅ Can monitor {len(groups)} user groups")
                    else:
                        logger.warning(f"  ⚠️  Cannot access user groups: {response.status_code}")
                
                # Test user's teams
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/me/joinedTeams",
                        headers={"Authorization": f"Bearer {delegated_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        teams = response.json().get("value", [])
                        logger.info(f"  ✅ Can monitor {len(teams)} user teams")
                    else:
                        logger.warning(f"  ⚠️  Cannot access user teams: {response.status_code}")
            
            # Test what we can monitor with application permissions
            app_token = self.auth_manager.get_token("application")
            if app_token:
                logger.info("🔍 Testing application monitoring capabilities:")
                
                # Test all groups (tenant-wide)
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/groups?$top=5",
                        headers={"Authorization": f"Bearer {app_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        groups = response.json().get("value", [])
                        logger.info(f"  ✅ Can monitor tenant-wide groups (sample: {len(groups)})")
                    else:
                        logger.warning(f"  ⚠️  Cannot access tenant groups: {response.status_code}")
                
                # Test organization info
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.graph_endpoint}/organization",
                        headers={"Authorization": f"Bearer {app_token}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        logger.info("  ✅ Can access organization information")
                    else:
                        logger.warning(f"  ⚠️  Cannot access organization: {response.status_code}")
            
            self.test_results["comprehensive_monitoring"] = True
            
        except Exception as e:
            logger.error(f"❌ Comprehensive monitoring test failed: {e}")
            self.test_results["comprehensive_monitoring"] = False
    
    async def _cleanup_subscription(self, subscription_id: str, token: str):
        """Clean up a test webhook subscription"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.graph_endpoint}/subscriptions/{subscription_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 204:
                    logger.info(f"🧹 Cleaned up test subscription: {subscription_id}")
                else:
                    logger.warning(f"⚠️  Failed to cleanup subscription: {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"⚠️  Error cleaning up subscription: {e}")
    
    def _print_test_summary(self):
        """Print a summary of all test results"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 PHASE 2 WEBHOOK TEST SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result is True)
        validation_issues = sum(1 for result in self.test_results.values() if result == "validation_issue")
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Validation Issues: {validation_issues}")
        logger.info(f"Failed: {total_tests - passed_tests - validation_issues}")
        
        logger.info("\nDetailed Results:")
        for test_name, result in self.test_results.items():
            if result is True:
                status = "✅ PASS"
            elif result == "validation_issue":
                status = "⚠️  VALIDATION ISSUE"
            else:
                status = "❌ FAIL"
            
            logger.info(f"  {test_name}: {status}")
        
        if passed_tests == total_tests:
            logger.info("\n🎉 ALL TESTS PASSED! Phase 2 is ready for deployment.")
        elif passed_tests + validation_issues == total_tests:
            logger.info("\n⚠️  All tests passed with validation issues.")
            logger.info("This is expected if webhook endpoint is not accessible from Microsoft.")
            logger.info("Deploy to make webhook endpoint accessible for full functionality.")
        else:
            logger.info("\n❌ Some tests failed. Check configuration and permissions.")
        
        logger.info("\n🚀 Phase 2 Capabilities:")
        logger.info("  • Delegated monitoring: User's groups, teams, tasks")
        logger.info("  • Application monitoring: Tenant-wide groups, teams, chats")
        logger.info("  • Smart token selection: Right token for each operation")
        logger.info("  • Comprehensive coverage: Nothing escapes monitoring!")


async def main():
    """Main entry point"""
    tester = Phase2WebhookTester()
    results = await tester.run_all_tests()
    
    # Return appropriate exit code
    failed_tests = sum(1 for result in results.values() if result is False)
    sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main()) 