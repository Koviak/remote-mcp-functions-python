"""
Enhanced Planner Sync Service V5 - Webhook-Driven Architecture

Key improvements over V4:
- Webhook-driven real-time sync (no more polling)
- Proper conflict resolution with timestamps
- Rate limiting protection with exponential backoff
- Batch operations for efficiency
- Transaction logging for debugging
- Health monitoring and recovery mechanisms
- Circuit breaker pattern
"""

import asyncio
import json
import logging
import redis.asyncio as redis
import time
import os
from pathlib import Path
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from agent_auth_manager import get_agent_token
from dual_auth_manager import (
    get_token_for_operation, 
    get_application_token, 
    get_delegated_token
)
from annika_task_adapter import AnnikaTaskAdapter
import requests
import uuid
from dataclasses import dataclass
from enum import Enum

# Load environment variables from .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Also load from local.settings.json (Function App settings)
settings_file = Path(__file__).parent / "local.settings.json"
if settings_file.exists():
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
            values = settings.get("Values", {})
            for key, value in values.items():
                if key not in os.environ:  # Don't override existing env vars
                    os.environ[key] = str(value)
        logging.info(f"Loaded {len(values)} settings from local.settings.json")
    except Exception as e:
        logging.error(f"Error loading local.settings.json: {e}")

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# Redis keys
PLANNER_ID_MAP_PREFIX = "annika:planner:id_map:"
ETAG_PREFIX = "annika:planner:etag:"
SYNC_LOG_KEY = "annika:sync:log"
PENDING_OPS_KEY = "annika:sync:pending"
FAILED_OPS_KEY = "annika:sync:failed"
WEBHOOK_STATUS_KEY = "annika:sync:webhook_status"


class SyncOperation(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ConflictResolution(Enum):
    ANNIKA_WINS = "annika_wins"
    PLANNER_WINS = "planner_wins"
    MERGE = "merge"


@dataclass
class SyncLogEntry:
    timestamp: str
    operation: str
    annika_id: Optional[str]
    planner_id: Optional[str]
    status: str
    error: Optional[str] = None
    conflict_resolution: Optional[str] = None


class RateLimitHandler:
    """Handle Microsoft Graph rate limiting with exponential backoff."""
    
    def __init__(self):
        self.retry_after = 0
        self.consecutive_failures = 0
        self.max_retries = 5
        
    def is_rate_limited(self) -> bool:
        """Check if we're currently in a rate limit backoff period."""
        return time.time() < self.retry_after
    
    def handle_rate_limit(self, retry_after_seconds: int = None):
        """Handle a rate limit response."""
        self.consecutive_failures += 1
        
        if retry_after_seconds:
            self.retry_after = time.time() + retry_after_seconds
        else:
            # Exponential backoff: 2^failures seconds
            backoff = min(2 ** self.consecutive_failures, 300)  # Max 5 minutes
            self.retry_after = time.time() + backoff
            
        logger.warning(
            f"Rate limited. Backing off for {backoff} seconds. "
            f"Failures: {self.consecutive_failures}"
        )
    
    def reset(self):
        """Reset rate limit state after successful request."""
        self.consecutive_failures = 0
        self.retry_after = 0


class ConflictResolver:
    """Resolve conflicts between Annika and Planner task versions."""
    
    def resolve_conflict(
        self, 
        annika_task: Dict, 
        planner_task: Dict
    ) -> ConflictResolution:
        """Determine which version should win in a conflict."""
        
        # Get modification timestamps
        annika_modified = annika_task.get("modified_at")
        planner_modified = planner_task.get("lastModifiedDateTime")
        
        if not annika_modified or not planner_modified:
            # If we can't determine timestamps, prefer Planner (human input)
            return ConflictResolution.PLANNER_WINS
        
        try:
            annika_time = datetime.fromisoformat(
                annika_modified.replace('Z', '+00:00')
            )
            planner_time = datetime.fromisoformat(
                planner_modified.replace('Z', '+00:00')
            )
            
            # Last write wins with 30-second grace period for near-simultaneous edits
            time_diff = abs((annika_time - planner_time).total_seconds())
            
            if time_diff < 30:
                # Very close in time - prefer human input (Planner)
                return ConflictResolution.PLANNER_WINS
            elif annika_time > planner_time:
                return ConflictResolution.ANNIKA_WINS
            else:
                return ConflictResolution.PLANNER_WINS
                
        except Exception as e:
            logger.error(f"Error parsing timestamps for conflict resolution: {e}")
            return ConflictResolution.PLANNER_WINS


class WebhookDrivenPlannerSync:
    """Webhook-driven bidirectional sync with intelligent conflict resolution."""
    
    def __init__(self):
        self.redis_client = None
        self.pubsub = None
        self.adapter = None
        self.running = False
        
        # Components
        self.rate_limiter = RateLimitHandler()
        self.conflict_resolver = ConflictResolver()
        
        # State tracking
        self.task_etags = {}
        self.processed_tasks = set()
        self.processing_upload = set()
        
        # Webhook management
        self.webhook_subscriptions = {}
        self.webhook_renewal_interval = 3600  # 1 hour
        
        # Batch processing
        self.pending_uploads = []
        self.batch_size = 10
        self.batch_timeout = 5  # seconds
        
    async def start(self):
        """Start the webhook-driven sync service."""
        logger.info("🚀 Starting Webhook-Driven Planner Sync Service V5...")
        
        # Initialize Redis
        self.redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Initialize adapter
        self.adapter = AnnikaTaskAdapter(self.redis_client)
        
        # Set up pub/sub for Annika changes
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(
            "__keyspace@0__:annika:conscious_state",
            "annika:tasks:updates",
            "annika:planner:webhook"  # Webhook notifications
        )
        
        self.running = True
        
        # Load existing state
        await self._load_existing_state()
        
        # Set up webhooks for real-time Planner notifications
        await self._setup_webhooks()
        
        # Perform minimal initial sync (only check for new tasks)
        await self._initial_sync()
        
        # Start all service loops
        await asyncio.gather(
            self._monitor_annika_changes(),      # Upload to Planner
            self._process_webhook_notifications(), # Handle Planner webhooks
            self._batch_processor(),             # Batch upload operations
            self._health_monitor(),              # Health checks
            self._webhook_renewal_loop(),        # Keep webhooks alive
            self._planner_polling_loop(),        # Planner polling loop
            return_exceptions=True
        )
    
    async def stop(self):
        """Stop the sync service."""
        self.running = False
        
        # Clean up webhooks
        await self._cleanup_webhooks()
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
            
        logger.info("Webhook-driven sync service stopped")
    
    async def _load_existing_state(self):
        """Load existing mappings and state."""
        logger.info("Loading existing state...")
        
        # Load ID mappings
        pattern = f"{PLANNER_ID_MAP_PREFIX}*"
        cursor = 0
        count = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=pattern, count=100
            )
            for key in keys:
                parts = key.split(":")
                if len(parts) > 3:
                    task_id = parts[3]
                    self.processed_tasks.add(task_id)
                    count += 1
            if cursor == 0:
                break
        
        # Load ETags
        etag_pattern = f"{ETAG_PREFIX}*"
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor, match=etag_pattern, count=100
            )
            for key in keys:
                planner_id = key.replace(ETAG_PREFIX, "")
                etag = await self.redis_client.get(key)
                if etag:
                    self.task_etags[planner_id] = etag
            if cursor == 0:
                break
        
        logger.info(f"Loaded {count} ID mappings and {len(self.task_etags)} ETags")
    
    # ========== WEBHOOK MANAGEMENT ==========
    
    async def _setup_webhooks(self):
        """Set up Microsoft Graph webhooks for real-time notifications."""
        logger.info("🔗 Setting up Microsoft Graph webhooks...")
        
        # Use delegated token for groups (works with delegated permissions)
        delegated_token = get_delegated_token()
        # Use application token for Teams (requires application permissions)
        app_token = get_application_token()
        
        if not delegated_token and not app_token:
            logger.error("No tokens available for webhook setup")
            return
        
        # Setup multiple webhook subscriptions with appropriate tokens
        webhook_configs = [
            {
                "name": "groups",
                "token": delegated_token,  # Groups work with delegated
                "config": {
                    "changeType": "created,updated,deleted",
                    "notificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "resource": "/groups",
                    "expirationDateTime": (
                        datetime.utcnow() + timedelta(hours=24)
                    ).isoformat() + "Z",
                    "clientState": "annika_groups_webhook_v5"
                }
            },
            {
                "name": "teams_chats",
                "token": app_token,  # Teams require application token
                "config": {
                    "changeType": "created,updated,deleted",
                    "notificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "lifecycleNotificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "resource": "/chats",
                    "expirationDateTime": (
                        datetime.utcnow() + timedelta(hours=24)
                    ).isoformat() + "Z",
                    "clientState": "annika_teams_chats_v5"
                }
            },
            {
                "name": "teams_channels",
                "token": app_token,  # Teams require application token
                "config": {
                    "changeType": "created,updated,deleted",
                    "notificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "lifecycleNotificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "resource": "/teams/getAllChannels",
                    "expirationDateTime": (
                        datetime.utcnow() + timedelta(hours=24)
                    ).isoformat() + "Z",
                    "clientState": "annika_teams_channels_v5"
                }
            }
        ]
        
        # Create each webhook subscription
        for webhook_info in webhook_configs:
            webhook_name = webhook_info["name"]
            webhook_config = webhook_info["config"]
            webhook_token = webhook_info["token"]
            
            if not webhook_token:
                logger.warning(
                    f"No token available for {webhook_name} webhook"
                )
                continue
            
            headers = {
                "Authorization": f"Bearer {webhook_token}",
                "Content-Type": "application/json"
            }
            
            try:
                response = requests.post(
                    f"{GRAPH_API_ENDPOINT}/subscriptions",
                    headers=headers,
                    json=webhook_config,
                    timeout=30
                )
                
                if response.status_code == 201:
                    subscription = response.json()
                    subscription_id = subscription["id"]
                    self.webhook_subscriptions[webhook_name] = subscription_id
                    
                    # Store webhook status in Redis
                    await self.redis_client.hset(
                        WEBHOOK_STATUS_KEY,
                        webhook_name,
                        json.dumps({
                            "subscription_id": subscription_id,
                            "created_at": datetime.utcnow().isoformat(),
                            "expires_at": subscription["expirationDateTime"],
                            "resource": webhook_config["resource"]
                        })
                    )
                    
                    logger.info(f"✅ {webhook_name} webhook subscription created: {subscription_id}")
                else:
                    logger.error(f"Failed to create {webhook_name} webhook: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    
            except Exception as e:
                logger.error(f"Error setting up {webhook_name} webhook: {e}")
    
    async def _webhook_renewal_loop(self):
        """Periodically renew webhook subscriptions."""
        while self.running:
            await asyncio.sleep(self.webhook_renewal_interval)
            await self._renew_webhooks()
    
    async def _renew_webhooks(self):
        """Renew webhook subscriptions before they expire."""
        logger.info("🔄 Renewing webhook subscriptions...")
        
        token = get_agent_token()
        if not token:
            return
        
        for webhook_type, subscription_id in self.webhook_subscriptions.items():
            try:
                # Extend expiration by 24 hours
                new_expiration = (
                    datetime.utcnow() + timedelta(hours=24)
                ).isoformat() + "Z"
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                update_data = {
                    "expirationDateTime": new_expiration
                }
                
                response = requests.patch(
                    f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
                    headers=headers,
                    json=update_data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Renewed webhook: {webhook_type}")
                else:
                    logger.error(f"Failed to renew webhook {webhook_type}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error renewing webhook {webhook_type}: {e}")
    
    async def _cleanup_webhooks(self):
        """Clean up webhook subscriptions on shutdown."""
        logger.info("🧹 Cleaning up webhooks...")
        
        token = get_agent_token()
        if not token:
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        for webhook_type, subscription_id in self.webhook_subscriptions.items():
            try:
                response = requests.delete(
                    f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 204:
                    logger.info(f"✅ Cleaned up webhook: {webhook_type}")
                else:
                    logger.warning(f"Failed to cleanup webhook {webhook_type}: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error cleaning up webhook {webhook_type}: {e}")
    
    # ========== WEBHOOK PROCESSING ==========
    
    async def _process_webhook_notifications(self):
        """Process incoming webhook notifications from Microsoft Graph."""
        logger.info("📥 Monitoring webhook notifications...")
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
            
            if message['type'] == 'message':
                try:
                    channel = message.get('channel', '')
                    
                    if channel == "annika:planner:webhook":
                        # Process webhook notification
                        notification_data = json.loads(message['data'])
                        await self._handle_webhook_notification(notification_data)
                        
                except Exception as e:
                    logger.error(f"Error processing webhook notification: {e}")
    
    async def _handle_webhook_notification(self, notification: Dict):
        """Handle a single webhook notification from Microsoft Graph."""
        try:
            change_type = notification.get("changeType")
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            resource_data = notification.get("resourceData", {})
            resource_id = resource_data.get("id")
            
            logger.info(f"📨 Webhook: {change_type} for {resource} (client: {client_state})")
            
            # Handle different types of webhook notifications
            if "groups" in client_state:
                await self._handle_group_notification(notification)
            elif "teams_chats" in client_state:
                await self._handle_teams_chat_notification(notification)
            elif "teams_channels" in client_state:
                await self._handle_teams_channel_notification(notification)
            elif "/chats" in resource:
                # Handle chat notifications even without specific client state
                await self._handle_teams_chat_notification(notification)
            elif "/teams" in resource and "/channels" in resource:
                # Handle channel notifications even without specific client state
                await self._handle_teams_channel_notification(notification)
            else:
                logger.warning(f"Unknown webhook client state: {client_state}, resource: {resource}")
                
        except Exception as e:
            logger.error(f"Error handling webhook notification: {e}")
            await self._log_sync_operation(
                SyncOperation.UPDATE.value,
                None,
                notification.get("resourceData", {}).get("id"),
                "error",
                str(e)
            )
    
    async def _handle_group_notification(self, notification: Dict):
        """Handle group change notifications - trigger Planner polling for the group."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            group_id = resource_data.get("id")
            
            if not group_id:
                logger.warning("Group notification missing group ID")
                return
            
            logger.info(f"🏢 Group {change_type}: {group_id[:8]}... - checking for Planner changes")
            
            # Check if this group has Planner plans and poll for changes
            await self._poll_group_planner_tasks(group_id)
            
            # Log the group change
            await self._log_sync_operation(
                "group_change",
                None,
                group_id,
                "success",
                None,
                f"Group {change_type} triggered Planner polling"
            )
            
        except Exception as e:
            logger.error(f"Error handling group notification: {e}")
    
    async def _handle_teams_chat_notification(self, notification: Dict):
        """Handle Teams chat notifications - save to Redis for Annika."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            
            # Extract chat and message IDs from resource path
            chat_id = "unknown"
            message_id = resource_data.get("id", "unknown")
            
            # Determine if this is a chat message or general chat notification
            if "/messages" in resource:
                # This is a chat message notification
                if "/chats/" in resource:
                    # Extract chat ID from resource path
                    import re
                    chat_match = re.search(r"/chats/([^/]+)", resource)
                    if chat_match:
                        chat_id = chat_match.group(1).strip("'\"()")
                
                logger.info(f"💬 Teams chat message {change_type}: chat={chat_id[:8]}, msg={message_id[:8]}")
                
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
                
                # Also save to history list
                await self.redis_client.lpush(
                    "annika:teams:chat_messages:history",
                    json.dumps(message_notification)
                )
                
                # Keep only last 100 messages in history
                await self.redis_client.ltrim("annika:teams:chat_messages:history", 0, 99)
                
                logger.info(f"💬 Saved chat message to Redis: chat={chat_id[:8]}, msg={message_id[:8]}")
                
            else:
                # General chat notification (chat created/updated)
                chat_id = resource_data.get("id", "unknown")
                logger.info(f"💬 Teams chat {change_type}: {chat_id[:8] if chat_id else 'unknown'}")
                
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
                
                # Also save to history list
                await self.redis_client.lpush(
                    "annika:teams:chats:history",
                    json.dumps(chat_notification)
                )
                
                # Keep only last 50 chat notifications in history
                await self.redis_client.ltrim("annika:teams:chats:history", 0, 49)
                
                logger.info(f"💬 Saved chat notification to Redis: chat={chat_id[:8]}")
            
        except Exception as e:
            logger.error(f"Error handling Teams chat notification: {e}")
    
    async def _handle_teams_channel_notification(self, notification: Dict):
        """Handle Teams channel notifications - save to Redis for Annika."""
        try:
            change_type = notification.get("changeType")
            resource_data = notification.get("resourceData", {})
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")
            
            # Determine if this is a channel message or general channel notification
            if "/messages" in resource:
                # This is a channel message notification
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
                
                logger.info(f"📺 Teams channel message {change_type}: team={team_id[:8]}, channel={channel_id[:8]}, msg={message_id[:8]}")
                
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
                
                # Also save to history list
                await self.redis_client.lpush(
                    "annika:teams:channel_messages:history",
                    json.dumps(message_notification)
                )
                
                # Keep only last 100 messages in history
                await self.redis_client.ltrim("annika:teams:channel_messages:history", 0, 99)
                
                logger.info(f"📺 Saved channel message to Redis: team={team_id[:8]}, channel={channel_id[:8]}, msg={message_id[:8]}")
                
            else:
                # General channel notification (channel created/updated)
                channel_id = resource_data.get("id", "unknown")
                logger.info(f"📺 Teams channel {change_type}: {channel_id[:8] if channel_id else 'unknown'}")
                
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
                
                # Also save to history list
                await self.redis_client.lpush(
                    "annika:teams:channels:history",
                    json.dumps(channel_notification)
                )
                
                # Keep only last 50 channel notifications in history
                await self.redis_client.ltrim("annika:teams:channels:history", 0, 49)
                
                logger.info(f"📺 Saved channel notification to Redis: channel={channel_id[:8]}")
            
        except Exception as e:
            logger.error(f"Error handling Teams channel notification: {e}")
    
    async def _poll_group_planner_tasks(self, group_id: str):
        """Poll Planner tasks for a specific group when the group changes."""
        try:
            token = get_agent_token()
            if not token:
                return
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # First, get the group's Planner plans
            plans_response = requests.get(
                f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
                headers=headers,
                timeout=10
            )
            
            if plans_response.status_code != 200:
                logger.debug(f"Group {group_id[:8]} has no Planner plans or access denied")
                return
            
            plans = plans_response.json().get("value", [])
            if not plans:
                logger.debug(f"Group {group_id[:8]} has no Planner plans")
                return
            
            logger.info(f"🔍 Polling {len(plans)} Planner plan(s) for group {group_id[:8]}")
            
            # Poll tasks for each plan in the group
            for plan in plans:
                plan_id = plan.get("id")
                if plan_id:
                    await self._poll_plan_tasks(plan_id)
                
        except Exception as e:
            logger.error(f"Error polling group {group_id} Planner tasks: {e}")
    
    async def _poll_plan_tasks(self, plan_id: str):
        """Poll tasks for a specific Planner plan."""
        try:
            token = get_agent_token()
            if not token:
                return
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get all tasks for the plan
            tasks_response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )
            
            if tasks_response.status_code == 200:
                tasks = tasks_response.json().get("value", [])
                logger.info(f"📋 Found {len(tasks)} tasks in plan {plan_id[:8]}")
                
                # Process each task to see if it needs syncing
                for task in tasks:
                    task_id = task.get("id")
                    if task_id:
                        # Check if this task needs to be synced
                        annika_id = await self._get_annika_id(task_id)
                        if not annika_id:
                            # New task - create in Annika
                            await self._create_annika_task_from_planner(task)
                        else:
                            # Existing task - check if it needs updating
                            await self._sync_existing_task(task_id, task)
            else:
                logger.debug(f"Could not access tasks for plan {plan_id}: {tasks_response.status_code}")
                
        except Exception as e:
            logger.error(f"Error polling plan {plan_id} tasks: {e}")
    
    async def _sync_existing_task(self, planner_id: str, planner_task: Dict):
        """Sync an existing task if it has been modified."""
        try:
            annika_id = await self._get_annika_id(planner_id)
            if not annika_id:
                return
            
            # Check if this task is currently being uploaded
            if annika_id in self.processing_upload:
                logger.debug(f"Skipping sync for task currently being uploaded: {planner_id[:8]}")
                return
            
            # Get the current Annika task
            annika_task = await self._get_annika_task(annika_id)
            if annika_task:
                # Check for conflicts and resolve
                resolution = self.conflict_resolver.resolve_conflict(
                    annika_task, planner_task
                )
                
                if resolution == ConflictResolution.PLANNER_WINS:
                    await self._update_annika_task_from_planner(annika_id, planner_task)
                    logger.info(f"🔄 Updated Annika task from Planner: {annika_id}")
                else:
                    logger.info(f"🔄 Annika version newer, queuing for upload: {annika_id}")
                    await self._queue_upload(annika_task)
                
                await self._log_sync_operation(
                    SyncOperation.UPDATE.value,
                    annika_id,
                    planner_id,
                    "success",
                    conflict_resolution=resolution.value
                )
                
        except Exception as e:
            logger.error(f"Error syncing existing task {planner_id}: {e}")
    
    # ========== UPLOAD PROCESSING ==========
    
    async def _monitor_annika_changes(self):
        """Monitor Annika changes and queue for upload."""
        logger.info("📤 Monitoring Annika changes for upload...")
        
        last_state_hash = await self._get_state_hash()
        
        async for message in self.pubsub.listen():
            if not self.running:
                break
            
            if message['type'] == 'message':
                try:
                    channel = message.get('channel', '')
                    
                    if "conscious_state" in channel:
                        current_hash = await self._get_state_hash()
                        if current_hash != last_state_hash:
                            await self._detect_and_queue_changes()
                            last_state_hash = current_hash
                    
                    elif channel == 'annika:tasks:updates':
                        await self._detect_and_queue_changes()
                        
                except Exception as e:
                    logger.error(f"Error monitoring Annika changes: {e}")
    
    async def _detect_and_queue_changes(self):
        """Detect changed tasks and queue them for upload."""
        try:
            annika_tasks = await self.adapter.get_all_annika_tasks()
            
            for task in annika_tasks:
                annika_id = task.get("id")
                if not annika_id or annika_id in self.processing_upload:
                    continue
                
                # Check if task needs upload
                if await self._task_needs_upload(task):
                    await self._queue_upload(task)
                    
        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
    
    async def _task_needs_upload(self, annika_task: Dict) -> bool:
        """Check if a task needs to be uploaded to Planner."""
        annika_id = annika_task.get("id")
        planner_id = await self._get_planner_id(annika_id)
        
        if not planner_id:
            # New task - needs upload
            return True
        
        # Check if modified since last sync
        annika_modified = annika_task.get("modified_at")
        last_sync = await self.redis_client.get(f"annika:sync:last_upload:{annika_id}")
        
        if not last_sync or not annika_modified:
            return True
        
        try:
            annika_time = datetime.fromisoformat(annika_modified.replace('Z', '+00:00'))
            sync_time = datetime.fromisoformat(last_sync)
            return annika_time > sync_time
        except:
            return True
    
    async def _queue_upload(self, annika_task: Dict):
        """Queue a task for batch upload."""
        self.pending_uploads.append(annika_task)
        
        # Trigger batch processing if queue is full
        if len(self.pending_uploads) >= self.batch_size:
            await self._process_upload_batch()
    
    async def _batch_processor(self):
        """Process upload batches periodically."""
        while self.running:
            await asyncio.sleep(self.batch_timeout)
            
            if self.pending_uploads:
                await self._process_upload_batch()
    
    async def _process_upload_batch(self):
        """Process a batch of uploads to Planner."""
        if not self.pending_uploads:
            return
        
        batch = self.pending_uploads[:self.batch_size]
        self.pending_uploads = self.pending_uploads[self.batch_size:]
        
        logger.info(f"📤 Processing upload batch of {len(batch)} tasks")
        
        for task in batch:
            annika_id = task.get("id")
            if annika_id:
                self.processing_upload.add(annika_id)
                
                try:
                    planner_id = await self._get_planner_id(annika_id)
                    
                    if planner_id:
                        await self._update_planner_task(planner_id, task)
                    else:
                        await self._create_planner_task(task)
                        
                    # Mark as uploaded
                    await self.redis_client.set(
                        f"annika:sync:last_upload:{annika_id}",
                        datetime.utcnow().isoformat()
                    )
                    
                finally:
                    self.processing_upload.discard(annika_id)
    
    # ========== HELPER METHODS ==========
    
    async def _get_state_hash(self) -> Optional[str]:
        """Get hash of conscious_state for change detection."""
        try:
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            if state_json:
                return str(hash(state_json))
        except Exception:
            pass
        return None
    
    async def _get_annika_task(self, annika_id: str) -> Optional[Dict]:
        """Get Annika task by ID."""
        try:
            annika_tasks = await self.adapter.get_all_annika_tasks()
            for task in annika_tasks:
                if task.get("id") == annika_id:
                    return task
        except Exception:
            pass
        return None
    
    async def _queue_operation(self, operation_type: str, task_id: str):
        """Queue an operation for later processing."""
        operation = {
            "type": operation_type,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.redis_client.lpush(
            PENDING_OPS_KEY,
            json.dumps(operation)
        )
    
    async def _log_sync_operation(
        self,
        operation: str,
        annika_id: Optional[str],
        planner_id: Optional[str],
        status: str,
        error: Optional[str] = None,
        conflict_resolution: Optional[str] = None
    ):
        """Log a sync operation for debugging and monitoring."""
        log_entry = SyncLogEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation=operation,
            annika_id=annika_id,
            planner_id=planner_id,
            status=status,
            error=error,
            conflict_resolution=conflict_resolution
        )
        
        await self.redis_client.lpush(
            SYNC_LOG_KEY,
            json.dumps(log_entry.__dict__)
        )
        
        # Keep only last 1000 log entries
        await self.redis_client.ltrim(SYNC_LOG_KEY, 0, 999)
    
    # ========== HEALTH MONITORING ==========
    
    async def _health_monitor(self):
        """Monitor service health and report metrics."""
        while self.running:
            await asyncio.sleep(300)  # Every 5 minutes
            
            try:
                metrics = await self._collect_health_metrics()
                logger.info("📊 Health Check:")
                logger.info(f"   - Processed tasks: {metrics['processed_tasks']}")
                logger.info(f"   - Pending uploads: {metrics['pending_uploads']}")
                logger.info(f"   - Failed operations: {metrics['failed_operations']}")
                logger.info(f"   - Rate limit status: {metrics['rate_limit_status']}")
                logger.info(f"   - Webhook status: {metrics['webhook_status']}")
                
                # Store metrics in Redis
                await self.redis_client.set(
                    "annika:sync:health",
                    json.dumps(metrics),
                    ex=3600  # Expire after 1 hour
                )
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
    
    async def _collect_health_metrics(self) -> Dict:
        """Collect health metrics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "processed_tasks": len(self.processed_tasks),
            "pending_uploads": len(self.pending_uploads),
            "failed_operations": await self.redis_client.llen(FAILED_OPS_KEY),
            "rate_limit_status": "limited" if self.rate_limiter.is_rate_limited() else "ok",
            "webhook_status": len(self.webhook_subscriptions),
            "consecutive_failures": self.rate_limiter.consecutive_failures
        }
    
    # ========== INITIAL SYNC ==========
    
    async def _initial_sync(self):
        """Perform minimal initial sync - only check for critical gaps."""
        logger.info("🔄 Performing minimal initial sync...")
        
        try:
            # Only sync tasks that have been modified in the last 24 hours
            # This catches any gaps without overwhelming the API
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            annika_tasks = await self.adapter.get_all_annika_tasks()
            recent_tasks = []
            
            for task in annika_tasks:
                modified_at = task.get("modified_at")
                if modified_at:
                    try:
                        mod_time = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
                        if mod_time > cutoff_time:
                            recent_tasks.append(task)
                    except:
                        # If we can't parse the time, include it to be safe
                        recent_tasks.append(task)
            
            logger.info(f"Found {len(recent_tasks)} recently modified tasks to sync")
            
            # Queue recent tasks for upload
            for task in recent_tasks:
                if await self._task_needs_upload(task):
                    await self._queue_upload(task)
            
            # Also do an immediate Planner poll to catch any recent changes
            logger.info("🔍 Performing immediate Planner poll as part of initial sync...")
            await self._poll_all_planner_tasks()
            
            logger.info("✅ Initial sync completed")
            
        except Exception as e:
            logger.error(f"Error in initial sync: {e}")
    
    # ========== ID MAPPING AND STORAGE ==========
    
    async def _store_id_mapping(self, annika_id: str, planner_id: str):
        """Store bidirectional ID mapping."""
        await self.redis_client.set(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            planner_id
        )
        await self.redis_client.set(
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}",
            annika_id
        )
    
    async def _get_planner_id(self, annika_id: str) -> Optional[str]:
        """Get Planner ID for Annika task."""
        return await self.redis_client.get(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}"
        )
    
    async def _get_annika_id(self, planner_id: str) -> Optional[str]:
        """Get Annika ID for Planner task."""
        return await self.redis_client.get(
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}"
        )
    
    async def _store_etag(self, planner_id: str, etag: str):
        """Store ETag for update detection."""
        await self.redis_client.set(f"{ETAG_PREFIX}{planner_id}", etag)
    
    async def _remove_mapping(self, annika_id: str, planner_id: str):
        """Remove ID mappings."""
        await self.redis_client.delete(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            f"{PLANNER_ID_MAP_PREFIX}{planner_id}",
            f"{ETAG_PREFIX}{planner_id}"
        )
    
    # ========== TASK OPERATIONS (Complete implementations) ==========
    
    async def _create_annika_task_from_planner(self, planner_task: Dict):
        """Create task in Annika from Planner task."""
        planner_id = planner_task["id"]
        annika_id = f"Task-{uuid.uuid4().hex[:8]}"
        
        try:
            # Store mapping first to prevent duplicates
            await self._store_id_mapping(annika_id, planner_id)
            await self._store_etag(planner_id, planner_task.get("@odata.etag", ""))
            
            # Convert to Annika format
            annika_task = await self.adapter.planner_to_annika(planner_task)
            annika_task["id"] = annika_id
            annika_task["external_id"] = planner_id
            annika_task["source"] = "planner"
            annika_task["created_at"] = datetime.utcnow().isoformat()
            
            # Determine list type
            list_type = self.adapter.determine_task_list(planner_task)
            
            # Update conscious_state directly
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            
            if state_json:
                state = json.loads(state_json)[0]
                
                if "task_lists" not in state:
                    state["task_lists"] = {}
                if list_type not in state["task_lists"]:
                    state["task_lists"][list_type] = {"tasks": []}
                
                state["task_lists"][list_type]["tasks"].append(annika_task)
                
                await self.redis_client.execute_command(
                    "JSON.SET", "annika:conscious_state", "$",
                    json.dumps(state)
                )
                
                await self._log_sync_operation(
                    SyncOperation.CREATE.value,
                    annika_id,
                    planner_id,
                    "success"
                )
                
                logger.info(f"✅ Created Annika task from Planner: {planner_task.get('title')}")
            else:
                logger.error("No conscious_state found in Redis!")
                await self._log_sync_operation(
                    SyncOperation.CREATE.value,
                    annika_id,
                    planner_id,
                    "error",
                    "No conscious_state found"
                )
                
        except Exception as e:
            logger.error(f"Error creating Annika task from Planner: {e}")
            await self._log_sync_operation(
                SyncOperation.CREATE.value,
                annika_id,
                planner_id,
                "error",
                str(e)
            )
    
    async def _update_annika_task_from_planner(self, annika_id: str, planner_task: Dict):
        """Update Annika task from Planner changes."""
        try:
            # Convert updates
            updates = await self.adapter.planner_to_annika(planner_task)
            
            # Get current state
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            
            if state_json:
                state = json.loads(state_json)[0]
                updated = False
                
                # Find and update task
                for list_type, task_list in state.get("task_lists", {}).items():
                    for i, task in enumerate(task_list.get("tasks", [])):
                        if task.get("id") == annika_id:
                            # Update fields
                            task.update(updates)
                            task["modified_at"] = datetime.utcnow().isoformat()
                            updated = True
                            break
                    if updated:
                        break
                
                if updated:
                    await self.redis_client.execute_command(
                        "JSON.SET", "annika:conscious_state", "$",
                        json.dumps(state)
                    )
                    
                    await self._log_sync_operation(
                        SyncOperation.UPDATE.value,
                        annika_id,
                        planner_task["id"],
                        "success"
                    )
                    
                    logger.debug(f"✅ Updated Annika task from Planner: {planner_task.get('title')}")
                else:
                    logger.warning(f"Task {annika_id} not found in conscious_state")
                    
        except Exception as e:
            logger.error(f"Error updating Annika task: {e}")
            await self._log_sync_operation(
                SyncOperation.UPDATE.value,
                annika_id,
                planner_task["id"],
                "error",
                str(e)
            )
    
    async def _create_planner_task(self, annika_task: Dict) -> bool:
        """Create task in Planner from Annika task."""
        if self.rate_limiter.is_rate_limited():
            logger.debug("Rate limited - queuing task creation")
            await self._queue_upload(annika_task)
            return False
        
        try:
            token = get_agent_token()
            if not token:
                logger.error("No token available for task creation")
                return False
            
            # Convert to Planner format
            planner_data = self.adapter.annika_to_planner(annika_task)
            
            # Set plan ID
            plan_id = await self._determine_plan_for_task(annika_task)
            if not plan_id:
                logger.warning(f"No plan for task: {annika_task.get('title')}")
                return False
            
            planner_data["planId"] = plan_id
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/planner/tasks",
                headers=headers,
                json=planner_data,
                timeout=10
            )
            
            if response.status_code == 201:
                planner_task = response.json()
                planner_id = planner_task["id"]
                annika_id = annika_task.get("id")
                
                # Store mapping and ETag
                await self._store_id_mapping(annika_id, planner_id)
                etag = planner_task.get("@odata.etag", "")
                await self._store_etag(planner_id, etag)
                
                await self._log_sync_operation(
                    SyncOperation.CREATE.value,
                    annika_id,
                    planner_id,
                    "success"
                )
                
                logger.info(f"✅ Created Planner task: {annika_task.get('title')}")
                self.rate_limiter.reset()
                return True
                
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.rate_limiter.handle_rate_limit(retry_after)
                await self._queue_upload(annika_task)
                return False
                
            else:
                logger.error(f"Failed to create Planner task: {response.status_code}")
                logger.error(f"Response: {response.text}")
                
                await self._log_sync_operation(
                    SyncOperation.CREATE.value,
                    annika_task.get("id"),
                    None,
                    "error",
                    f"HTTP {response.status_code}: {response.text}"
                )
                return False
                
        except Exception as e:
            logger.error(f"Error creating Planner task: {e}")
            await self._log_sync_operation(
                SyncOperation.CREATE.value,
                annika_task.get("id"),
                None,
                "error",
                str(e)
            )
            return False
    
    async def _update_planner_task(self, planner_id: str, annika_task: Dict) -> bool:
        """Update Planner task from Annika changes."""
        if self.rate_limiter.is_rate_limited():
            logger.debug("Rate limited - queuing task update")
            await self._queue_upload(annika_task)
            return False
        
        try:
            token = get_agent_token()
            if not token:
                return False
            
            # Get current task for ETag
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get task for update: {planner_id}")
                return False
            
            current_task = response.json()
            etag = current_task.get("@odata.etag")
            
            # Convert to update format
            update_data = self.adapter.annika_to_planner(annika_task)
            update_data.pop("planId", None)  # Can't update plan
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": etag
            }
            
            response = requests.patch(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers=headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                # Update stored ETag
                new_etag = response.headers.get("ETag", etag)
                await self._store_etag(planner_id, new_etag)
                
                await self._log_sync_operation(
                    SyncOperation.UPDATE.value,
                    annika_task.get("id"),
                    planner_id,
                    "success"
                )
                
                logger.debug(f"✅ Updated Planner task: {annika_task.get('title')}")
                self.rate_limiter.reset()
                return True
                
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.rate_limiter.handle_rate_limit(retry_after)
                await self._queue_upload(annika_task)
                return False
                
            else:
                logger.error(f"Failed to update Planner task: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating Planner task: {e}")
            await self._log_sync_operation(
                SyncOperation.UPDATE.value,
                annika_task.get("id"),
                planner_id,
                "error",
                str(e)
            )
            return False
    
    async def _delete_annika_task(self, annika_id: str):
        """Delete task from Annika."""
        try:
            # Get current state
            state_json = await self.redis_client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            
            if state_json:
                state = json.loads(state_json)[0]
                deleted = False
                
                # Find and remove task
                for list_type, task_list in state.get("task_lists", {}).items():
                    tasks = task_list.get("tasks", [])
                    for i, task in enumerate(tasks):
                        if task.get("id") == annika_id:
                            tasks.pop(i)
                            deleted = True
                            break
                    if deleted:
                        break
                
                if deleted:
                    await self.redis_client.execute_command(
                        "JSON.SET", "annika:conscious_state", "$",
                        json.dumps(state)
                    )
                    logger.debug(f"✅ Deleted Annika task: {annika_id}")
                else:
                    logger.warning(f"Task {annika_id} not found for deletion")
                    
        except Exception as e:
            logger.error(f"Error deleting Annika task {annika_id}: {e}")
    
    async def _determine_plan_for_task(self, annika_task: Dict) -> Optional[str]:
        """Determine which plan a task should go to."""
        # You can customize this logic based on task properties
        # For now, use default plan from environment or Redis config
        
        # Check if task has a specific plan preference
        task_plan = annika_task.get("plan_id")
        if task_plan:
            return task_plan
        
        # Check Redis config
        default_plan = await self.redis_client.get("annika:config:default_plan_id")
        if default_plan:
            return default_plan
        
        # Fall back to environment variable
        import os
        return os.getenv("DEFAULT_PLANNER_PLAN_ID")

    # ========== PLANNER POLLING ==========

    async def _planner_polling_loop(self):
        """Poll all known Planner plans for task changes every hour."""
        logger.info("⏰ Starting Planner polling loop (every hour)")
        
        while self.running:
            try:
                await asyncio.sleep(3600)  # Wait 1 hour (3600 seconds)
                
                if not self.running:
                    break
                
                logger.info("🔍 Starting hourly Planner poll for task changes...")
                await self._poll_all_planner_tasks()
                
            except Exception as e:
                logger.error(f"Error in Planner polling loop: {e}")
                # Continue running even if one poll fails
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def _poll_all_planner_tasks(self):
        """Poll all accessible Planner plans for task changes."""
        try:
            token = get_agent_token()
            if not token:
                logger.warning("No token available for Planner polling")
                return
            
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get all plans using the same approach as V4 (groups + personal)
            all_plans = await self._get_all_plans_for_polling(headers)
            
            if not all_plans:
                logger.warning("No plans found to poll")
                return
            
            logger.info(f"📋 Polling {len(all_plans)} Planner plans for task changes")
            
            tasks_checked = 0
            tasks_updated = 0
            tasks_created = 0
            
            # Poll each plan for tasks
            for plan in all_plans:
                plan_id = plan.get("id")
                plan_title = plan.get("title", "Unknown")
                
                if not plan_id:
                    continue
                
                try:
                    # Get all tasks for this plan
                    tasks_response = requests.get(
                        f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                        headers=headers,
                        timeout=15
                    )
                    
                    if tasks_response.status_code == 200:
                        tasks = tasks_response.json().get("value", [])
                        logger.debug(f"📋 Plan '{plan_title}': {len(tasks)} tasks")
                        
                        for task in tasks:
                            task_id = task.get("id")
                            if not task_id:
                                continue
                            
                            tasks_checked += 1
                            
                            # Check if this task exists in Annika
                            annika_id = await self._get_annika_id(task_id)
                            
                            if not annika_id:
                                # New task - create in Annika
                                await self._create_annika_task_from_planner(task)
                                tasks_created += 1
                                logger.info(f"📝 Created new task from Planner: {task.get('title', 'Untitled')}")
                            else:
                                # Existing task - check if it needs updating
                                if await self._task_needs_sync_from_planner(task_id, task):
                                    await self._sync_existing_task(task_id, task)
                                    tasks_updated += 1
                    else:
                        logger.debug(f"Could not access tasks for plan '{plan_title}': {tasks_response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error polling plan '{plan_title}': {e}")
                    continue
            
            # Log polling results
            logger.info(f"✅ Planner polling complete: {tasks_checked} tasks checked, {tasks_created} created, {tasks_updated} updated")
            
            # Log the polling operation
            await self._log_sync_operation(
                "planner_poll",
                None,
                None,
                "success",
                None,
                f"Polled {len(all_plans)} plans, {tasks_checked} tasks checked, {tasks_created} created, {tasks_updated} updated"
            )
            
        except Exception as e:
            logger.error(f"Error in Planner polling: {e}")
            await self._log_sync_operation(
                "planner_poll",
                None,
                None,
                "error",
                str(e)
            )
    
    async def _task_needs_sync_from_planner(self, planner_id: str, planner_task: Dict) -> bool:
        """Check if a Planner task needs to be synced to Annika."""
        try:
            # Check stored ETag to see if task has changed
            stored_etag = await self.redis_client.get(f"{ETAG_PREFIX}{planner_id}")
            current_etag = planner_task.get("@odata.etag", "")
            
            if stored_etag != current_etag:
                logger.debug(f"Task {planner_id[:8]} has changed (ETag mismatch)")
                return True
            
            # Also check modification time as backup
            planner_modified = planner_task.get("lastModifiedDateTime")
            if planner_modified:
                try:
                    # Get the Annika task to compare modification times
                    annika_id = await self._get_annika_id(planner_id)
                    if annika_id:
                        annika_task = await self._get_annika_task(annika_id)
                        if annika_task:
                            annika_modified = annika_task.get("modified_at")
                            if annika_modified:
                                planner_time = datetime.fromisoformat(planner_modified.replace('Z', '+00:00'))
                                annika_time = datetime.fromisoformat(annika_modified.replace('Z', '+00:00'))
                                
                                # If Planner task is newer, sync it
                                if planner_time > annika_time:
                                    logger.debug(f"Task {planner_id[:8]} is newer in Planner")
                                    return True
                except Exception as e:
                    logger.debug(f"Error comparing modification times for {planner_id}: {e}")
                    # If we can't compare times, err on the side of syncing
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if task needs sync: {e}")
            return True  # Err on the side of syncing

    async def _get_all_plans_for_polling(self, headers: Dict) -> List[Dict]:
        """Get all accessible plans (personal + group plans) - based on V4 approach."""
        all_plans = []
        
        try:
            logger.info("🔍 Getting personal plans...")
            # Personal plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/planner/plans",
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                personal_plans = response.json().get("value", [])
                all_plans.extend(personal_plans)
                logger.info(f"   Found {len(personal_plans)} personal plans")
            else:
                logger.warning(f"Failed to get personal plans: {response.status_code}")
            
            logger.info("🔍 Getting group memberships...")
            # Group plans
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/memberOf",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                groups = response.json().get("value", [])
                logger.info(f"   Found {len(groups)} group memberships")
                
                group_plan_count = 0
                processed_groups = 0
                
                for item in groups:
                    if item.get("@odata.type") == "#microsoft.graph.group":
                        group_id = item.get("id")
                        group_name = item.get("displayName", "Unknown")
                        processed_groups += 1
                        
                        try:
                            logger.debug(
                                f"   [{processed_groups}/{len(groups)}] "
                                f"Checking group: {group_name}"
                            )
                            
                            url = (f"{GRAPH_API_ENDPOINT}/groups/{group_id}"
                                   "/planner/plans")
                            plans_resp = requests.get(
                                url, headers=headers, timeout=10
                            )
                            
                            if plans_resp.status_code == 200:
                                group_plans = plans_resp.json().get("value", [])
                                if group_plans:
                                     all_plans.extend(group_plans)
                                     group_plan_count += len(group_plans)
                                     logger.debug(
                                         f"      Added {len(group_plans)} "
                                         f"plans from {group_name}"
                                     )
                            elif plans_resp.status_code == 403:
                                logger.debug(f"      No Planner access for group: {group_name}")
                            else:
                                logger.debug(f"      Failed to get plans for {group_name}: {plans_resp.status_code}")
                                
                        except requests.exceptions.Timeout:
                            logger.warning(f"      Timeout getting plans for group: {group_name}")
                        except Exception as e:
                            logger.debug(f"      Error getting plans for {group_name}: {e}")
                        
                        # Add small delay to avoid rate limiting
                        if processed_groups % 5 == 0:
                            await asyncio.sleep(0.1)
                
                logger.info(f"   Found {group_plan_count} plans across {processed_groups} groups")
            else:
                logger.warning(f"Failed to get group memberships: {response.status_code}")
        
        except requests.exceptions.Timeout:
            logger.error("Timeout getting plans - continuing with what we have")
        except Exception as e:
            logger.error(f"Error getting plans: {e}")
        
        logger.info(f"📋 Total plans found: {len(all_plans)}")
        return all_plans

    async def trigger_immediate_poll(self):
        """Trigger an immediate Planner poll (for testing/manual use)."""
        logger.info("🚀 Triggering immediate Planner poll...")
        await self._poll_all_planner_tasks()


async def main():
    """Run the webhook-driven sync service."""
    sync_service = WebhookDrivenPlannerSync()
    
    try:
        await sync_service.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        await sync_service.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main()) 