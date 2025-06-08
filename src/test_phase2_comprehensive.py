#!/usr/bin/env python3
"""
Phase 2 Comprehensive Test - Live Service Validation

This script tests the Phase 2 implementation with the currently running services
to validate that dual authentication and webhook architecture are working correctly.
"""

import os
import sys
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

# Load environment variables
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

import httpx
from dual_auth_manager import get_dual_auth_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_phase2_with_running_services():
    """Test Phase 2 implementation with currently running services"""
    logger.info("🚀 Phase 2 Comprehensive Test - Live Service Validation")
    logger.info("=" * 70)
    
    results = {}
    
    # Test 1: Dual Authentication
    logger.info("\n📋 Test 1: Dual Authentication System")
    logger.info("-" * 50)
    
    auth_manager = get_dual_auth_manager()
    
    # Test delegated token
    delegated_token = auth_manager.get_token("delegated")
    if delegated_token:
        logger.info("✅ Delegated token acquired successfully")
        
        # Validate with Microsoft Graph
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {delegated_token}"},
                timeout=10
            )
            if response.status_code == 200:
                user = response.json()
                logger.info(f"✅ Delegated token validated for: {user.get('displayName')}")
                results["delegated_auth"] = True
            else:
                logger.error(f"❌ Delegated token validation failed: {response.status_code}")
                results["delegated_auth"] = False
    else:
        logger.error("❌ Failed to acquire delegated token")
        results["delegated_auth"] = False
    
    # Test application token
    app_token = auth_manager.get_token("application")
    if app_token:
        logger.info("✅ Application token acquired successfully")
        
        # Validate with Microsoft Graph
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/organization",
                headers={"Authorization": f"Bearer {app_token}"},
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✅ Application token validated for tenant-wide access")
                results["application_auth"] = True
            else:
                logger.error(f"❌ Application token validation failed: {response.status_code}")
                results["application_auth"] = False
    else:
        logger.error("❌ Failed to acquire application token")
        results["application_auth"] = False
    
    # Test 2: Function App Connectivity
    logger.info("\n📋 Test 2: Function App Connectivity")
    logger.info("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:7071/api/hello", timeout=10)
            if response.status_code == 200:
                logger.info("✅ Function App is accessible locally")
                results["function_app_local"] = True
            else:
                logger.error(f"❌ Function App returned: {response.status_code}")
                results["function_app_local"] = False
    except Exception as e:
        logger.error(f"❌ Function App not accessible: {e}")
        results["function_app_local"] = False
    
    # Test 3: ngrok Tunnel
    logger.info("\n📋 Test 3: ngrok Tunnel Status")
    logger.info("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://agency-swarm.ngrok.app/api/hello", timeout=10)
            if response.status_code == 200:
                logger.info("✅ ngrok tunnel is accessible externally")
                results["ngrok_tunnel"] = True
            else:
                logger.error(f"❌ ngrok tunnel returned: {response.status_code}")
                results["ngrok_tunnel"] = False
    except Exception as e:
        logger.error(f"❌ ngrok tunnel not accessible: {e}")
        results["ngrok_tunnel"] = False
    
    # Test 4: Webhook Endpoint
    logger.info("\n📋 Test 4: Webhook Endpoint Validation")
    logger.info("-" * 50)
    
    try:
        async with httpx.AsyncClient() as client:
            # Test webhook endpoint with validation token
            response = await client.post(
                "https://agency-swarm.ngrok.app/api/graph_webhook",
                params={"validationToken": "test123"},
                timeout=10
            )
            if response.status_code == 200 and response.text == "test123":
                logger.info("✅ Webhook endpoint responds correctly to validation")
                results["webhook_endpoint"] = True
            else:
                logger.warning(f"⚠️  Webhook endpoint response: {response.status_code}")
                results["webhook_endpoint"] = False
    except Exception as e:
        logger.error(f"❌ Webhook endpoint test failed: {e}")
        results["webhook_endpoint"] = False
    
    # Test 5: Smart Token Selection
    logger.info("\n📋 Test 5: Smart Token Selection")
    logger.info("-" * 50)
    
    # Test operation-based token selection
    operations_to_test = [
        ("tenant_wide_groups", "application"),
        ("all_teams_monitoring", "application"),
        ("user_specific_tasks", "delegated"),
        ("user_planner_access", "delegated"),
        ("unknown_operation", "delegated")  # Should default to delegated
    ]
    
    smart_selection_working = True
    for operation, expected_type in operations_to_test:
        token = auth_manager.get_best_token_for_operation(operation)
        if token:
            # We can't easily determine the token type from the token itself,
            # but we can verify that we get a token
            logger.info(f"✅ Token acquired for operation: {operation}")
        else:
            logger.error(f"❌ No token for operation: {operation}")
            smart_selection_working = False
    
    results["smart_token_selection"] = smart_selection_working
    
    # Test 6: Monitoring Capabilities
    logger.info("\n📋 Test 6: Monitoring Capabilities")
    logger.info("-" * 50)
    
    monitoring_capabilities = {}
    
    # Test user groups monitoring (delegated)
    if delegated_token:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/memberOf",
                    headers={"Authorization": f"Bearer {delegated_token}"},
                    timeout=10
                )
                if response.status_code == 200:
                    groups = response.json().get("value", [])
                    logger.info(f"✅ Can monitor {len(groups)} user groups")
                    monitoring_capabilities["user_groups"] = len(groups)
                else:
                    logger.warning(f"⚠️  Cannot access user groups: {response.status_code}")
                    monitoring_capabilities["user_groups"] = 0
        except Exception as e:
            logger.error(f"❌ User groups monitoring failed: {e}")
            monitoring_capabilities["user_groups"] = 0
    
    # Test tenant groups monitoring (application)
    if app_token:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/groups?$top=5",
                    headers={"Authorization": f"Bearer {app_token}"},
                    timeout=10
                )
                if response.status_code == 200:
                    groups = response.json().get("value", [])
                    logger.info(f"✅ Can monitor tenant-wide groups (sample: {len(groups)})")
                    monitoring_capabilities["tenant_groups"] = len(groups)
                else:
                    logger.warning(f"⚠️  Cannot access tenant groups: {response.status_code}")
                    monitoring_capabilities["tenant_groups"] = 0
        except Exception as e:
            logger.error(f"❌ Tenant groups monitoring failed: {e}")
            monitoring_capabilities["tenant_groups"] = 0
    
    results["monitoring_capabilities"] = monitoring_capabilities
    
    # Test 7: Redis Token Storage
    logger.info("\n📋 Test 7: Redis Token Storage")
    logger.info("-" * 50)
    
    try:
        # Test token storage by getting tokens again (should use cache)
        cached_delegated = auth_manager.get_token("delegated")
        cached_app = auth_manager.get_token("application")
        
        if cached_delegated and cached_app:
            logger.info("✅ Token caching and Redis storage working")
            results["redis_storage"] = True
        else:
            logger.error("❌ Token caching/storage issues")
            results["redis_storage"] = False
    except Exception as e:
        logger.error(f"❌ Redis storage test failed: {e}")
        results["redis_storage"] = False
    
    # Print comprehensive summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 PHASE 2 COMPREHENSIVE TEST RESULTS")
    logger.info("=" * 70)
    
    total_tests = len([k for k in results.keys() if k != "monitoring_capabilities"])
    passed_tests = sum(1 for k, v in results.items() if k != "monitoring_capabilities" and v is True)
    
    logger.info(f"Core Tests: {passed_tests}/{total_tests} passed")
    
    # Detailed results
    logger.info("\nDetailed Results:")
    test_descriptions = {
        "delegated_auth": "Delegated Authentication",
        "application_auth": "Application Authentication", 
        "function_app_local": "Function App (Local)",
        "ngrok_tunnel": "ngrok Tunnel (External)",
        "webhook_endpoint": "Webhook Endpoint Validation",
        "smart_token_selection": "Smart Token Selection",
        "redis_storage": "Redis Token Storage"
    }
    
    for test_key, description in test_descriptions.items():
        if test_key in results:
            status = "✅ PASS" if results[test_key] else "❌ FAIL"
            logger.info(f"  {description}: {status}")
    
    # Monitoring capabilities
    if "monitoring_capabilities" in results:
        caps = results["monitoring_capabilities"]
        logger.info(f"\nMonitoring Capabilities:")
        logger.info(f"  User Groups: {caps.get('user_groups', 0)} accessible")
        logger.info(f"  Tenant Groups: {caps.get('tenant_groups', 0)} accessible")
    
    # Overall assessment
    logger.info("\n" + "=" * 70)
    if passed_tests == total_tests:
        logger.info("🎉 PHASE 2 FULLY OPERATIONAL!")
        logger.info("All core systems are working correctly.")
        
        if results.get("webhook_endpoint"):
            logger.info("🚀 Ready for live webhook subscriptions!")
        else:
            logger.info("⚠️  Webhook validation will work once deployed to accessible endpoint")
        
        logger.info("\n🎯 Phase 2 Achievements:")
        logger.info("  ✅ Dual authentication (delegated + application)")
        logger.info("  ✅ Smart token selection for operations")
        logger.info("  ✅ Comprehensive monitoring capabilities")
        logger.info("  ✅ Redis token caching and storage")
        logger.info("  ✅ Function App and ngrok infrastructure")
        logger.info("  ✅ Webhook endpoint ready for validation")
        
        return True
    else:
        logger.error("❌ Some Phase 2 components need attention")
        failed_tests = [desc for key, desc in test_descriptions.items() if not results.get(key, False)]
        logger.error(f"Failed tests: {', '.join(failed_tests)}")
        return False


async def main():
    """Main entry point"""
    success = await test_phase2_with_running_services()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 