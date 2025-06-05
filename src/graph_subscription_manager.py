"""
Microsoft Graph Subscription Manager

Manages webhook subscriptions for Graph resources
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
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


class GraphSubscriptionManager:
    """Manages Microsoft Graph webhook subscriptions"""
    
    def __init__(self):
        self.redis_manager = get_redis_token_manager()
        self.subscriptions = {}
    
    def create_user_subscription(self) -> Optional[str]:
        """Create subscription for Annika's user changes"""
        token = get_agent_token()
        if not token:
            logger.error("Failed to get agent token")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Subscribe to messages for Annika
        subscription = {
            "changeType": "created,updated,deleted",
            "notificationUrl": WEBHOOK_URL,
            "resource": "/me/messages",
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
            
            # Store subscription info in Redis
            self.redis_manager._client.setex(
                f"annika:subscriptions:{subscription_id}",
                int(timedelta(days=2).total_seconds()),
                json.dumps(sub)
            )
            
            logger.info(f"Created user subscription: {subscription_id}")
            return subscription_id
        else:
            logger.error(f"Failed to create subscription: {response.text}")
            return None
    
    def create_event_subscription(self) -> Optional[str]:
        """Create subscription for Annika's calendar events"""
        token = get_agent_token()
        if not token:
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        subscription = {
            "changeType": "created,updated,deleted",
            "notificationUrl": WEBHOOK_URL,
            "resource": "/me/events",
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
            
            self.redis_manager._client.setex(
                f"annika:subscriptions:{subscription_id}",
                int(timedelta(days=2).total_seconds()),
                json.dumps(sub)
            )
            
            logger.info(f"Created event subscription: {subscription_id}")
            return subscription_id
        else:
            logger.error(
                f"Failed to create event subscription: {response.text}"
            )
            return None
    
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
        expires_on = subscription["expirationDateTime"]
        
        # Calculate TTL
        expire_time = datetime.fromisoformat(expires_on.replace("Z", "+00:00"))
        ttl = int((expire_time - datetime.utcnow()).total_seconds())
        
        if ttl > 0:
            self.redis_manager._client.setex(
                f"annika:subscriptions:{subscription_id}",
                ttl,
                json.dumps(subscription)
            )
    
    def renew_subscription(self, subscription_id: str) -> bool:
        """Renew an existing subscription"""
        token = get_agent_token()
        if not token:
            return False
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
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
            timeout=10
        )
        
        if response.status_code == 200:
            # Update Redis
            sub = response.json()
            self._store_subscription(sub)
            logger.info(f"Renewed subscription: {subscription_id}")
            return True
        else:
            logger.error(f"Failed to renew subscription: {response.text}")
            return False
    
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
    
    def setup_annika_subscriptions(self):
        """Set up all necessary subscriptions for Annika"""
        logger.info("Setting up Annika's webhook subscriptions...")
        
        # 1. Subscribe to Annika's user resources
        self.create_user_subscription()
        self.create_event_subscription()
        
        # 2. Get groups Annika is member of
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
        failed = 0
        
        for sub in subscriptions:
            if self.renew_subscription(sub["id"]):
                renewed += 1
            else:
                failed += 1
        
        logger.info(f"Renewed {renewed} subscriptions, {failed} failed")
        return {"renewed": renewed, "failed": failed} 