#!/usr/bin/env python3
"""
Test Teams Webhook Subscriptions

This script tests that Teams webhook subscriptions are working
and that messages are being saved to Redis channels.
"""

import asyncio
import json
import logging
import sys
import os

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import redis.asyncio as redis  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_redis_channels():
    """Test Redis channels for Teams messages."""
    logger.info("🧪 Testing Redis channels for Teams messages...")
    
    try:
        # Connect to Redis
        redis_client = await redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("✅ Connected to Redis")
        
        # Check for existing message history
        channels_to_check = [
            "annika:teams:chat_messages:history",
            "annika:teams:channel_messages:history",
            "annika:teams:chats:history",
            "annika:teams:channels:history"
        ]
        
        for channel in channels_to_check:
            count = await redis_client.llen(channel)
            logger.info(f"📊 {channel}: {count} messages")
            
            if count > 0:
                # Show latest message
                latest = await redis_client.lindex(channel, 0)
                if latest:
                    try:
                        msg = json.loads(latest)
                        timestamp = msg.get("timestamp", "unknown")
                        msg_type = msg.get("type", "unknown")
                        logger.info(f"  Latest: {msg_type} at {timestamp}")
                    except json.JSONDecodeError:
                        logger.info(f"  Latest: {latest[:100]}...")
        
        return redis_client
        
    except Exception as e:
        logger.error(f"❌ Error connecting to Redis: {e}")
        return None


async def listen_for_messages(redis_client, timeout=30):
    """Listen for new Teams messages on Redis channels."""
    logger.info(f"👂 Listening for Teams messages for {timeout} seconds...")
    
    try:
        # Subscribe to all Teams channels
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(
            "annika:teams:chat_messages",
            "annika:teams:channel_messages",
            "annika:teams:chats",
            "annika:teams:channels"
        )
        
        logger.info("✅ Subscribed to Teams channels")
        logger.info("💬 Send a Teams message to test...")
        
        # Listen for messages with timeout
        start_time = asyncio.get_event_loop().time()
        message_count = 0
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                message_count += 1
                channel = message["channel"]
                data = message["data"]
                
                logger.info(f"📨 Message #{message_count} on {channel}")
                
                try:
                    msg_data = json.loads(data)
                    msg_type = msg_data.get("type", "unknown")
                    change_type = msg_data.get("change_type", "unknown")
                    timestamp = msg_data.get("timestamp", "unknown")
                    
                    logger.info(f"  Type: {msg_type}")
                    logger.info(f"  Change: {change_type}")
                    logger.info(f"  Time: {timestamp}")
                    
                    if msg_type == "teams_chat_message":
                        chat_id = msg_data.get("chat_id", "unknown")
                        message_id = msg_data.get("message_id", "unknown")
                        logger.info(f"  Chat: {chat_id[:8]}")
                        logger.info(f"  Message: {message_id[:8]}")
                    elif msg_type == "teams_channel_message":
                        team_id = msg_data.get("team_id", "unknown")
                        channel_id = msg_data.get("channel_id", "unknown")
                        message_id = msg_data.get("message_id", "unknown")
                        logger.info(f"  Team: {team_id[:8]}")
                        logger.info(f"  Channel: {channel_id[:8]}")
                        logger.info(f"  Message: {message_id[:8]}")
                    
                except json.JSONDecodeError:
                    logger.info(f"  Raw data: {data[:100]}...")
            
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                break
        
        if message_count == 0:
            logger.info("⏰ No messages received during test period")
        else:
            logger.info(f"✅ Received {message_count} messages")
        
    except Exception as e:
        logger.error(f"❌ Error listening for messages: {e}")


async def simulate_webhook_notification():
    """Simulate a webhook notification for testing."""
    logger.info("🎭 Simulating webhook notification...")
    
    try:
        from webhook_handler import webhook_handler
        
        # Simulate a chat message notification
        test_notification = {
            "subscriptionId": "test-subscription-123",
            "changeType": "created",
            "clientState": "annika_user_chat_messages",
            "resource": "/me/chats/19:test-chat-id@thread.v2/messages/1234567890",
            "resourceData": {
                "id": "1234567890",
                "@odata.type": "#Microsoft.Graph.chatMessage",
                "@odata.id": "chats('19:test-chat-id@thread.v2')/messages('1234567890')"
            },
            "tenantId": "test-tenant-id"
        }
        
        # Initialize webhook handler if needed
        if not webhook_handler.redis_client:
            from webhook_handler import initialize_webhook_handler
            await initialize_webhook_handler()
        
        # Process the test notification
        success = await webhook_handler.handle_webhook_notification(test_notification)
        
        if success:
            logger.info("✅ Test notification processed successfully")
        else:
            logger.error("❌ Test notification failed")
        
    except Exception as e:
        logger.error(f"❌ Error simulating webhook: {e}")


async def main():
    """Main test function."""
    logger.info("🚀 Starting Teams webhook test...")
    
    # Test Redis connection and check existing data
    redis_client = await test_redis_channels()
    if not redis_client:
        logger.error("❌ Cannot connect to Redis, exiting")
        return
    
    try:
        # Simulate a webhook notification
        await simulate_webhook_notification()
        
        # Listen for messages
        await listen_for_messages(redis_client, timeout=10)
        
        logger.info("🎉 Test completed!")
        
    finally:
        await redis_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1) 