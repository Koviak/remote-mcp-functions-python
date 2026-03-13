"""
Microsoft Graph Subscription Manager

Manages webhook subscriptions for Graph resources
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
import requests
from agent_auth_manager import get_agent_token
from mcp_redis_config import get_redis_token_manager

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
WEBHOOK_URL = os.environ.get(
    "GRAPH_WEBHOOK_URL", 
    "https://agency-swarm.ngrok.app/api/graph_webhook"
)
CLIENT_STATE = os.environ.get("GRAPH_WEBHOOK_CLIENT_STATE", "annika-secret")
MAIL_CLIENT_STATE = os.environ.get(
    "GRAPH_WEBHOOK_MAIL_CLIENT_STATE",
    "annika_mail_messages",
)
CONTACTS_CLIENT_STATE = os.environ.get(
    "GRAPH_WEBHOOK_CONTACTS_CLIENT_STATE",
    "annika_contacts",
)


def _normalize_mailbox_user_id(value: Optional[str]) -> str:
    if not value:
        return ""
    candidate = str(value).strip().strip("'\"")
    if not candidate:
        return ""
    if "@" in candidate:
        return candidate.lower()
    return candidate


def _parse_graph_datetime_utc(value: str) -> datetime:
    """Parse Graph datetime string as timezone-aware UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class GraphSubscriptionManager:
    """Manages Microsoft Graph webhook subscriptions"""
    
    def __init__(self):
        self.redis_manager = get_redis_token_manager()
        self.subscriptions = {}

    @staticmethod
    def _configured_mailbox_user_ids() -> List[str]:
        configured: List[str] = []
        seen: set[str] = set()

        def _append(value: Optional[str]) -> None:
            normalized = _normalize_mailbox_user_id(value)
            if not normalized:
                return
            if normalized in seen:
                return
            seen.add(normalized)
            configured.append(normalized)

        for item in os.environ.get("OUTLOOK_SYNC_MAILBOX_USER_IDS", "").split(","):
            _append(item)
        _append(os.environ.get("OUTLOOK_SYNC_MAILBOX_USER_ID"))
        return configured

    @classmethod
    def _configured_mail_subscription_resources(cls) -> List[str]:
        mailbox_user_ids = cls._configured_mailbox_user_ids()
        if mailbox_user_ids:
            return [f"/users/{mailbox_user_id}/messages" for mailbox_user_id in mailbox_user_ids]
        return ["/me/messages"]

    @classmethod
    def _default_mail_subscription_resource(cls) -> str:
        return cls._configured_mail_subscription_resources()[0]

    @staticmethod
    def _is_outlook_mail_resource(resource: str) -> bool:
        resource_lower = resource.lower()
        if (
            "/chats" in resource_lower
            or "chats(" in resource_lower
            or "/teams" in resource_lower
            or "teams(" in resource_lower
        ):
            return False
        return (
            resource_lower == "/me/messages"
            or ("/users/" in resource_lower and "/messages" in resource_lower)
            or ("/mailfolders/" in resource_lower and "/messages" in resource_lower)
            or ("users(" in resource_lower and "/messages" in resource_lower)
            or ("mailfolders(" in resource_lower and "/messages" in resource_lower)
        )
    
    def create_mail_subscription(
        self,
        resource: Optional[str] = None,
        client_state: Optional[str] = None,
    ) -> Optional[str]:
        """Create subscription for Outlook mail message changes."""
        resource = resource or self._default_mail_subscription_resource()
        sub = self.create_subscription(
            resource=resource,
            client_state=client_state or MAIL_CLIENT_STATE,
        )
        if not sub:
            return None
        return str(sub.get("id") or "")

    def create_mail_subscriptions(
        self,
        resources: Optional[List[str]] = None,
        client_state: Optional[str] = None,
    ) -> Dict[str, str]:
        """Create subscriptions for all configured Outlook mailbox message resources."""
        created: Dict[str, str] = {}
        for resource in resources or self._configured_mail_subscription_resources():
            subscription_id = self.create_mail_subscription(
                resource=resource,
                client_state=client_state,
            )
            if subscription_id:
                created[resource] = subscription_id
        return created

    def create_user_subscription(self) -> Optional[str]:
        """Backward-compatible alias for mail message subscription."""
        return self.create_mail_subscription()

    def create_contacts_subscription(
        self,
        resource: str = "/me/contacts",
        client_state: Optional[str] = None,
    ) -> Optional[str]:
        """Create subscription for Outlook contact changes."""
        sub = self.create_subscription(
            resource=resource,
            client_state=client_state or CONTACTS_CLIENT_STATE,
        )
        if not sub:
            return None
        return str(sub.get("id") or "")
    
    def create_event_subscription(self) -> Optional[str]:
        """Create subscription for Annika's calendar events"""
        sub = self.create_subscription(
            resource="/me/events",
            client_state=CLIENT_STATE,
        )
        if not sub:
            return None
        return str(sub.get("id") or "")
    
    def create_group_subscriptions(self, group_ids: List[str]) -> Dict[str, str]:
        """Create subscriptions for groups Annika is member of"""
        token = get_agent_token()
        if not token:
            return {}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        created_subscriptions = {}
        
        for group_id in group_ids:
            # Subscribe to group changes
            subscription = {
                "changeType": "updated",
                "notificationUrl": WEBHOOK_URL,
                "resource": f"/groups/{group_id}",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(days=2)
                ).isoformat() + "Z",
                "clientState": CLIENT_STATE
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/subscriptions",
                headers=headers,
                json=subscription,
                timeout=10
            )
            
            if response.status_code == 201:
                sub = response.json()
                subscription_id = sub["id"]
                created_subscriptions[group_id] = subscription_id
                
                # Store in Redis
                self.redis_manager._client.setex(
                    f"annika:subscriptions:{subscription_id}",
                    int(timedelta(days=2).total_seconds()),
                    json.dumps(sub)
                )
                
                logger.info(
                    f"Created group subscription for {group_id}: "
                    f"{subscription_id}"
                )
        
        return created_subscriptions
    
    def create_teams_subscriptions(
            self, team_ids: List[str]
    ) -> Dict[str, Dict[str, str]]:
        """Create subscriptions for Teams resources"""
        token = get_agent_token()
        if not token:
            return {}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        created_subscriptions = {}
        
        for team_id in team_ids:
            team_subs = {}
            
            # Subscribe to channels
            channel_sub = {
                "changeType": "created,updated,deleted",
                "notificationUrl": WEBHOOK_URL,
                "resource": f"/teams/{team_id}/channels",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=4)
                ).isoformat() + "Z",
                "clientState": CLIENT_STATE
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/subscriptions",
                headers=headers,
                json=channel_sub,
                timeout=10
            )
            
            if response.status_code == 201:
                sub = response.json()
                team_subs["channels"] = sub["id"]
                self._store_subscription(sub)
            
            # Subscribe to chat messages (if allowed)
            chat_sub = {
                "changeType": "created,updated",
                "notificationUrl": WEBHOOK_URL,
                "resource": f"/teams/{team_id}/channels/getAllMessages",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=4)
                ).isoformat() + "Z",
                "clientState": CLIENT_STATE,
                "encryptionCertificate": None,  # Required for messages
                "encryptionCertificateId": None
            }
            
            # Note: Chat message subscriptions require additional setup
            # This is a placeholder - actual implementation needs certificate
            
            if team_subs:
                created_subscriptions[team_id] = team_subs
                logger.info(f"Created Teams subscriptions for {team_id}")
        
        return created_subscriptions
    
    def _store_subscription(self, subscription: Dict):
        """Store subscription in Redis"""
        subscription_id = subscription["id"]
        expires_on = subscription.get("expirationDateTime")
        if not expires_on:
            logger.warning(
                "Subscription %s missing expirationDateTime; skipping cache write",
                subscription_id,
            )
            return
        
        # Calculate TTL using timezone-aware UTC to avoid naive/aware subtraction.
        expire_time = _parse_graph_datetime_utc(expires_on)
        now_utc = datetime.now(timezone.utc)
        ttl = int((expire_time - now_utc).total_seconds())
        
        if ttl > 0:
            self.redis_manager._client.setex(
                f"annika:subscriptions:{subscription_id}",
                ttl,
                json.dumps(subscription)
            )

    def _load_cached_subscription(
        self,
        subscription_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load cached subscription payload from Redis."""
        try:
            raw_value = self.redis_manager._client.get(
                f"annika:subscriptions:{subscription_id}"
            )
            if not raw_value:
                return None
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            return json.loads(raw_value)
        except Exception as exc:
            logger.warning(
                "Failed to load cached subscription %s: %s",
                subscription_id,
                exc,
            )
            return None

    def _retire_cached_subscription(self, subscription_id: str) -> None:
        """Delete stale cached subscription entry."""
        try:
            self.redis_manager._client.delete(
                f"annika:subscriptions:{subscription_id}"
            )
        except Exception as exc:
            logger.warning(
                "Failed to retire cached subscription %s: %s",
                subscription_id,
                exc,
            )

    @staticmethod
    def _is_message_resource(resource: str) -> bool:
        resource_lower = resource.lower()
        return "messages" in resource_lower and (
            "/chats" in resource_lower
            or "/teams" in resource_lower
            or "getallmessages" in resource_lower
        )

    @staticmethod
    def _expiration_for_resource(resource: str) -> str:
        if GraphSubscriptionManager._is_message_resource(resource):
            # Chat and channel message subscriptions are short-lived.
            return (datetime.utcnow() + timedelta(hours=23)).isoformat() + "Z"
        return (datetime.utcnow() + timedelta(days=2)).isoformat() + "Z"

    @staticmethod
    def _default_client_state_for_resource(resource: str) -> str:
        resource_lower = resource.lower()
        if GraphSubscriptionManager._is_outlook_mail_resource(resource):
            return MAIL_CLIENT_STATE
        if resource_lower == "/me/contacts":
            return CONTACTS_CLIENT_STATE
        return CLIENT_STATE

    @staticmethod
    def _default_change_type_for_resource(resource: str) -> str:
        resource_lower = resource.lower()
        if GraphSubscriptionManager._is_message_resource(resource_lower):
            return "created,updated"
        if "/groups/" in resource_lower:
            return "updated"
        return "created,updated,deleted"

    def _find_existing_subscription(
        self,
        *,
        resource: str,
        client_state: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        desired_resource = str(resource or "").strip().lower()
        desired_client_state = str(client_state or "").strip().lower()
        for subscription in self.list_active_subscriptions():
            subscription_resource = str(subscription.get("resource") or "").strip().lower()
            subscription_client_state = str(subscription.get("clientState") or "").strip().lower()
            if subscription_resource != desired_resource:
                continue
            if desired_client_state and subscription_client_state != desired_client_state:
                continue
            return subscription
        return None

    def create_subscription(
        self,
        resource: str,
        *,
        client_state: Optional[str] = None,
        change_type: Optional[str] = None,
        lifecycle_notification_url: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a subscription for an arbitrary Graph resource intent."""
        desired_client_state = client_state or self._default_client_state_for_resource(resource)
        existing_subscription = self._find_existing_subscription(
            resource=resource,
            client_state=desired_client_state,
        )
        if existing_subscription:
            self._store_subscription(existing_subscription)
            logger.info(
                "Reusing existing subscription: %s (%s)",
                existing_subscription.get("id"),
                resource,
            )
            return existing_subscription

        token = get_agent_token()
        if not token:
            logger.error("Failed to get agent token")
            return None

        payload: Dict[str, Any] = {
            "changeType": change_type or self._default_change_type_for_resource(resource),
            "notificationUrl": WEBHOOK_URL,
            "resource": resource,
            "expirationDateTime": self._expiration_for_resource(resource),
            "clientState": desired_client_state,
        }
        if lifecycle_notification_url:
            payload["lifecycleNotificationUrl"] = lifecycle_notification_url

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/subscriptions",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code != 201:
            logger.error(
                "Failed to create subscription for resource %s: %s",
                resource,
                response.text,
            )
            return None

        sub = response.json()
        self._store_subscription(sub)
        logger.info(
            "Created subscription: %s (%s)",
            sub.get("id"),
            resource,
        )
        return sub

    def _recover_not_found_subscription(
        self,
        subscription_id: str,
        known_subscription: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retire stale subscription and recreate same intent."""
        cached_subscription = self._load_cached_subscription(subscription_id)
        source = known_subscription or cached_subscription or {}
        resource = source.get("resource")
        if not resource:
            self._retire_cached_subscription(subscription_id)
            return {
                "status": "failed",
                "reason": "missing_recovery_context",
            }

        recreated_subscription = self.create_subscription(
            resource=resource,
            client_state=source.get("clientState"),
            change_type=source.get("changeType"),
            lifecycle_notification_url=source.get("lifecycleNotificationUrl"),
        )
        self._retire_cached_subscription(subscription_id)
        if not recreated_subscription:
            return {
                "status": "failed",
                "reason": "recreate_failed",
                "resource": resource,
            }

        logger.info(
            "RETIRED_STALE_SUBSCRIPTION old_id=%s new_id=%s resource=%s client_state=%s",
            subscription_id,
            recreated_subscription.get("id"),
            resource,
            source.get("clientState"),
        )
        return {
            "status": "recovered_not_found",
            "old_id": subscription_id,
            "new_id": recreated_subscription.get("id"),
            "resource": resource,
        }

    def renew_subscription_detailed(
        self,
        subscription_id: str,
        known_subscription: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Renew an existing subscription with detailed status."""
        token = get_agent_token()
        if not token:
            return {"status": "failed", "reason": "missing_token"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        update_data = {
            "expirationDateTime": (
                datetime.utcnow() + timedelta(days=2)
            ).isoformat() + "Z"
        }
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
            headers=headers,
            json=update_data,
            timeout=10,
        )

        if response.status_code == 200:
            sub = response.json()
            self._store_subscription(sub)
            logger.info(
                "Renewed subscription: %s resource=%s client_state=%s",
                subscription_id,
                sub.get("resource"),
                sub.get("clientState"),
            )
            return {"status": "renewed"}

        response_text = response.text
        logger.error(
            "Failed to renew subscription: id=%s status=%s body=%s",
            subscription_id,
            response.status_code,
            response_text,
        )

        if (
            response.status_code == 404
            or "No subscription found" in response_text
            or "Status Code: NotFound" in response_text
        ):
            return self._recover_not_found_subscription(
                subscription_id,
                known_subscription=known_subscription,
            )

        return {
            "status": "failed",
            "status_code": response.status_code,
        }


    def renew_subscription(self, subscription_id: str) -> bool:
        """Renew an existing subscription"""
        result = self.renew_subscription_detailed(subscription_id)
        return result.get("status") in {"renewed", "recovered_not_found"}
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription"""
        token = get_agent_token()
        if not token:
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            # Remove from Redis
            self.redis_manager._client.delete(
                f"annika:subscriptions:{subscription_id}"
            )
            logger.info(f"Deleted subscription: {subscription_id}")
            return True
        else:
            logger.error(f"Failed to delete subscription: {response.text}")
            return False
    
    def list_active_subscriptions(self) -> List[Dict]:
        """List all active subscriptions"""
        token = get_agent_token()
        if not token:
            return []
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/subscriptions",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            logger.error(f"Failed to list subscriptions: {response.text}")
            return []
    
    def create_teams_chat_message_subscriptions(self) -> Dict[str, str]:
        """Create subscriptions for Teams chat messages that Annika is part of"""
        token = get_agent_token()
        if not token:
            logger.error("Failed to get agent token for chat message subscriptions")
            return {}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        created_subscriptions = {}
        
        # 1. Subscribe to all chats Annika is part of (user-level)
        user_chats_sub = {
            "changeType": "created,updated",
            "notificationUrl": WEBHOOK_URL,
            "resource": "/me/chats/getAllMessages",
            "expirationDateTime": (
                datetime.utcnow() + timedelta(hours=23)
            ).isoformat() + "Z",  # Max 24 hours for chat messages
            "clientState": "annika_user_chat_messages",
            "lifecycleNotificationUrl": WEBHOOK_URL  # Required for >1 hour
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/subscriptions",
            headers=headers,
            json=user_chats_sub,
            timeout=10
        )
        
        if response.status_code == 201:
            sub = response.json()
            subscription_id = sub["id"]
            created_subscriptions["user_chat_messages"] = subscription_id
            
            # Store in Redis
            self.redis_manager._client.setex(
                f"annika:subscriptions:{subscription_id}",
                int(timedelta(hours=23).total_seconds()),
                json.dumps(sub)
            )
            
            logger.info(
                f"✅ Created user chat messages subscription: {subscription_id}"
            )
        else:
            logger.error(
                f"❌ Failed to create user chat messages subscription: "
                f"{response.text}"
            )
        
        # 2. Subscribe to all chats in the tenant (if app permissions)
        try:
            tenant_chats_sub = {
                "changeType": "created,updated",
                "notificationUrl": WEBHOOK_URL,
                "resource": "/chats/getAllMessages",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=23)
                ).isoformat() + "Z",
                "clientState": "annika_tenant_chat_messages",
                "lifecycleNotificationUrl": WEBHOOK_URL
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/subscriptions",
                headers=headers,
                json=tenant_chats_sub,
                timeout=10
            )
            
            if response.status_code == 201:
                sub = response.json()
                subscription_id = sub["id"]
                created_subscriptions["tenant_chat_messages"] = subscription_id
                
                self.redis_manager._client.setex(
                    f"annika:subscriptions:{subscription_id}",
                    int(timedelta(hours=23).total_seconds()),
                    json.dumps(sub)
                )
                
                logger.info(
                    f"✅ Created tenant chat messages subscription: "
                    f"{subscription_id}"
                )
            else:
                logger.warning(
                    f"⚠️ Could not create tenant chat messages subscription "
                    f"(may need app permissions): {response.status_code}"
                )
        except Exception as e:
            logger.warning(
                f"⚠️ Tenant chat subscription failed "
                f"(expected if no app permissions): {e}"
            )
        
        # 3. Subscribe to specific chats Annika is part of
        try:
            # Get Annika's chats first
            chats_response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/chats",
                headers=headers,
                timeout=10
            )
            
            if chats_response.status_code == 200:
                chats = chats_response.json().get("value", [])
                logger.info(f"Found {len(chats)} chats for Annika")
                
                # Subscribe to messages in each chat (limit to 10 most recent)
                for chat in chats[:10]:
                    chat_id = chat["id"]
                    chat_sub = {
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
                        json=chat_sub,
                        timeout=10
                    )
                    
                    if response.status_code == 201:
                        sub = response.json()
                        subscription_id = sub["id"]
                        created_subscriptions[f"chat_{chat_id[:8]}"] = subscription_id
                        
                        self.redis_manager._client.setex(
                            f"annika:subscriptions:{subscription_id}",
                            int(timedelta(hours=23).total_seconds()),
                            json.dumps(sub)
                        )
                        
                        logger.info(f"✅ Created chat subscription for {chat_id[:8]}: {subscription_id}")
                    else:
                        logger.warning(f"⚠️ Failed to create subscription for chat {chat_id[:8]}: {response.status_code}")
            
        except Exception as e:
            logger.error(f"❌ Error setting up individual chat subscriptions: {e}")
        
        return created_subscriptions

    def create_teams_channel_message_subscriptions(self) -> Dict[str, str]:
        """Create subscriptions for Teams channel messages in teams Annika is part of"""
        token = get_agent_token()
        if not token:
            return {}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        created_subscriptions = {}
        
        # 1. Subscribe to all channel messages in the tenant (if we have permissions)
        try:
            tenant_channels_sub = {
                "changeType": "created,updated",
                "notificationUrl": WEBHOOK_URL,
                "resource": "/teams/getAllMessages",
                "expirationDateTime": (
                    datetime.utcnow() + timedelta(hours=23)
                ).isoformat() + "Z",
                "clientState": "annika_tenant_channel_messages",
                "lifecycleNotificationUrl": WEBHOOK_URL
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/subscriptions",
                headers=headers,
                json=tenant_channels_sub,
                timeout=10
            )
            
            if response.status_code == 201:
                sub = response.json()
                subscription_id = sub["id"]
                created_subscriptions["tenant_channel_messages"] = subscription_id
                
                self.redis_manager._client.setex(
                    f"annika:subscriptions:{subscription_id}",
                    int(timedelta(hours=23).total_seconds()),
                    json.dumps(sub)
                )
                
                logger.info(f"✅ Created tenant channel messages subscription: {subscription_id}")
            else:
                logger.warning(f"⚠️ Could not create tenant channel messages subscription: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Tenant channel subscription failed: {e}")
        
        # 2. Subscribe to specific teams/channels Annika is part of
        try:
            # Get teams Annika is member of
            teams_response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/joinedTeams",
                headers=headers,
                timeout=10
            )
            
            if teams_response.status_code == 200:
                teams = teams_response.json().get("value", [])
                logger.info(f"Found {len(teams)} teams for Annika")
                
                # Subscribe to messages in each team (limit to 5 teams)
                for team in teams[:5]:
                    team_id = team["id"]
                    team_name = team.get("displayName", "Unknown")
                    
                    # Get channels for this team
                    channels_response = requests.get(
                        f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels",
                        headers=headers,
                        timeout=10
                    )
                    
                    if channels_response.status_code == 200:
                        channels = channels_response.json().get("value", [])
                        
                        # Subscribe to messages in each channel (limit to 3 channels per team)
                        for channel in channels[:3]:
                            channel_id = channel["id"]
                            channel_name = channel.get("displayName", "Unknown")
                            
                            channel_sub = {
                                "changeType": "created,updated",
                                "notificationUrl": WEBHOOK_URL,
                                "resource": f"/teams/{team_id}/channels/{channel_id}/messages",
                                "expirationDateTime": (
                                    datetime.utcnow() + timedelta(hours=23)
                                ).isoformat() + "Z",
                                "clientState": f"annika_team_{team_id[:8]}_channel_{channel_id[:8]}",
                                "lifecycleNotificationUrl": WEBHOOK_URL
                            }
                            
                            response = requests.post(
                                f"{GRAPH_API_ENDPOINT}/subscriptions",
                                headers=headers,
                                json=channel_sub,
                                timeout=10
                            )
                            
                            if response.status_code == 201:
                                sub = response.json()
                                subscription_id = sub["id"]
                                key = f"team_{team_id[:8]}_channel_{channel_id[:8]}"
                                created_subscriptions[key] = subscription_id
                                
                                self.redis_manager._client.setex(
                                    f"annika:subscriptions:{subscription_id}",
                                    int(timedelta(hours=23).total_seconds()),
                                    json.dumps(sub)
                                )
                                
                                logger.info(f"✅ Created channel subscription for {team_name}/{channel_name}: {subscription_id}")
                            else:
                                logger.warning(f"⚠️ Failed to create subscription for {team_name}/{channel_name}: {response.status_code}")
        
        except Exception as e:
            logger.error(f"❌ Error setting up team channel subscriptions: {e}")
        
        return created_subscriptions

    def setup_annika_subscriptions(self):
        """Set up all necessary subscriptions for Annika"""
        logger.info("Setting up Annika's webhook subscriptions...")
        
        # 1. Subscribe to Annika's user resources
        self.create_mail_subscriptions()
        self.create_contacts_subscription()
        self.create_event_subscription()
        
        # 2. Subscribe to Teams chat messages
        logger.info("🔔 Setting up Teams chat message subscriptions...")
        chat_subs = self.create_teams_chat_message_subscriptions()
        logger.info(f"Created {len(chat_subs)} chat message subscriptions")
        
        # 3. Subscribe to Teams channel messages
        logger.info("📺 Setting up Teams channel message subscriptions...")
        channel_subs = self.create_teams_channel_message_subscriptions()
        logger.info(f"Created {len(channel_subs)} channel message subscriptions")
        
        # 4. Get groups Annika is member of
        token = get_agent_token()
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/memberOf",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                groups = response.json().get("value", [])
                group_ids = [
                    g["id"] for g in groups 
                    if g["@odata.type"] == "#microsoft.graph.group"
                ]
                
                # Subscribe to these groups (limit to 10 for now)
                if group_ids:
                    self.create_group_subscriptions(group_ids[:10])
                
                # Check for teams
                team_ids = []
                for group in groups:
                    if "Team" in group.get("resourceProvisioningOptions", []):
                        team_ids.append(group["id"])
                
                # Subscribe to teams (limit to 5 for now)
                if team_ids:
                    self.create_teams_subscriptions(team_ids[:5])
        
        logger.info("Webhook subscription setup completed")
    
    def renew_all_subscriptions(self):
        """Renew all active subscriptions"""
        logger.info("Renewing all subscriptions...")

        subscriptions = self.list_active_subscriptions()
        renewed = 0
        recovered_not_found = 0
        failed = 0

        for sub in subscriptions:
            result = self.renew_subscription_detailed(
                sub["id"],
                known_subscription=sub,
            )
            if result.get("status") == "renewed":
                renewed += 1
            elif result.get("status") == "recovered_not_found":
                recovered_not_found += 1
            else:
                failed += 1

        logger.info(
            "Renewed %s subscriptions, %s recovered_not_found, %s failed",
            renewed,
            recovered_not_found,
            failed,
        )
        return {
            "renewed": renewed,
            "recovered_not_found": recovered_not_found,
            "failed": failed,
        } 
