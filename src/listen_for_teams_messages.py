#!/usr/bin/env python3
"""
Listen for Teams Chat Messages for Annika

This script demonstrates how Annika can subscribe to Teams chat messages
in real-time via Redis pub/sub channels.
"""

import asyncio
import json
import logging
from datetime import datetime

import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def listen_for_chat_messages():
    """Listen for Teams chat messages on Redis channels."""
    logger.info("🎧 Starting Teams chat message listener for Annika...")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        await redis_client.ping()

        # Test connection
        await redis_client.ping()
        logger.info("✅ Connected to Redis")
        
        # Subscribe to Teams chat message channels
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(
            "annika:teams:chat_messages",
            "annika:teams:channel_messages",
            "annika:teams:chats",
            "annika:teams:channels"
        )
        
        logger.info("📡 Subscribed to Teams message channels:")
        logger.info("  - annika:teams:chat_messages (chat messages)")
        logger.info("  - annika:teams:channel_messages (channel messages)")
        logger.info("  - annika:teams:chats (chat events)")
        logger.info("  - annika:teams:channels (channel events)")
        logger.info()
        logger.info("💬 Waiting for Teams messages... (Press Ctrl+C to stop)")
        logger.info("   Send a message to Annika in Teams to test!")
        logger.info()
        
        message_count = 0
        
        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                message_count += 1
                channel = message["channel"]
                data = message["data"]
                
                try:
                    msg_data = json.loads(data)
                    timestamp = msg_data.get("timestamp", "unknown")
                    msg_type = msg_data.get("type", "unknown")
                    change_type = msg_data.get("change_type", "unknown")
                    
                    # Parse timestamp for display
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp
                    
                    logger.info(f"📨 Message #{message_count} received at {time_str}")
                    logger.info(f"   Channel: {channel}")
                    logger.info(f"   Type: {msg_type}")
                    logger.info(f"   Change: {change_type}")
                    
                    if msg_type == "teams_chat_message":
                        chat_id = msg_data.get("chat_id", "unknown")
                        message_id = msg_data.get("message_id", "unknown")
                        logger.info(f"   Chat ID: {chat_id}")
                        logger.info(f"   Message ID: {message_id}")
                        
                        # This is where Annika would process the chat message
                        logger.info("   🤖 Annika could process this chat message here!")
                        
                    elif msg_type == "teams_channel_message":
                        team_id = msg_data.get("team_id", "unknown")
                        channel_id = msg_data.get("channel_id", "unknown")
                        message_id = msg_data.get("message_id", "unknown")
                        logger.info(f"   Team ID: {team_id}")
                        logger.info(f"   Channel ID: {channel_id}")
                        logger.info(f"   Message ID: {message_id}")
                        
                        # This is where Annika would process the channel message
                        logger.info("   🤖 Annika could process this channel message here!")
                    
                    logger.info()
                    
                except json.JSONDecodeError:
                    logger.warning(f"   Invalid JSON data: {data[:100]}...")
                    logger.info()
        
    except KeyboardInterrupt:
        logger.info("🛑 Stopped listening for messages")
    except Exception as e:
        logger.error(f"❌ Error listening for messages: {e}")
    finally:
        if 'redis_client' in locals():
            await redis_client.close()


async def show_message_history():
    """Show recent Teams message history."""
    logger.info("📚 Checking recent Teams message history...")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        
        # Check each history channel
        channels = [
            ("annika:teams:chat_messages:history", "Chat Messages"),
            ("annika:teams:channel_messages:history", "Channel Messages"),
            ("annika:teams:chats:history", "Chat Events"),
            ("annika:teams:channels:history", "Channel Events")
        ]
        
        for channel, name in channels:
            count = await redis_client.llen(channel)
            logger.info(f"   {name}: {count} messages")
            
            if count > 0:
                # Show latest message
                latest = await redis_client.lindex(channel, 0)
                if latest:
                    try:
                        msg = json.loads(latest)
                        timestamp = msg.get("timestamp", "unknown")
                        msg_type = msg.get("type", "unknown")
                        change_type = msg.get("change_type", "unknown")
                        
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp
                        
                        logger.info(f"     Latest: {time_str} - {change_type} {msg_type}")
                    except json.JSONDecodeError:
                        logger.info(f"     Latest: {latest[:50]}...")
        
        await redis_client.close()
        logger.info()
        
    except Exception as e:
        logger.error(f"❌ Error checking message history: {e}")


async def main():
    """Main function."""
    logger.info("🚀 Teams Message Listener for Annika")
    logger.info("=" * 50)
    
    # Show current message history
    await show_message_history()
    
    # Start listening for new messages
    await listen_for_chat_messages()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc() 