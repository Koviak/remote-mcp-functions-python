"""
Webhook Handler for Microsoft Graph Notifications

This module handles incoming webhook notifications from Microsoft Graph
and routes them to the appropriate sync services via Redis pub/sub.
"""

import json
import logging
import redis.asyncio as redis
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"


class GraphWebhookHandler:
    """Handle Microsoft Graph webhook notifications."""
    
    def __init__(self):
        self.redis_client = None
        
    async def initialize(self):
        """Initialize Redis connection."""
        self.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
    
    async def handle_webhook_notification(self, notification: Dict) -> bool:
        """
        Handle a webhook notification from Microsoft Graph.
        
        Args:
            notification: The webhook notification payload
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            # Validate notification
            if not self._validate_notification(notification):
                logger.warning("Invalid webhook notification received")
                return False
            
            # Extract notification details
            change_type = notification.get("changeType")
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            
            logger.info(
                f"📨 Webhook received: {change_type} for {resource} "
                f"(client: {client_state})"
            )
            
            # Route to appropriate handler based on resource type and client state
            if "/planner/tasks" in resource:
                await self._handle_planner_task_notification(notification)
            elif "/planner/plans" in resource:
                await self._handle_planner_plan_notification(notification)
            elif "/groups" in resource or "groups" in client_state:
                await self._handle_groups_notification(notification)
            elif "/chats" in resource or "teams_chats" in client_state:
                await self._handle_teams_chats_notification(notification)
            elif "/teams" in resource or "teams_channels" in client_state:
                await self._handle_teams_channels_notification(notification)
            else:
                logger.warning(
                    f"Unhandled resource type: {resource} "
                    f"with client state: {client_state}"
                )
                # Still log it for debugging
                await self._log_webhook_notification(notification)
                return True  # Don't fail for unknown types
            
            # Log the webhook for debugging
            await self._log_webhook_notification(notification)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling webhook notification: {e}")
            return False
    
    def _validate_notification(self, notification: Dict) -> bool:
        """Validate webhook notification structure."""
        required_fields = ["changeType", "resource"]
        
        for field in required_fields:
            if field not in notification:
                logger.warning(f"Missing required field: {field}")
                return False
        
        # Validate change type
        valid_change_types = ["created", "updated", "deleted"]
        if notification["changeType"] not in valid_change_types:
            logger.warning(
                f"Invalid change type: {notification['changeType']}"
            )
            return False
        
        return True
    
    async def _handle_planner_task_notification(self, notification: Dict):
        """Handle Planner task webhook notifications."""
        try:
            # Check client state to determine which sync service should handle this
            client_state = notification.get("clientState", "")
            
            if client_state == "annika_planner_sync_v5":
                # Route to V5 sync service
                await self.redis_client.publish(
                    "annika:planner:webhook",
                    json.dumps(notification)
                )
                logger.debug("Routed Planner task notification to V5 sync service")
            else:
                logger.warning(
                    f"Unknown client state for Planner task: {client_state}"
                )
                
        except Exception as e:
            logger.error(f"Error handling Planner task notification: {e}")
    
    async def _handle_planner_plan_notification(self, notification: Dict):
        """Handle Planner plan webhook notifications."""
        try:
            # For now, just log plan changes
            # You can extend this to handle plan-level changes
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            plan_id = resource_data.get("id", "unknown")
            
            logger.info(f"📋 Plan {change_type}: {plan_id}")
            
            # Could route to plan management service if needed
            # await self.redis_client.publish("annika:planner:plans", json.dumps(notification))
            
        except Exception as e:
            logger.error(f"Error handling Planner plan notification: {e}")
    
    async def _handle_groups_notification(self, notification: Dict):
        """Handle Groups webhook notifications - route to V5 sync service."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            group_id = resource_data.get("id", "unknown")
            
            logger.info(
                f"🏢 Group {change_type}: "
                f"{group_id[:8] if group_id != 'unknown' else group_id}"
            )
            
            # Route to V5 sync service for processing
            await self.redis_client.publish(
                "annika:planner:webhook",
                json.dumps(notification)
            )
            logger.debug("Routed Groups notification to V5 sync service")
            
        except Exception as e:
            logger.error(f"Error handling Groups notification: {e}")
    
    async def _handle_teams_chats_notification(self, notification: Dict):
        """Handle Teams chats webhook notifications - save to Redis channel."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            chat_id = resource_data.get("id", "unknown")
            client_state = notification.get("clientState", "")
            
            logger.info(f"💬 Teams chat {change_type}: {chat_id[:8] if chat_id != 'unknown' else chat_id}")
            
            # Extract message details if available
            resource = notification.get("resource", "")
            
            # Determine if this is a chat message notification
            if "/messages" in resource:
                await self._process_chat_message_notification(notification)
            else:
                # General chat notification (chat created/updated)
                await self._process_chat_notification(notification)
            
            # Route to V5 sync service for processing
            await self.redis_client.publish(
                "annika:planner:webhook",
                json.dumps(notification)
            )
            logger.debug("Routed Teams chats notification to V5 sync service")
            
        except Exception as e:
            logger.error(f"Error handling Teams chats notification: {e}")
    
    async def _process_chat_message_notification(self, notification: Dict):
        """Process a Teams chat message notification and save to Redis."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            
            # Extract chat and message IDs from resource path
            # Resource format: chats('chat-id')/messages('message-id')
            chat_id = "unknown"
            message_id = resource_data.get("id", "unknown")
            
            if "/chats/" in resource:
                # Extract chat ID from resource path
                import re
                chat_match = re.search(r"/chats/([^/]+)", resource)
                if chat_match:
                    chat_id = chat_match.group(1).strip("'\"()")
            
            # Create message notification for Annika
            message_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_chat_message",
                "change_type": change_type,
                "chat_id": chat_id,
                "message_id": message_id,
                "client_state": client_state,
                "resource": resource,
                "notification_id": notification.get("subscriptionId"),
                "raw_notification": notification
            }
            
            # Save to Redis channel for Annika to subscribe to
            await self.redis_client.publish(
                "annika:teams:chat_messages",
                json.dumps(message_notification)
            )
            
            # Also save to a list for history
            await self.redis_client.lpush(
                "annika:teams:chat_messages:history",
                json.dumps(message_notification)
            )
            
            # Keep only last 100 messages in history
            await self.redis_client.ltrim("annika:teams:chat_messages:history", 0, 99)
            
            logger.info(
                f"💬 Saved chat message notification: "
                f"chat={chat_id[:8]}, msg={message_id[:8]}, type={change_type}"
            )
            
        except Exception as e:
            logger.error(f"Error processing chat message notification: {e}")
    
    async def _process_chat_notification(self, notification: Dict):
        """Process a general Teams chat notification (chat created/updated)."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            chat_id = resource_data.get("id", "unknown")
            client_state = notification.get("clientState", "")
            
            # Create chat notification for Annika
            chat_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_chat",
                "change_type": change_type,
                "chat_id": chat_id,
                "client_state": client_state,
                "notification_id": notification.get("subscriptionId"),
                "raw_notification": notification
            }
            
            # Save to Redis channel for Annika to subscribe to
            await self.redis_client.publish(
                "annika:teams:chats",
                json.dumps(chat_notification)
            )
            
            # Also save to a list for history
            await self.redis_client.lpush(
                "annika:teams:chats:history",
                json.dumps(chat_notification)
            )
            
            # Keep only last 50 chat notifications in history
            await self.redis_client.ltrim("annika:teams:chats:history", 0, 49)
            
            logger.info(
                f"💬 Saved chat notification: "
                f"chat={chat_id[:8]}, type={change_type}"
            )
            
        except Exception as e:
            logger.error(f"Error processing chat notification: {e}")
    
    async def _handle_teams_channels_notification(self, notification: Dict):
        """Handle Teams channels webhook notifications - save to Redis channel."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            channel_id = resource_data.get("id", "unknown")
            client_state = notification.get("clientState", "")
            resource = notification.get("resource", "")

            logger.info(f"📺 Teams channel {change_type}: {channel_id[:8] if channel_id != 'unknown' else channel_id}")

            # Determine if this is a channel message notification
            if "/messages" in resource:
                await self._process_channel_message_notification(notification)
            else:
                # General channel notification (channel created/updated)
                await self._process_channel_notification(notification)

            # Route to V5 sync service for processing
            await self.redis_client.publish(
                "annika:planner:webhook",
                json.dumps(notification)
            )
            logger.debug("Routed Teams channels notification to V5 sync service")

        except Exception as e:
            logger.error(f"Error handling Teams channels notification: {e}")
    
    async def _process_channel_message_notification(self, notification: Dict):
        """Process a Teams channel message notification and save to Redis."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            
            # Extract team, channel, and message IDs from resource path
            # Resource format: teams('team-id')/channels('channel-id')/messages('message-id')
            team_id = "unknown"
            channel_id = "unknown"
            message_id = resource_data.get("id", "unknown")
            
            if "/teams/" in resource and "/channels/" in resource:
                import re
                team_match = re.search(r"/teams/([^/]+)", resource)
                channel_match = re.search(r"/channels/([^/]+)", resource)
                
                if team_match:
                    team_id = team_match.group(1).strip("'\"()")
                if channel_match:
                    channel_id = channel_match.group(1).strip("'\"()")
            
            # Create message notification for Annika
            message_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_channel_message",
                "change_type": change_type,
                "team_id": team_id,
                "channel_id": channel_id,
                "message_id": message_id,
                "client_state": client_state,
                "resource": resource,
                "notification_id": notification.get("subscriptionId"),
                "raw_notification": notification
            }
            
            # Save to Redis channel for Annika to subscribe to
            await self.redis_client.publish(
                "annika:teams:channel_messages",
                json.dumps(message_notification)
            )
            
            # Also save to a list for history
            await self.redis_client.lpush(
                "annika:teams:channel_messages:history",
                json.dumps(message_notification)
            )
            
            # Keep only last 100 messages in history
            await self.redis_client.ltrim("annika:teams:channel_messages:history", 0, 99)
            
            logger.info(
                f"📺 Saved channel message notification: "
                f"team={team_id[:8]}, channel={channel_id[:8]}, "
                f"msg={message_id[:8]}, type={change_type}"
            )
            
        except Exception as e:
            logger.error(f"Error processing channel message notification: {e}")
    
    async def _process_channel_notification(self, notification: Dict):
        """Process a general Teams channel notification (channel created/updated)."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            channel_id = resource_data.get("id", "unknown")
            client_state = notification.get("clientState", "")
            
            # Create channel notification for Annika
            channel_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_channel",
                "change_type": change_type,
                "channel_id": channel_id,
                "client_state": client_state,
                "notification_id": notification.get("subscriptionId"),
                "raw_notification": notification
            }
            
            # Save to Redis channel for Annika to subscribe to
            await self.redis_client.publish(
                "annika:teams:channels",
                json.dumps(channel_notification)
            )
            
            # Also save to a list for history
            await self.redis_client.lpush(
                "annika:teams:channels:history",
                json.dumps(channel_notification)
            )
            
            # Keep only last 50 channel notifications in history
            await self.redis_client.ltrim("annika:teams:channels:history", 0, 49)
            
            logger.info(
                f"📺 Saved channel notification: "
                f"channel={channel_id[:8]}, type={change_type}"
            )
            
        except Exception as e:
            logger.error(f"Error processing channel notification: {e}")
    
    async def _log_webhook_notification(self, notification: Dict):
        """Log webhook notification for debugging."""
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": notification.get("changeType"),
                "resource": notification.get("resource"),
                "resource_id": notification.get("resourceData", {}).get("id"),
                "client_state": notification.get("clientState"),
                "subscription_id": notification.get("subscriptionId")
            }
            
            await self.redis_client.lpush(
                "annika:webhook:log",
                json.dumps(log_entry)
            )
            
            # Keep only last 500 webhook logs
            await self.redis_client.ltrim("annika:webhook:log", 0, 499)
            
        except Exception as e:
            logger.error(f"Error logging webhook notification: {e}")
    
    async def handle_validation_request(self, validation_token: str) -> str:
        """
        Handle webhook validation request from Microsoft Graph.
        
        Args:
            validation_token: The validation token from Microsoft Graph
            
        Returns:
            str: The validation token to confirm subscription
        """
        logger.info(f"📋 Webhook validation request received: {validation_token}")
        return validation_token
    
    async def handle_batch_notifications(self, notifications: List[Dict]) -> bool:
        """
        Handle a batch of webhook notifications.
        
        Args:
            notifications: List of webhook notification payloads
            
        Returns:
            bool: True if all handled successfully, False otherwise
        """
        try:
            success_count = 0
            
            for notification in notifications:
                if await self.handle_webhook_notification(notification):
                    success_count += 1
            
            logger.info(f"📨 Processed {success_count}/{len(notifications)} webhook notifications")
            
            return success_count == len(notifications)
            
        except Exception as e:
            logger.error(f"Error handling batch notifications: {e}")
            return False
    
    async def get_webhook_health(self) -> Dict:
        """Get webhook handler health metrics."""
        try:
            # Get recent webhook logs
            recent_logs = await self.redis_client.lrange("annika:webhook:log", 0, 9)
            
            # Count notifications by type in last 10
            change_type_counts = {}
            resource_type_counts = {}
            for log_json in recent_logs:
                try:
                    log_entry = json.loads(log_json)
                    change_type = log_entry.get("change_type", "unknown")
                    resource = log_entry.get("resource", "unknown")
                    
                    change_type_counts[change_type] = change_type_counts.get(change_type, 0) + 1
                    
                    # Categorize resource types
                    if "/groups" in resource:
                        resource_type = "groups"
                    elif "/chats" in resource:
                        resource_type = "teams_chats"
                    elif "/teams" in resource:
                        resource_type = "teams_channels"
                    elif "/planner" in resource:
                        resource_type = "planner"
                    else:
                        resource_type = "other"
                    
                    resource_type_counts[resource_type] = resource_type_counts.get(resource_type, 0) + 1
                except:
                    continue
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "total_logs": await self.redis_client.llen("annika:webhook:log"),
                "recent_notifications": len(recent_logs),
                "change_type_counts": change_type_counts,
                "resource_type_counts": resource_type_counts,
                "status": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Error getting webhook health: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global webhook handler instance
webhook_handler = GraphWebhookHandler()


async def initialize_webhook_handler():
    """Initialize the global webhook handler."""
    await webhook_handler.initialize()


async def handle_graph_webhook(notification_data: Dict) -> bool:
    """
    Handle a Microsoft Graph webhook notification.
    
    This function is called by the Azure Function webhook endpoint.
    
    Args:
        notification_data: The webhook notification payload
        
    Returns:
        bool: True if handled successfully, False otherwise
    """
    return await webhook_handler.handle_webhook_notification(notification_data)


async def handle_webhook_validation(validation_token: str) -> str:
    """
    Handle webhook validation request.
    
    Args:
        validation_token: The validation token from Microsoft Graph
        
    Returns:
        str: The validation token to confirm subscription
    """
    return await webhook_handler.handle_validation_request(validation_token)


async def get_webhook_health() -> Dict:
    """Get webhook handler health metrics."""
    return await webhook_handler.get_webhook_health() 