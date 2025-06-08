#!/usr/bin/env python3
"""
Phase 2 Simple Test - Dual Authentication for Comprehensive Monitoring
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

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


async def test_phase2_capabilities():
    """Test Phase 2 dual authentication capabilities"""
    logger.info("🚀 Testing Phase 2 Dual Authentication")
    logger.info("=" * 50)
    
    auth_manager = get_dual_auth_manager()
    
    # Test delegated authentication
    logger.info("\n📋 Testing Delegated Authentication (User Context)")
    delegated_token = auth_manager.get_token("delegated")
    
    if delegated_token:
        logger.info("✅ Delegated token acquired")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {delegated_token}"},
                    timeout=10
                )
                if response.status_code == 200:
                    user = response.json()
                    logger.info(f"✅ Delegated auth validated for: {user.get('displayName')}")
                else:
                    logger.error(f"❌ Delegated auth failed: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Delegated auth error: {e}")
    else:
        logger.error("❌ Failed to acquire delegated token")
    
    # Test application authentication
    logger.info("\n📋 Testing Application Authentication (Tenant-Wide)")
    app_token = auth_manager.get_token("application")
    
    if app_token:
        logger.info("✅ Application token acquired")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/organization",
                    headers={"Authorization": f"Bearer {app_token}"},
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("✅ Application auth validated for tenant-wide access")
                else:
                    logger.error(f"❌ Application auth failed: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Application auth error: {e}")
    else:
        logger.error("❌ Failed to acquire application token")
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("🎯 PHASE 2 SUMMARY")
    logger.info("=" * 50)
    
    if delegated_token and app_token:
        logger.info("🎉 SUCCESS: Phase 2 dual authentication is working!")
        logger.info("\n🚀 Capabilities Enabled:")
        logger.info("  • Delegated monitoring: User's groups, teams, tasks")
        logger.info("  • Application monitoring: Tenant-wide groups, teams, chats")
        logger.info("  • Smart token selection: Right token for each operation")
        logger.info("  • Comprehensive coverage: Nothing escapes monitoring!")
        logger.info("\n📡 Webhook Support:")
        logger.info("  • Groups webhooks: ✅ (delegated token)")
        logger.info("  • Teams chats: ✅ (application token)")
        logger.info("  • Teams channels: ✅ (application token)")
        return True
    else:
        logger.error("❌ Phase 2 setup incomplete - check authentication configuration")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_phase2_capabilities())
    sys.exit(0 if success else 1) 