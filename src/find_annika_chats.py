#!/usr/bin/env python3
"""
Find Annika's Teams Chats and Set Up Individual Subscriptions

This script finds all Teams chats that Annika is part of and sets up
individual webhook subscriptions for each chat.
"""

import json
import logging
import sys
import os
import requests
from datetime import datetime, timedelta

# Add src directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_auth_manager import get_agent_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
WEBHOOK_URL = "https://agency-swarm.ngrok.app/api/graph_webhook"


def find_annika_chats():
    """Find all Teams chats that Annika is part of."""
    logger.info("🔍 Finding Teams chats for Annika...")
    
    try:
        # Get token for Annika
        token = get_agent_token()
        if not token:
            logger.error("❌ Could not get token for Annika")
            return []
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Get all chats Annika is part of
        logger.info("📱 Getting all chats...")
        chats_url = f"{GRAPH_API_ENDPOINT}/me/chats"
        
        response = requests.get(chats_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            chats_data = response.json()
            chats = chats_data.get("value", [])
            
            logger.info(f"✅ Found {len(chats)} chats")
            
            for i, chat in enumerate(chats, 1):
                chat_id = chat.get("id", "unknown")
                chat_type = chat.get("chatType", "unknown")
                topic = chat.get("topic", "No topic")
                created = chat.get("createdDateTime", "unknown")
                
                logger.info(f"{i}. Chat ID: {chat_id}")
                logger.info(f"   Type: {chat_type}")
                logger.info(f"   Topic: {topic}")
                logger.info(f"   Created: {created}")
                
                # Get chat members to see who's in the chat
                try:
                    members_url = f"{GRAPH_API_ENDPOINT}/me/chats/{chat_id}/members"
                    members_response = requests.get(members_url, headers=headers, timeout=10)
                    
                    if members_response.status_code == 200:
                        members_data = members_response.json()
                        members = members_data.get("value", [])
                        
                        logger.info(f"   Members ({len(members)}):")
                        for member in members:
                            display_name = member.get("displayName", "Unknown")
                            email = member.get("email", "No email")
                            logger.info(f"     - {display_name} ({email})")
                    else:
                        logger.warning(f"   Could not get members: {members_response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"   Error getting members: {e}")
                
                logger.info("")  # Empty line for readability
                
            return chats
            
        else:
            logger.error(f"❌ Failed to get chats: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error finding chats: {e}")
        return []


def create_chat_subscription(chat_id: str, token: str):
    """Create a webhook subscription for a specific chat."""
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Create subscription for this specific chat's messages
        subscription_data = {
            "changeType": "created,updated",
            "notificationUrl": WEBHOOK_URL,
            "resource": f"/chats/{chat_id}/messages",
            "expirationDateTime": (
                datetime.utcnow() + timedelta(hours=23)
            ).isoformat() + "Z",
            "clientState": f"annika_chat_{chat_id[:8]}",
            "lifecycleNotificationUrl": WEBHOOK_URL
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/subscriptions",
            headers=headers,
            json=subscription_data,
            timeout=30
        )
        
        if response.status_code == 201:
            subscription = response.json()
            subscription_id = subscription.get("id")
            logger.info(f"✅ Created subscription for chat {chat_id[:8]}: {subscription_id}")
            return subscription_id
        else:
            logger.error(f"❌ Failed to create subscription for chat {chat_id[:8]}: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating subscription for chat {chat_id}: {e}")
        return None


def setup_individual_chat_subscriptions():
    """Set up individual webhook subscriptions for each of Annika's chats."""
    logger.info("🚀 Setting up individual chat subscriptions...")
    
    # Find all chats
    chats = find_annika_chats()
    
    if not chats:
        logger.warning("⚠️ No chats found - cannot set up subscriptions")
        return
    
    # Get token for creating subscriptions
    token = get_agent_token()
    if not token:
        logger.error("❌ Could not get token for creating subscriptions")
        return
    
    logger.info(f"🔔 Creating individual subscriptions for {len(chats)} chats...")
    
    successful_subscriptions = 0
    
    for chat in chats:
        chat_id = chat.get("id")
        if chat_id:
            subscription_id = create_chat_subscription(chat_id, token)
            if subscription_id:
                successful_subscriptions += 1
    
    logger.info(f"✅ Created {successful_subscriptions}/{len(chats)} chat subscriptions")
    
    if successful_subscriptions > 0:
        logger.info("💬 Individual chat subscriptions are now active!")
        logger.info("📱 Send a Teams message to Annika to test the new subscriptions")
    else:
        logger.warning("⚠️ No subscriptions were created successfully")


def main():
    """Main function."""
    logger.info("🚀 Starting individual Teams chat subscription setup...")
    
    setup_individual_chat_subscriptions()
    
    logger.info("✅ Setup complete!")


if __name__ == "__main__":
    main() 