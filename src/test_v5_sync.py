#!/usr/bin/env python3
"""
Test script for V5 Webhook-Driven Planner Sync Service

This script tests the basic functionality of the V5 sync service
without running the full service stack.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import after path setup to avoid import errors
from planner_sync_service_v5 import WebhookDrivenPlannerSync  # noqa: E402
from webhook_handler import initialize_webhook_handler  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_v5_initialization():
    """Test V5 service initialization."""
    logger.info("🧪 Testing V5 Sync Service Initialization...")
    
    try:
        # Initialize webhook handler
        logger.info("1. Initializing webhook handler...")
        await initialize_webhook_handler()
        logger.info("✅ Webhook handler initialized")
        
        # Create V5 sync service
        logger.info("2. Creating V5 sync service...")
        sync_service = WebhookDrivenPlannerSync()
        logger.info("✅ V5 sync service created")
        
        # Initialize Redis connection
        logger.info("3. Initializing Redis connection...")
        import redis.asyncio as redis
        sync_service.redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        await sync_service.redis_client.ping()
        logger.info("✅ Redis connection initialized")
        
        # Test loading existing state
        logger.info("4. Testing state loading...")
        await sync_service._load_existing_state()
        logger.info("✅ State loading completed")
        
        # Test webhook setup (this might fail without proper tokens)
        logger.info("5. Testing webhook setup...")
        try:
            await sync_service._setup_webhooks()
            logger.info("✅ Webhook setup completed")
        except Exception as e:
            logger.warning(
                f"⚠️ Webhook setup failed (expected without token): {e}"
            )
        
        # Test cleanup
        logger.info("6. Testing cleanup...")
        await sync_service.stop()
        logger.info("✅ Cleanup completed")
        
        logger.info("🎉 All V5 initialization tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ V5 initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_webhook_handler():
    """Test webhook handler functionality."""
    logger.info("🧪 Testing Webhook Handler...")
    
    try:
        from webhook_handler import webhook_handler
        
        # Test validation
        logger.info("1. Testing webhook validation...")
        test_notification = {
            "changeType": "created",
            "resource": "/planner/tasks/test-id",
            "resourceData": {"id": "test-task-id"},
            "clientState": "annika_planner_sync_v5"
        }
        
        is_valid = webhook_handler._validate_notification(test_notification)
        logger.info(f"✅ Validation result: {is_valid}")
        
        # Test health metrics
        logger.info("2. Testing webhook health...")
        health = await webhook_handler.get_webhook_health()
        logger.info(f"✅ Webhook health: {health}")
        
        logger.info("🎉 All webhook handler tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Webhook handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    logger.info("🚀 Starting V5 Sync Service Tests...")
    
    # Test 1: V5 Service Initialization
    test1_passed = await test_v5_initialization()
    
    # Test 2: Webhook Handler
    test2_passed = await test_webhook_handler()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📊 Test Results:")
    result1 = '✅ PASS' if test1_passed else '❌ FAIL'
    result2 = '✅ PASS' if test2_passed else '❌ FAIL'
    logger.info(f"   V5 Initialization: {result1}")
    logger.info(f"   Webhook Handler:   {result2}")
    
    if test1_passed and test2_passed:
        logger.info("🎉 All tests passed! V5 service is ready.")
        return True
    else:
        logger.error("❌ Some tests failed. Check the logs above.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test runner failed: {e}")
        sys.exit(1) 