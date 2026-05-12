#!/usr/bin/env python3
"""
Real-time Webhook Monitor for Annika

This script monitors all incoming webhook notifications in real-time
and displays them in the CLI, including Teams chat messages.
"""

import asyncio
import json
import logging
import os
import sys
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


async def monitor_webhooks():
    """Monitor all webhook notifications in real-time."""
    logger.info("🎧 Starting real-time webhook monitor...")
    logger.info("📡 Listening for webhook notifications...")
    logger.info("💬 Send a Teams message to Annika to test!")
    logger.info("=" * 60)
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        await redis_client.ping()
        
        # Subscribe to all webhook-related channels
        pubsub = redis_client.pubsub()
        
        # Subscribe to main webhook channel
        await pubsub.subscribe("annika:planner:webhook")
        
        # Subscribe to Teams channels
        await pubsub.subscribe("annika:teams:chat_messages")
        await pubsub.subscribe("annika:teams:chats")
        await pubsub.subscribe("annika:teams:channel_messages")
        await pubsub.subscribe("annika:teams:channels")
        
        logger.info("✅ Subscribed to webhook channels")
        logger.info("⏳ Waiting for webhook notifications...")
        logger.info("")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    channel = message.get('channel', 'unknown')
                    data = message.get('data', '')
                    
                    # Parse the notification
                    try:
                        notification = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning(f"📨 Raw message on {channel}: {data}")
                        continue
                    
                    # Display the notification based on type
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if channel == "annika:planner:webhook":
                        # Main webhook notification
                        resource = notification.get("resource", "unknown")
                        change_type = notification.get("changeType", "unknown")
                        client_state = notification.get("clientState", "none")
                        
                        print(f"🔔 [{timestamp}] WEBHOOK: {change_type} | {resource} | state: {client_state}")
                        
                        # Show resource data if available
                        resource_data = notification.get("resourceData", {})
                        if resource_data:
                            resource_id = resource_data.get("id", "unknown")
                            print(f"   📋 Resource ID: {resource_id[:20]}...")
                        
                    elif channel == "annika:teams:chat_messages":
                        # Teams chat message
                        msg_type = notification.get("type", "unknown")
                        change_type = notification.get("change_type", "unknown")
                        chat_id = notification.get("chat_id", "unknown")
                        message_id = notification.get("message_id", "unknown")
                        
                        print(f"💬 [{timestamp}] TEAMS CHAT MESSAGE: {change_type}")
                        print(f"   📱 Chat: {chat_id[:20]}...")
                        print(f"   📝 Message: {message_id[:20]}...")
                        
                    elif channel == "annika:teams:chats":
                        # Teams chat event
                        msg_type = notification.get("type", "unknown")
                        change_type = notification.get("change_type", "unknown")
                        chat_id = notification.get("chat_id", "unknown")
                        
                        print(f"💬 [{timestamp}] TEAMS CHAT: {change_type}")
                        print(f"   📱 Chat: {chat_id[:20]}...")
                        
                    elif channel == "annika:teams:channel_messages":
                        # Teams channel message
                        msg_type = notification.get("type", "unknown")
                        change_type = notification.get("change_type", "unknown")
                        team_id = notification.get("team_id", "unknown")
                        channel_id = notification.get("channel_id", "unknown")
                        message_id = notification.get("message_id", "unknown")
                        
                        print(f"📺 [{timestamp}] TEAMS CHANNEL MESSAGE: {change_type}")
                        print(f"   🏢 Team: {team_id[:20]}...")
                        print(f"   📺 Channel: {channel_id[:20]}...")
                        print(f"   📝 Message: {message_id[:20]}...")
                        
                    elif channel == "annika:teams:channels":
                        # Teams channel event
                        msg_type = notification.get("type", "unknown")
                        change_type = notification.get("change_type", "unknown")
                        channel_id = notification.get("channel_id", "unknown")
                        
                        print(f"📺 [{timestamp}] TEAMS CHANNEL: {change_type}")
                        print(f"   📺 Channel: {channel_id[:20]}...")
                    
                    else:
                        print(f"❓ [{timestamp}] UNKNOWN: {channel}")
                        print(f"   📄 Data: {str(notification)[:100]}...")
                    
                    print("")  # Empty line for readability
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
    except KeyboardInterrupt:
        logger.info("🛑 Webhook monitor stopped by user")
    except Exception as e:
        logger.error(f"❌ Error in webhook monitor: {e}")
    finally:
        try:
            await redis_client.aclose()
        except:
            pass


async def show_recent_activity():
    """Show recent webhook activity before starting real-time monitoring."""
    logger.info("📊 Checking recent webhook activity...")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        await redis_client.ping()
        
        # Check recent webhook notifications
        webhook_key = "annika:webhooks:notifications"
        notifications = await redis_client.lrange(webhook_key, 0, 4)
        
        if notifications:
            logger.info(f"📨 Found {len(notifications)} recent webhook notifications:")
            for i, notification_json in enumerate(notifications, 1):
                try:
                    notification = json.loads(notification_json)
                    timestamp = notification.get("timestamp", "unknown")
                    resource = notification.get("resource", "unknown")
                    change_type = notification.get("changeType", "unknown")
                    
                    logger.info(f"  {i}. {timestamp} | {change_type} | {resource}")
                    
                except json.JSONDecodeError:
                    logger.warning(f"  {i}. Invalid JSON: {notification_json[:50]}...")
        else:
            logger.info("📭 No recent webhook notifications found")
        
        # Check Teams message history
        teams_key = "annika:teams:chat_messages:history"
        messages = await redis_client.lrange(teams_key, 0, 4)
        
        if messages:
            logger.info(f"💬 Found {len(messages)} recent Teams chat messages:")
            for i, message_json in enumerate(messages, 1):
                try:
                    message = json.loads(message_json)
                    timestamp = message.get("timestamp", "unknown")
                    change_type = message.get("change_type", "unknown")
                    chat_id = message.get("chat_id", "unknown")
                    
                    logger.info(f"  {i}. {timestamp} | {change_type} | Chat: {chat_id[:15]}...")
                    
                except json.JSONDecodeError:
                    logger.warning(f"  {i}. Invalid JSON: {message_json[:50]}...")
        else:
            logger.info("💬 No recent Teams chat messages found")
        
        await redis_client.aclose()
        
    except Exception as e:
        logger.error(f"❌ Error checking recent activity: {e}")


async def main():
    """Main function."""
    logger.info("🚀 Starting Webhook Monitor for Annika...")
    
    # Show recent activity first
    await show_recent_activity()
    
    logger.info("")
    logger.info("🎯 Starting real-time monitoring...")
    logger.info("💡 Send a Teams message to Annika to see it appear here!")
    logger.info("")
    
    # Start real-time monitoring
    await monitor_webhooks()


if __name__ == "__main__":
    asyncio.run(main()) 