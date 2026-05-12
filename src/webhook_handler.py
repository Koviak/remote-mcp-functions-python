"""
Webhook Handler for Microsoft Graph Notifications

This module handles incoming webhook notifications from Microsoft Graph
and routes them to the appropriate sync services via Redis pub/sub.
"""

import json
import logging
import re
import asyncio
import hashlib
from datetime import datetime
from typing import Dict, List

from Redis_Master_Manager_Client import get_async_redis_client, set_json_async

logger = logging.getLogger(__name__)

MAIL_MESSAGES_CHANNEL = "annika:mail:messages"
MAIL_MESSAGES_HISTORY_KEY = "annika:mail:messages:history"
MAIL_MESSAGES_HISTORY_MAX = 200
CONTACTS_CHANNEL = "annika:contacts:webhook"
CONTACTS_HISTORY_KEY = "annika:contacts:webhook:history"
CONTACTS_HISTORY_MAX = 200
CONTACTS_DEDUP_PREFIX = "annika:contacts:webhook:dedup:"
CONTACTS_DEDUP_TTL_SECONDS = 24 * 60 * 60
TEAMS_REVERSE_MAP_PREFIX = "annika:conversation_to_teams_chat:"
TEAMS_REVERSE_MAP_TTL_SECONDS = 30 * 24 * 60 * 60


def _deterministic_teams_conversation_id(chat_id: str) -> str:
    digest = hashlib.sha256(chat_id.encode("utf-8")).hexdigest()
    return f"CVteams_{digest[:16]}"


class GraphWebhookHandler:
    """Handle Microsoft Graph webhook notifications."""
    
    def __init__(self):
        self.redis_client = None
        self._redis_client_loop = None
        
    async def initialize(self, force_reconnect: bool = False):
        """Initialize Redis connection bound to the current event loop."""
        self.redis_client = await get_async_redis_client(
            force_reconnect=force_reconnect
        )
        if self.redis_client is None:
            raise RuntimeError("Redis client unavailable for webhook handler")
        await self.redis_client.ping()
        self._redis_client_loop = asyncio.get_running_loop()

    async def _ensure_redis_client(self):
        """Ensure Redis client is present and bound to the current loop."""
        current_loop = asyncio.get_running_loop()
        stale_loop = (
            self._redis_client_loop is None
            or self._redis_client_loop is not current_loop
            or self._redis_client_loop.is_closed()
        )
        if self.redis_client is None or stale_loop:
            await self.initialize(force_reconnect=self.redis_client is not None)

    async def _ensure_teams_reverse_map(self, chat_id: str) -> str:
        """Create/update the reverse map used by AETP for Teams delivery."""
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id or normalized_chat_id == "unknown":
            return ""

        conversation_id = _deterministic_teams_conversation_id(normalized_chat_id)
        try:
            await set_json_async(
                self.redis_client,
                f"{TEAMS_REVERSE_MAP_PREFIX}{conversation_id}",
                {
                    "teams_chat_id": normalized_chat_id,
                    "last_used": datetime.utcnow().isoformat(),
                    "message_mode": "send",
                },
                expire_seconds=TEAMS_REVERSE_MAP_TTL_SECONDS,
            )
        except Exception as exc:
            logger.debug(
                "Failed to sync Teams reverse map for chat %s: %s",
                normalized_chat_id,
                exc,
            )
        return conversation_id
    
    async def handle_webhook_notification(self, notification: Dict) -> bool:
        """
        Handle a webhook notification from Microsoft Graph.
        
        Args:
            notification: The webhook notification payload
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            await self._ensure_redis_client()

            # Validate notification
            if not self._validate_notification(notification):
                logger.warning("Invalid webhook notification received")
                return False

            # Lifecycle events don't include changeType
            lifecycle_event = notification.get("lifecycleEvent")
            if lifecycle_event:
                sub_id = notification.get("subscriptionId")
                logger.info(
                    f"🔔 Lifecycle event '{lifecycle_event}' for subscription {sub_id}"
                )
                await self._log_webhook_notification(notification)
                return True
            
            # Extract notification details
            change_type = notification.get("changeType")
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            resource_l = resource.lower()
            client_state_l = client_state.lower()
            
            logger.info(
                f"📨 Webhook received: {change_type} for {resource} "
                f"(client: {client_state})"
            )
            
            # Route to appropriate handler based on resource type and client state
            if "/planner/tasks" in resource_l:
                await self._handle_planner_task_notification(notification)
            elif "/planner/plans" in resource_l:
                await self._handle_planner_plan_notification(notification)
            elif "/groups" in resource_l or "groups" in client_state_l:
                await self._handle_groups_notification(notification)
            elif self._is_mail_message_resource(resource_l) or "mail_messages" in client_state_l:
                await self._handle_mail_notification(notification)
            elif self._is_contact_resource(resource_l) or "contacts" in client_state_l:
                await self._handle_contacts_notification(notification)
            elif (
                "/chats" in resource_l
                or resource_l.startswith("chats(")
                or "teams_chats" in client_state_l
                or "chat_global" in client_state_l
            ):
                await self._handle_teams_chats_notification(notification)
            elif (
                "/teams" in resource_l
                or resource_l.startswith("teams(")
                or "teams_channels" in client_state_l
            ):
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
        # Lifecycle events (e.g., reauthorizationRequired) may omit changeType
        if "lifecycleEvent" in notification:
            if "resource" not in notification:
                logger.warning("Missing required field: resource")
                return False
            return True

        required_fields = ["changeType", "resource"]

        for field in required_fields:
            if field not in notification:
                logger.warning(f"Missing required field: {field}")
                return False

        valid_change_types = ["created", "updated", "deleted"]
        if notification["changeType"] not in valid_change_types:
            logger.warning(
                f"Invalid change type: {notification['changeType']}"
            )
            return False

        return True

    def _is_mail_message_resource(self, resource: str) -> bool:
        """Return True when a Graph webhook resource points to Outlook mail messages."""
        if not resource:
            return False

        resource_l = resource.lower()

        # Exclude Teams chat/channel message resources.
        if (
            "/chats" in resource_l
            or "chats(" in resource_l
            or "/teams" in resource_l
            or "teams(" in resource_l
        ):
            return False

        return (
            "/me/messages" in resource_l
            or ("/users/" in resource_l and "/messages" in resource_l)
            or ("/mailfolders/" in resource_l and "/messages" in resource_l)
            or ("users(" in resource_l and "/messages(" in resource_l)
            or ("mailfolders(" in resource_l and "/messages(" in resource_l)
        )

    def _extract_message_id(self, notification: Dict) -> str:
        """Extract the message id from resourceData first, then resource path fallback."""
        resource_data = notification.get("resourceData", {}) or {}
        resource_id = resource_data.get("id")
        if resource_id:
            return str(resource_id)

        resource = notification.get("resource", "") or ""
        patterns = [
            r"/messages/([^/]+)$",
            r"/messages\('([^']+)'\)",
            r"messages\('([^']+)'\)",
            r"/messages\(([^)]+)\)",
        ]
        for pattern in patterns:
            match = re.search(pattern, resource, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip("'\"()")

        return ""

    def _is_contact_resource(self, resource: str) -> bool:
        """Return True when a Graph webhook resource points to contacts."""
        if not resource:
            return False
        resource_l = resource.lower()
        return (
            "/me/contacts" in resource_l
            or ("/users/" in resource_l and "/contacts" in resource_l)
            or ("contacts(" in resource_l)
        )

    def _extract_contact_id(self, notification: Dict) -> str:
        """Extract contact id from resourceData first, then resource path fallback."""
        resource_data = notification.get("resourceData", {}) or {}
        resource_id = resource_data.get("id")
        if resource_id:
            return str(resource_id)
        resource = notification.get("resource", "") or ""
        patterns = [
            r"/contacts/([^/]+)$",
            r"/contacts\('([^']+)'\)",
            r"contacts\('([^']+)'\)",
            r"/contacts\(([^)]+)\)",
        ]
        for pattern in patterns:
            match = re.search(pattern, resource, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip("'\"()")
        return ""

    async def _handle_mail_notification(self, notification: Dict):
        """Handle Outlook message webhook notifications."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            message_id = self._extract_message_id(notification)

            logger.info(
                "Mail message %s: id=%s resource=%s",
                change_type,
                message_id or "unknown",
                resource,
            )

            message_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "mail_message",
                "change_type": change_type,
                "message_id": message_id,
                "resource": resource,
                "resource_data": resource_data,
                "client_state": client_state,
                "subscription_id": notification.get("subscriptionId"),
                "tenant_id": notification.get("tenantId"),
                "raw_notification": notification,
            }

            await self.redis_client.publish(
                MAIL_MESSAGES_CHANNEL,
                json.dumps(message_notification),
            )
            await self.redis_client.lpush(
                MAIL_MESSAGES_HISTORY_KEY,
                json.dumps(message_notification),
            )
            await self.redis_client.ltrim(
                MAIL_MESSAGES_HISTORY_KEY, 0, MAIL_MESSAGES_HISTORY_MAX - 1
            )
        except Exception as e:
            logger.error(f"Error handling mail notification: {e}")

    async def _handle_contacts_notification(self, notification: Dict):
        """Handle Outlook contacts webhook notifications."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            contact_id = self._extract_contact_id(notification)
            subscription_id = notification.get("subscriptionId")
            dedup_key = (
                f"{CONTACTS_DEDUP_PREFIX}{subscription_id}:{contact_id}:{change_type}"
            )

            if hasattr(self.redis_client, "get"):
                already_seen = await self.redis_client.get(dedup_key)
                if already_seen:
                    logger.debug(
                        "Skipping duplicate contacts notification: %s",
                        dedup_key,
                    )
                    return

            contact_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "contact",
                "change_type": change_type,
                "contact_id": contact_id,
                "resource": resource,
                "resource_data": resource_data,
                "client_state": client_state,
                "subscription_id": subscription_id,
                "tenant_id": notification.get("tenantId"),
                "raw_notification": notification,
            }

            await self.redis_client.publish(
                CONTACTS_CHANNEL,
                json.dumps(contact_notification),
            )
            await self.redis_client.lpush(
                CONTACTS_HISTORY_KEY,
                json.dumps(contact_notification),
            )
            await self.redis_client.ltrim(
                CONTACTS_HISTORY_KEY, 0, CONTACTS_HISTORY_MAX - 1
            )

            if hasattr(self.redis_client, "setex"):
                await self.redis_client.setex(
                    dedup_key,
                    CONTACTS_DEDUP_TTL_SECONDS,
                    "1",
                )
            elif hasattr(self.redis_client, "set"):
                await self.redis_client.set(dedup_key, "1")
                if hasattr(self.redis_client, "expire"):
                    await self.redis_client.expire(
                        dedup_key,
                        CONTACTS_DEDUP_TTL_SECONDS,
                    )
        except Exception as e:
            logger.error(f"Error handling contacts notification: {e}")
    
    async def _handle_planner_task_notification(self, notification: Dict):
        """Handle Planner task webhook notifications."""
        try:
            # Check client state to determine which sync service should handle this
            client_state = notification.get("clientState", "")
            
            if client_state == "annika_planner_sync_v5":
                # Route to V5 sync service
                await self.redis_client.publish(
                    "annika:planner:webhook",
                    json.dumps({
                        "changeType": notification.get("changeType"),
                        "resource": notification.get("resource"),
                        "resourceData": notification.get("resourceData", {}),
                        "clientState": client_state,
                        "subscriptionId": notification.get("subscriptionId"),
                    })
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
            
            # Extract chat ID from resource path
            chat_match = re.search(r"/chats/([^/]+)", resource, flags=re.IGNORECASE)
            if not chat_match:
                chat_match = re.search(
                    r"chats\('([^']+)'\)",
                    resource,
                    flags=re.IGNORECASE,
                )
            if chat_match:
                chat_id = chat_match.group(1).strip("'\"()")

            # Extract message ID from resource path if resourceData.id is absent.
            if message_id == "unknown":
                message_match = re.search(
                    r"/messages/([^/]+)",
                    resource,
                    flags=re.IGNORECASE,
                )
                if not message_match:
                    message_match = re.search(
                        r"messages\('([^']+)'\)",
                        resource,
                        flags=re.IGNORECASE,
                    )
                if message_match:
                    message_id = message_match.group(1).strip("'\"()")
            
            conversation_id = await self._ensure_teams_reverse_map(chat_id)

            # Create message notification for Annika
            message_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_chat_message",
                "change_type": change_type,
                "chat_id": chat_id,
                "message_id": message_id,
                "conversation_id": conversation_id or None,
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
            
            conversation_id = await self._ensure_teams_reverse_map(chat_id)

            # Create chat notification for Annika
            chat_notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "teams_chat",
                "change_type": change_type,
                "chat_id": chat_id,
                "conversation_id": conversation_id or None,
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

            if change_type == "created" and chat_id != "unknown":
                try:
                    from chat_subscription_manager import chat_subscription_manager

                    await chat_subscription_manager.handle_new_chat_created(chat_id)
                except Exception as e:
                    logger.error(f"Chat subscription manager error: {e}")

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
            
            team_match = re.search(r"/teams/([^/]+)", resource, flags=re.IGNORECASE)
            channel_match = re.search(
                r"/channels/([^/]+)",
                resource,
                flags=re.IGNORECASE,
            )
            if not team_match:
                team_match = re.search(
                    r"teams\('([^']+)'\)",
                    resource,
                    flags=re.IGNORECASE,
                )
            if not channel_match:
                channel_match = re.search(
                    r"channels\('([^']+)'\)",
                    resource,
                    flags=re.IGNORECASE,
                )

            if team_match:
                team_id = team_match.group(1).strip("'\"()")
            if channel_match:
                channel_id = channel_match.group(1).strip("'\"()")

            # Extract message ID from resource path if resourceData.id is absent.
            if message_id == "unknown":
                message_match = re.search(
                    r"/messages/([^/]+)",
                    resource,
                    flags=re.IGNORECASE,
                )
                if not message_match:
                    message_match = re.search(
                        r"messages\('([^']+)'\)",
                        resource,
                        flags=re.IGNORECASE,
                    )
                if message_match:
                    message_id = message_match.group(1).strip("'\"()")
            
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
            # Ensure Redis client is valid for the current event loop.
            await self._ensure_redis_client()
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": notification.get("changeType"),
                "resource": notification.get("resource"),
                "resource_id": notification.get("resourceData", {}).get("id"),
                "client_state": notification.get("clientState"),
                "subscription_id": notification.get("subscriptionId"),
                "lifecycle_event": notification.get("lifecycleEvent")
            }
            
            await self.redis_client.lpush(
                "annika:webhook:log",
                json.dumps(log_entry)
            )

            # Keep only last 500 webhook logs
            await self.redis_client.ltrim("annika:webhook:log", 0, 499)

            # Store notifications with a 1-hour TTL for monitoring
            await self.redis_client.lpush(
                "annika:webhooks:notifications",
                json.dumps(log_entry)
            )
            await self.redis_client.expire("annika:webhooks:notifications", 3600)

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
            await self._ensure_redis_client()
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
                    elif "/chats" in resource or "chats(" in resource:
                        resource_type = "teams_chats"
                    elif "/teams" in resource or "teams(" in resource:
                        resource_type = "teams_channels"
                    elif "/planner" in resource:
                        resource_type = "planner"
                    elif self._is_mail_message_resource(resource):
                        resource_type = "mail_messages"
                    elif self._is_contact_resource(resource):
                        resource_type = "contacts"
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
            self.redis_client = None
            self._redis_client_loop = None


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
