#!/usr/bin/env python3
"""
Test Webhook Flow

This script tests the webhook flow by simulating a Teams chat message
and checking if it gets processed correctly.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_webhook_flow():
    """Test the webhook flow by simulating a notification."""
    logger.info("🧪 Testing webhook flow...")
    
    try:
        # Connect to Redis
        redis_client = await redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        
        # Create a test Teams chat message notification
        test_notification = {
            "changeType": "created",
            "resource": "/chats/19:test-chat-id/messages/1234567890",
            "resourceData": {
                "id": "1234567890",
                "@odata.type": "#Microsoft.Graph.chatMessage"
            },
            "subscriptionId": "test-subscription-id",
            "clientState": "test-client-state",
            "subscriptionExpirationDateTime": datetime.utcnow().isoformat() + "Z"
        }
        
        logger.info("📤 Sending test notification to webhook channel...")
        
        # Send to the main webhook channel (simulating the webhook handler)
        await redis_client.publish(
            "annika:planner:webhook",
            json.dumps(test_notification)
        )
        
        logger.info("✅ Test notification sent")
        
        # Wait a moment for processing
        await asyncio.sleep(2)
        
        # Check if it was processed and saved to Teams channels
        teams_key = "annika:teams:chat_messages:history"
        messages = await redis_client.lrange(teams_key, 0, 4)
        
        logger.info(f"📊 Found {len(messages)} messages in Teams history")
        
        # Check for our test message
        found_test = False
        for msg_json in messages:
            try:
                msg = json.loads(msg_json)
                if msg.get("message_id") == "1234567890":
                    found_test = True
                    logger.info("✅ Test message found in Teams history!")
                    break
            except:
                continue
        
        if not found_test:
            logger.warning("⚠️ Test message not found in Teams history")
        
        # Check webhook logs
        webhook_logs = await redis_client.lrange("annika:webhook:log", 0, 4)
        logger.info(f"📋 Found {len(webhook_logs)} webhook log entries")
        
        # Check if V5 sync service is processing webhooks
        logger.info("🔍 Checking if V5 sync service is processing webhooks...")
        
        # Send a direct test to Teams chat messages channel
        test_chat_message = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "teams_chat_message",
            "change_type": "created",
            "chat_id": "19:test-direct-chat",
            "message_id": "direct-test-message",
            "test": True
        }
        
        await redis_client.publish(
            "annika:teams:chat_messages",
            json.dumps(test_chat_message)
        )
        
        logger.info("📤 Sent direct test to Teams chat messages channel")
        
        await redis_client.aclose()
        
    except Exception as e:
        logger.error(f"❌ Error testing webhook flow: {e}")


async def check_webhook_subscriptions():
    """Check active webhook subscriptions."""
    logger.info("🔍 Checking webhook subscriptions...")
    
    try:
        from graph_subscription_manager import GraphSubscriptionManager
        
        mgr = GraphSubscriptionManager()
        subs = mgr.list_active_subscriptions()
        
        logger.info(f"📊 Found {len(subs)} active subscriptions:")
        
        for i, sub in enumerate(subs, 1):
            resource = sub.get("resource", "unknown")
            client_state = sub.get("clientState", "none")
            expires = sub.get("expirationDateTime", "unknown")
            sub_id = sub.get("id", "unknown")
            
            if "/chats" in resource or "/teams" in resource:
                logger.info(f"💬 {i}. Teams: {resource}")
                logger.info(f"    ID: {sub_id}")
                logger.info(f"    State: {client_state}")
                logger.info(f"    Expires: {expires}")
                logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Error checking subscriptions: {e}")


async def monitor_real_time():
    """Monitor webhook notifications in real-time for 30 seconds."""
    logger.info("🎧 Monitoring webhook notifications for 30 seconds...")
    logger.info("💬 Send a Teams message to Annika now!")
    
    try:
        # Connect to Redis
        redis_client = await redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        
        # Subscribe to webhook channels
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("annika:planner:webhook")
        await pubsub.subscribe("annika:teams:chat_messages")
        
        logger.info("✅ Subscribed to webhook channels")
        logger.info("⏳ Waiting for notifications...")
        
        # Monitor for 30 seconds
        start_time = asyncio.get_event_loop().time()
        timeout = 30
        
        async for message in pubsub.listen():
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > timeout:
                break
            
            if message['type'] == 'message':
                channel = message.get('channel', 'unknown')
                data = message.get('data', '')
                
                try:
                    notification = json.loads(data)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if channel == "annika:planner:webhook":
                        resource = notification.get("resource", "unknown")
                        change_type = notification.get("changeType", "unknown")
                        print(f"🔔 [{timestamp}] WEBHOOK: {change_type} | {resource}")
                        
                    elif channel == "annika:teams:chat_messages":
                        change_type = notification.get("change_type", "unknown")
                        chat_id = notification.get("chat_id", "unknown")
                        print(f"💬 [{timestamp}] TEAMS MESSAGE: {change_type} | Chat: {chat_id[:15]}...")
                        
                except json.JSONDecodeError:
                    print(f"📨 [{datetime.now().strftime('%H:%M:%S')}] Raw: {data[:50]}...")
        
        logger.info("⏰ Monitoring timeout reached")
        await redis_client.aclose()
        
    except Exception as e:
        logger.error(f"❌ Error monitoring: {e}")


async def main():
    """Main function."""
    logger.info("🚀 Starting webhook flow test...")
    
    # Check subscriptions first
    await check_webhook_subscriptions()
    
    # Test the webhook flow
    await test_webhook_flow()
    
    # Monitor real-time
    await monitor_real_time()
    
    logger.info("✅ Webhook flow test complete!")


if __name__ == "__main__":
    asyncio.run(main()) 