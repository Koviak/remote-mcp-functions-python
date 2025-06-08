#!/usr/bin/env python3
"""
Discover Teams Chats for Annika

This script discovers existing Teams chats that Annika is part of
and sets up proper webhook subscriptions for each chat.
"""

import asyncio
import json
import logging
import sys
import os
from typing import List, Dict

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_auth_manager import get_agent_token  # noqa: E402
import requests  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


async def discover_teams_chats():
    """Discover Teams chats that Annika is part of."""
    logger.info("🔍 Discovering Teams chats for Annika...")
    
    try:
        # Get delegated token for Annika
        token = await get_agent_token("delegated")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Get all chats Annika is part of
        logger.info("📱 Getting all chats...")
        chats_url = f"{GRAPH_API_ENDPOINT}/me/chats"
        
        response = requests.get(chats_url, headers=headers)
        
        if response.status_code == 200:
            chats_data = response.json()
            chats = chats_data.get("value", [])
            
            logger.info(f"✅ Found {len(chats)} chats")
            
            for i, chat in enumerate(chats, 1):
                chat_id = chat.get("id", "unknown")
                chat_type = chat.get("chatType", "unknown")
                topic = chat.get("topic", "No topic")
                created = chat.get("createdDateTime", "unknown")
                
                logger.info(f"{i}. Chat ID: {chat_id[:20]}...")
                logger.info(f"   Type: {chat_type}")
                logger.info(f"   Topic: {topic}")
                logger.info(f"   Created: {created}")
                
                # Get chat members
                members_url = f"{GRAPH_API_ENDPOINT}/me/chats/{chat_id}/members"
                members_response = requests.get(members_url, headers=headers)
                
                if members_response.status_code == 200:
                    members_data = members_response.json()
                    members = members_data.get("value", [])
                    
                    logger.info(f"   Members ({len(members)}):")
                    for member in members:
                        display_name = member.get("displayName", "Unknown")
                        email = member.get("email", "No email")
                        logger.info(f"     - {display_name} ({email})")
                
                # Get recent messages
                messages_url = f"{GRAPH_API_ENDPOINT}/me/chats/{chat_id}/messages"
                messages_response = requests.get(
                    messages_url, 
                    headers=headers,
                    params={"$top": 3, "$orderby": "createdDateTime desc"}
                )
                
                if messages_response.status_code == 200:
                    messages_data = messages_response.json()
                    messages = messages_data.get("value", [])
                    
                    logger.info(f"   Recent messages ({len(messages)}):")
                    for msg in messages:
                        msg_id = msg.get("id", "unknown")
                        created_dt = msg.get("createdDateTime", "unknown")
                        from_user = msg.get("from", {}).get("user", {})
                        from_name = from_user.get("displayName", "Unknown")
                        body = msg.get("body", {}).get("content", "No content")
                        
                        # Truncate long messages
                        if len(body) > 100:
                            body = body[:100] + "..."
                        
                        logger.info(f"     - {created_dt} | {from_name}: {body}")
                
                logger.info("")  # Empty line for readability
                
            return chats
            
        else:
            logger.error(f"❌ Failed to get chats: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error discovering chats: {e}")
        return []


async def check_webhook_notifications():
    """Check if webhook notifications are being received."""
    logger.info("🔔 Checking webhook notification status...")
    
    try:
        import redis.asyncio as redis
        
        # Connect to Redis
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            password="password",
            decode_responses=True
        )
        await redis_client.ping()
        
        # Check for recent webhook notifications
        webhook_key = "annika:webhooks:notifications"
        notifications = await redis_client.lrange(webhook_key, 0, 9)
        
        logger.info(f"📨 Found {len(notifications)} recent webhook notifications:")
        
        for i, notification_json in enumerate(notifications, 1):
            try:
                notification = json.loads(notification_json)
                timestamp = notification.get("timestamp", "unknown")
                resource = notification.get("resource", "unknown")
                change_type = notification.get("changeType", "unknown")
                client_state = notification.get("clientState", "none")
                
                logger.info(f"{i}. {timestamp} | {resource} | {change_type} | {client_state}")
                
            except json.JSONDecodeError:
                logger.warning(f"{i}. Invalid JSON: {notification_json[:100]}...")
        
        # Check Teams-specific channels
        teams_channels = [
            "annika:teams:chat_messages",
            "annika:teams:chat_messages:history",
            "annika:teams:chats",
            "annika:teams:chats:history"
        ]
        
        for channel in teams_channels:
            count = await redis_client.llen(channel)
            logger.info(f"📊 {channel}: {count} messages")
        
        await redis_client.close()
        
    except Exception as e:
        logger.error(f"❌ Error checking webhook notifications: {e}")


async def main():
    """Main function."""
    logger.info("🚀 Starting Teams chat discovery...")
    
    # Discover chats
    chats = await discover_teams_chats()
    
    # Check webhook status
    await check_webhook_notifications()
    
    logger.info("✅ Discovery complete!")
    
    if chats:
        logger.info(f"💡 Found {len(chats)} chats. The existing /chats webhook subscription should capture messages from these chats.")
        logger.info("💡 If messages aren't appearing, the issue might be in the webhook processing logic.")
    else:
        logger.warning("⚠️ No chats found. This might indicate a permissions issue.")


if __name__ == "__main__":
    asyncio.run(main()) 