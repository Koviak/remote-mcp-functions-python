#!/usr/bin/env python3
"""
Setup Teams Chat Message Subscriptions for Annika

This script sets up Microsoft Graph webhook subscriptions to receive
Teams chat messages sent to Annika and saves them to Redis channels.
"""

import asyncio
import logging
import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from graph_subscription_manager import GraphSubscriptionManager  # noqa: E402
from webhook_handler import initialize_webhook_handler  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_teams_subscriptions():
    """Set up Teams chat message subscriptions for Annika."""
    logger.info("🚀 Setting up Teams chat message subscriptions for Annika...")
    
    try:
        # Initialize webhook handler
        await initialize_webhook_handler()
        logger.info("✅ Webhook handler initialized")
        
        # Create subscription manager
        subscription_manager = GraphSubscriptionManager()
        
        # Set up chat message subscriptions
        logger.info("🔔 Creating Teams chat message subscriptions...")
        chat_subs = (
            subscription_manager.create_teams_chat_message_subscriptions()
        )
        
        if chat_subs:
            logger.info(
                f"✅ Created {len(chat_subs)} chat message subscriptions:"
            )
            for sub_type, sub_id in chat_subs.items():
                logger.info(f"  - {sub_type}: {sub_id}")
        else:
            logger.warning("⚠️ No chat message subscriptions were created")
        
        # Set up channel message subscriptions
        logger.info("📺 Creating Teams channel message subscriptions...")
        channel_subs = (
            subscription_manager.create_teams_channel_message_subscriptions()
        )
        
        if channel_subs:
            logger.info(
                f"✅ Created {len(channel_subs)} channel message subscriptions:"
            )
            for sub_type, sub_id in channel_subs.items():
                logger.info(f"  - {sub_type}: {sub_id}")
        else:
            logger.warning("⚠️ No channel message subscriptions were created")
        
        # List all active subscriptions
        logger.info("📋 Listing all active subscriptions...")
        all_subs = subscription_manager.list_active_subscriptions()
        logger.info(f"Total active subscriptions: {len(all_subs)}")
        
        for sub in all_subs:
            resource = sub.get("resource", "unknown")
            client_state = sub.get("clientState", "unknown")
            expiry = sub.get("expirationDateTime", "unknown")
            logger.info(
                f"  - {resource} (state: {client_state}, expires: {expiry})"
            )
        
        logger.info("🎉 Teams subscription setup completed!")
        
        # Print Redis channel information
        logger.info("\n📡 Annika can now subscribe to these Redis channels:")
        logger.info("  - annika:teams:chat_messages (for chat messages)")
        logger.info("  - annika:teams:channel_messages (for channel messages)")
        logger.info("  - annika:teams:chats (for chat events)")
        logger.info("  - annika:teams:channels (for channel events)")
        logger.info("\n📚 Message history is stored in:")
        logger.info("  - annika:teams:chat_messages:history")
        logger.info("  - annika:teams:channel_messages:history")
        logger.info("  - annika:teams:chats:history")
        logger.info("  - annika:teams:channels:history")
        
    except Exception as e:
        logger.error(f"❌ Error setting up Teams subscriptions: {e}")
        raise


async def test_redis_subscription():
    """Test subscribing to the Redis channels."""
    import redis.asyncio as redis
    
    logger.info("\n🧪 Testing Redis subscription...")
    
    try:
        # Connect to Redis
        redis_client = await redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        
        # Subscribe to chat messages channel
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("annika:teams:chat_messages")
        
        logger.info("✅ Subscribed to annika:teams:chat_messages")
        logger.info("💬 Waiting for chat messages... (Press Ctrl+C to stop)")
        
        # Listen for messages (for testing)
        async for message in pubsub.listen():
            if message["type"] == "message":
                logger.info(f"📨 Received chat message: {message['data']}")
        
    except KeyboardInterrupt:
        logger.info("🛑 Stopped listening for messages")
    except Exception as e:
        logger.error(f"❌ Error testing Redis subscription: {e}")
    finally:
        if 'redis_client' in locals():
            await redis_client.close()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup Teams subscriptions for Annika")
    parser.add_argument(
        "--test", 
        action="store_true", 
        help="Test Redis subscription after setup"
    )
    args = parser.parse_args()
    
    try:
        # Set up subscriptions
        asyncio.run(setup_teams_subscriptions())
        
        # Test if requested
        if args.test:
            asyncio.run(test_redis_subscription())
            
    except KeyboardInterrupt:
        logger.info("🛑 Setup interrupted by user")
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 