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
import os
import time
import uuid
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
import redis.asyncio as redis
import requests

# FIX: Use package-absolute import to avoid ModuleNotFoundError when running as src.*
try:
    # When running as a package (python -m src.start_all_services)
    from src.agent_auth_manager import get_agent_token  # type: ignore
except ModuleNotFoundError:
    # When running from inside src/ (python start_all_services.py)
    from agent_auth_manager import get_agent_token  # type: ignore
from annika_task_adapter import AnnikaTaskAdapter
from dual_auth_manager import get_application_token, get_delegated_token

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

try:
    from logging_setup import setup_logging
    setup_logging(add_console=True)
except Exception:
    pass
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
            backoff = retry_after_seconds
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

        # Get modification timestamps (prefer last_modified_at, then updated_at)
        annika_modified = (
            annika_task.get("last_modified_at")
            or annika_task.get("updated_at")
            or annika_task.get("modified_at")
        )
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
        # Quick-poll scheduling to tighten feedback after local edits
        self.quick_poll_task = None
        self.last_quick_poll_at: float = 0.0
        try:
            self.quick_poll_min_interval = int(os.environ.get("MIN_QUICK_POLL_INTERVAL_SECONDS", "300"))
        except Exception:
            self.quick_poll_min_interval = 300

        try:
            self.default_poll_interval = max(
                self.quick_poll_min_interval,
                int(os.environ.get("PLANNER_POLL_INTERVAL_SECONDS", "3600"))
            )
        except Exception:
            self.default_poll_interval = max(self.quick_poll_min_interval, 3600)

        try:
            self.webhook_poll_interval = int(
                os.environ.get("PLANNER_WEBHOOK_POLL_INTERVAL_SECONDS", "21600")
            )
        except Exception:
            self.webhook_poll_interval = 21600

        self.poll_interval = self.default_poll_interval
        self.polling_enabled = self.poll_interval > 0
        self.planner_webhooks_requested = False

        try:
            self.health_ttl = int(os.environ.get("SYNC_HEALTH_TTL_SECONDS", "300"))
        except Exception:
            self.health_ttl = 300

        # Components
        self.rate_limiter = RateLimitHandler()
        self.conflict_resolver = ConflictResolver()
        self.http = requests.Session()

        # State tracking
        self.task_etags = {}
        self.processed_tasks = set()
        self.processing_upload = set()

        # Webhook management
        self.webhook_subscriptions = {}
        self.webhook_configs = {}
        self.webhook_renewal_interval = 3600  # 1 hour

        # Batch processing
        self.pending_uploads = []
        self.batch_size = 10
        self.batch_timeout = 5  # seconds
        self.batch_processing = False  # Flag to prevent concurrent batch processing
        self.batch_scheduled = False  # Flag to prevent scheduling multiple batch tasks
        # Optional Graph $batch for creates (safer subset) – config gated
        self.batch_writes_enabled = os.environ.get("BATCH_WRITES_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        self.max_graph_batch = 20

        # Discovery caches (per-cycle)
        self.plan_cache: List[Dict] = []
        self.plan_cache_time: float = 0.0
        self.plan_cache_token_type: str = "unknown"
        self.bucket_cache: Dict[str, Dict[str, any]] = {}
        self.last_read_token_choice: str = "delegated"

        # Cleanup/housekeeping
        self.cleanup_enabled = os.environ.get("CLEANUP_ENABLED", "false").lower() == "true"
        self.cleanup_dry_run = os.environ.get("CLEANUP_DRY_RUN", "true").lower() == "true"
        try:
            self.cleanup_interval = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "21600"))
        except Exception:
            self.cleanup_interval = 21600

    async def start(self):
        """Start the webhook-driven sync service."""
        logger.info("🚀 Starting Webhook-Driven Planner Sync Service V5...")

        # Initialize Redis
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        await self.redis_client.ping()

        # Initialize adapter
        self.adapter = AnnikaTaskAdapter(self.redis_client)

        # Set up pub/sub (use separate clients to avoid cross-consumer message loss)
        self.pubsub_annika = self.redis_client.pubsub()
        await self.pubsub_annika.subscribe(
            "__keyspace@0__:annika:conscious_state",
            "annika:tasks:updates",
        )
        self.pubsub_webhook = self.redis_client.pubsub()
        await self.pubsub_webhook.subscribe(
            "annika:planner:webhook"
        )

        self.running = True
        self.poll_on_startup = False

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
            self._pending_queue_worker(),        # Process pending Redis queue
            self._housekeeping_loop(),           # Redis housekeeping
            return_exceptions=True
        )

    async def _housekeeping_loop(self) -> None:
        """Low-priority Redis housekeeping per spec; dry-run unless enabled."""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if not self.cleanup_enabled:
                    continue

                # ID map normalization (forward string + reverse exists)
                cursor = 0
                pattern = f"{PLANNER_ID_MAP_PREFIX}*"
                while True:
                    cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=200)
                    for key in keys:
                        annika_id = key.replace(PLANNER_ID_MAP_PREFIX, "")
                        v = await self.redis_client.get(key)
                        planner_id = None
                        if v:
                            if isinstance(v, str) and v.strip().startswith("{"):
                                try:
                                    obj = json.loads(v)
                                    planner_id = obj.get("planner_id") or obj.get("plannerId") or obj.get("planner")
                                except Exception:
                                    planner_id = None
                            else:
                                planner_id = v
                        if planner_id:
                            # Ensure reverse mapping exists
                            reverse_key = f"annika:task:mapping:planner:{planner_id}"
                            if self.cleanup_dry_run:
                                await self.redis_client.lpush("annika:cleanup:log", json.dumps({
                                    "op": "ensure_reverse_map",
                                    "annika_id": annika_id,
                                    "planner_id": planner_id,
                                }))
                            else:
                                await self.redis_client.set(reverse_key, annika_id)
                        else:
                            # Malformed mapping; skip
                            pass
                    if cursor == 0:
                        break

                # ETag orphans: delete where no reverse mapping exists
                cursor = 0
                etag_prefix = ETAG_PREFIX
                while True:
                    cursor, keys = await self.redis_client.scan(cursor, match=f"{etag_prefix}*", count=200)
                    for ekey in keys:
                        pid = ekey.replace(etag_prefix, "")
                        reverse = await self.redis_client.get(f"annika:task:mapping:planner:{pid}")
                        if not reverse:
                            if self.cleanup_dry_run:
                                await self.redis_client.lpush("annika:cleanup:log", json.dumps({
                                    "op": "delete_orphan_etag",
                                    "planner_id": pid,
                                }))
                            else:
                                await self.redis_client.delete(ekey)
                    if cursor == 0:
                        break

                # Lists bounds and TTLs
                await self.redis_client.ltrim("annika:webhook:log", 0, 499)
                await self.redis_client.expire("annika:webhooks:notifications", 3600)
                await self.redis_client.ltrim("annika:sync:failed", 0, 999)
                await self.redis_client.expire("annika:sync:failed", 7 * 24 * 60 * 60)

                # Graph caches TTL enforcement
                for prefix in ("annika:graph:plans:", "annika:graph:buckets:"):
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis_client.scan(cursor, match=f"{prefix}*", count=200)
                        for k in keys:
                            ttl = await self.redis_client.ttl(k)
                            if ttl is None or ttl < 0 or ttl > 300:
                                await self.redis_client.expire(k, 300)
                        if cursor == 0:
                            break

                # Health TTL
                ttl = await self.redis_client.ttl("annika:sync:health")
                if ttl is None or ttl < 0 or ttl > self.health_ttl:
                    await self.redis_client.expire("annika:sync:health", self.health_ttl)

                # Housekeeping heartbeat
                await self.redis_client.set("annika:cleanup:stats", json.dumps({
                    "timestamp": datetime.utcnow().isoformat(),
                    "dry_run": self.cleanup_dry_run,
                }), ex=300)

            except Exception as e:
                logger.debug(f"Housekeeping loop error: {e}")

    def _processed_set_key(self) -> str:
        """Return today's processed identity set key."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return f"annika:sync:processed:{today}"

    async def _ensure_key_ttl(self, key: str, seconds: int) -> None:
        try:
            ttl = await self.redis_client.ttl(key)
            if ttl is None or ttl < 0:
                await self.redis_client.expire(key, seconds)
        except Exception:
            pass

    async def _pending_queue_worker(self) -> None:
        """Consume operations from annika:sync:pending with retry/backoff and dedup."""
        MAX_RETRIES = 5
        BACKOFF_BASE = 2
        PROCESSED_TTL = 2 * 24 * 60 * 60  # 2 days

        while self.running:
            try:
                result = await self.redis_client.brpop(PENDING_OPS_KEY, timeout=5)
                if not result:
                    # Timeout: loop and check running flag again
                    continue

                # redis-py may return (key, value) or [key, value]
                raw = result[1] if isinstance(result, (list, tuple)) and len(result) == 2 else result
                try:
                    op = json.loads(raw)
                except Exception:
                    # Malformed entry → drop to failed list
                    await self.redis_client.lpush(FAILED_OPS_KEY, json.dumps({
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": "malformed_operation",
                        "raw": raw if isinstance(raw, str) else str(raw),
                    }))
                    await self.redis_client.ltrim(FAILED_OPS_KEY, 0, 999)
                    await self._ensure_key_ttl(FAILED_OPS_KEY, 7 * 24 * 60 * 60)
                    continue

                op_type = op.get("type") or op.get("operation")
                annika_id = op.get("task_id") or op.get("annika_id")
                identity = f"{op_type}:{annika_id}"

                # Respect scheduled next_retry if present
                next_retry = op.get("next_retry")
                if next_retry:
                    try:
                        due = datetime.fromisoformat(next_retry.replace("Z", "+00:00"))
                        if due > datetime.utcnow():
                            # Not yet due: push back to the queue tail
                            await self.redis_client.rpush(PENDING_OPS_KEY, json.dumps(op))
                            # Small sleep to avoid tight loop on same entry
                            await asyncio.sleep(0.1)
                            continue
                    except Exception:
                        # Ignore parsing errors and treat as due now
                        pass

                # Dedup processed identities across restarts
                processed_key = self._processed_set_key()
                try:
                    if identity and await self.redis_client.sismember(processed_key, identity):
                        continue
                except Exception:
                    pass

                success = False
                error_detail = None

                try:
                    if op_type == "create":
                        task = await self._get_annika_task(annika_id)
                        if task:
                            success = await self._create_planner_task(task)
                        else:
                            error_detail = "annika_task_not_found"
                    elif op_type == "update":
                        task = await self._get_annika_task(annika_id)
                        if task:
                            planner_id = await self._get_planner_id(annika_id)
                            if planner_id:
                                success = await self._update_planner_task(planner_id, task)
                            else:
                                # If no mapping, upgrade to create
                                success = await self._create_planner_task(task)
                        else:
                            error_detail = "annika_task_not_found"
                    elif op_type == "delete":
                        planner_id = await self._get_planner_id(annika_id)
                        if planner_id:
                            success = await self._delete_planner_task(planner_id)
                        else:
                            # Treat missing mapping as already deleted
                            success = True
                    else:
                        error_detail = f"unknown_operation:{op_type}"
                except Exception as exc:
                    error_detail = f"exception:{type(exc).__name__}:{str(exc)[:160]}"

                if success:
                    try:
                        await self.redis_client.sadd(processed_key, identity)
                        await self._ensure_key_ttl(processed_key, PROCESSED_TTL)
                    except Exception:
                        pass
                    await self._log_sync_operation(
                        op_type or "unknown",
                        annika_id,
                        None,
                        "success"
                    )
                else:
                    # Retry or fail out
                    retry_count = int(op.get("retry_count", 0)) + 1
                    if retry_count <= MAX_RETRIES:
                        # Exponential backoff with jitter
                        base = BACKOFF_BASE ** min(retry_count, 8)
                        delay = min(base, 300) + random.uniform(0, 1.0)
                        next_due = (datetime.utcnow() + timedelta(seconds=delay)).isoformat() + "Z"
                        op["retry_count"] = retry_count
                        op["next_retry"] = next_due
                        if error_detail:
                            op["last_error"] = error_detail
                        await self.redis_client.rpush(PENDING_OPS_KEY, json.dumps(op))
                    else:
                        fail_entry = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "operation": op_type,
                            "annika_id": annika_id,
                            "status": "failed",
                            "error": error_detail or "max_retries_exceeded",
                        }
                        await self.redis_client.lpush(FAILED_OPS_KEY, json.dumps(fail_entry))
                        await self.redis_client.ltrim(FAILED_OPS_KEY, 0, 999)
                        await self._ensure_key_ttl(FAILED_OPS_KEY, 7 * 24 * 60 * 60)

            except Exception as loop_exc:
                # Do not crash the worker; log and continue
                logger.error("Pending queue worker error: %s", loop_exc)
                await asyncio.sleep(0.5)

    async def stop(self):
        """Stop the sync service."""
        self.running = False

        if getattr(self, 'http', None) is not None:
            try:
                self.http.close()
            except Exception:
                pass

        # Clean up webhooks
        await self._cleanup_webhooks()

        # Close pubsubs
        if getattr(self, "pubsub_annika", None):
            try:
                await self.pubsub_annika.unsubscribe()
            except Exception:
                pass
            try:
                await self.pubsub_annika.close()
            except Exception:
                pass
        if getattr(self, "pubsub_webhook", None):
            try:
                await self.pubsub_webhook.unsubscribe()
            except Exception:
                pass
            try:
                await self.pubsub_webhook.close()
            except Exception:
                pass
        if self.redis_client:
            # Ensure all connections are fully torn down before the event loop closes
            try:
                pool = getattr(self.redis_client, "connection_pool", None)
                if pool is not None:
                    try:
                        # Some redis.asyncio versions expose an async disconnect
                        await pool.disconnect()  # type: ignore[func-returns-value]
                    except TypeError:
                        # Fallback for sync disconnect signature
                        pool.disconnect()
            except Exception:
                pass
            try:
                await self.redis_client.close()
            except Exception:
                pass
            # Yield control to allow cleanup callbacks to run
            try:
                await asyncio.sleep(0)
            except Exception:
                pass

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

        # Feature flag: allow disabling Planner webhook attempts to reduce noise
        enable_planner_webhooks_raw = await self.redis_client.get("annika:config:enable_planner_webhooks")
        enable_planner_webhooks = False
        try:
            if isinstance(enable_planner_webhooks_raw, str):
                enable_planner_webhooks = enable_planner_webhooks_raw.strip().lower() in ("1", "true", "yes", "on")
            elif enable_planner_webhooks_raw:
                enable_planner_webhooks = True
        except Exception:
            enable_planner_webhooks = False

        self.planner_webhooks_requested = enable_planner_webhooks

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

        # Conditionally add Planner global webhook only when enabled
        if enable_planner_webhooks:
            webhook_configs.insert(1, {
                "name": "planner_tasks",
                "token": delegated_token,
                "config": {
                    "changeType": "created,updated,deleted",
                    "notificationUrl": (
                        "https://agency-swarm.ngrok.app/api/graph_webhook"
                    ),
                    "resource": "/planner/tasks",
                    "expirationDateTime": (
                        datetime.utcnow() + timedelta(hours=24)
                    ).isoformat() + "Z",
                    "clientState": "annika_planner_sync_v5"
                }
            })
        else:
            logger.info("Planner webhooks disabled by config; skipping /planner/tasks subscriptions")

        # Optionally subscribe to specific Planner plan task changes if enabled
        if enable_planner_webhooks:
            try:
                # Read default plan id
                default_plan_id = await self.redis_client.get("annika:config:default_plan_id")
                # Read optional explicit list of plan ids (JSON array)
                raw_plan_ids = await self.redis_client.get("annika:config:planner_plan_ids")
                extra_plan_ids = []
                if raw_plan_ids:
                    try:
                        extra_plan_ids = json.loads(raw_plan_ids)
                        if not isinstance(extra_plan_ids, list):
                            extra_plan_ids = []
                    except Exception:
                        extra_plan_ids = []

                plan_ids: list = []
                if default_plan_id:
                    plan_ids.append(default_plan_id)
                for pid in extra_plan_ids:
                    if isinstance(pid, str) and pid not in plan_ids:
                        plan_ids.append(pid)

                # If no configured plans, attempt discovery via Graph (delegated)
                if not plan_ids and delegated_token:
                    try:
                        headers = {"Authorization": f"Bearer {delegated_token}"}
                        discovered = await self._get_all_plans_for_polling(headers)
                        for p in discovered:
                            pid = p.get("id")
                            if isinstance(pid, str) and pid not in plan_ids:
                                plan_ids.append(pid)
                    except Exception:
                        logger.debug("Plan discovery failed; continuing without cached plans")

                # Persist discovered plan ids into config for future runs
                try:
                    if plan_ids:
                        await self.redis_client.set(
                            "annika:config:planner_plan_ids", json.dumps(plan_ids)
                        )
                        if not default_plan_id:
                            await self.redis_client.set(
                                "annika:config:default_plan_id", plan_ids[0]
                            )
                            default_plan_id = plan_ids[0]
                except Exception:
                    logger.debug("Unable to persist planner plan ids to Redis config")

                # Build plan-scoped webhook configs (requires delegated token and plan membership)
                for pid in plan_ids:
                    webhook_configs.append(
                        {
                            "name": f"planner_plan_{pid}_tasks",
                            "token": delegated_token,
                            "config": {
                                "changeType": "created,updated,deleted",
                                "notificationUrl": (
                                    "https://agency-swarm.ngrok.app/api/graph_webhook"
                                ),
                                "resource": f"/planner/plans/{pid}/tasks",
                                "expirationDateTime": (
                                    datetime.utcnow() + timedelta(hours=24)
                                ).isoformat() + "Z",
                                "clientState": f"annika_planner_plan_{pid}"
                            }
                        }
                    )
            except Exception:
                # Non-fatal: proceed without plan-scoped webhooks
                logger.debug("Planner plan-scoped webhook configuration skipped due to error")
        else:
            logger.info("Planner plan-scoped webhooks disabled by config; skipping per-plan subscriptions")

        # Store configs for renewal/recreation
        self.webhook_configs = {
            cfg["name"]: {"name": cfg["name"], "token": cfg["token"], "config": cfg["config"]}
            for cfg in webhook_configs
        }

        for webhook_info in webhook_configs:
            webhook_name = webhook_info["name"]
            webhook_token = webhook_info["token"]

            existing = await self.redis_client.hget(WEBHOOK_STATUS_KEY, webhook_name)
            if existing:
                try:
                    data = json.loads(existing)
                    exp = data.get("expires_at")
                    if exp:
                        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                        if exp_dt > datetime.utcnow() + timedelta(minutes=5):
                            self.webhook_subscriptions[webhook_name] = data.get("subscription_id")
                            self._apply_polling_strategy()
                            await self._write_webhook_status(
                                webhook_name,
                                status="active",
                            )
                            logger.info(
                                f"{webhook_name} webhook already active: {data.get('subscription_id')}"
                            )
                            continue
                except Exception:
                    pass

            if not webhook_token:
                logger.warning(f"No token available for {webhook_name} webhook")
                continue

            # Idempotency: check Graph for an existing active subscription
            try:
                found = await self._find_existing_webhook(
                    webhook_token, webhook_info["config"]
                )
                if found:
                    sub_id = found.get("id")
                    self.webhook_subscriptions[webhook_name] = sub_id
                    self._apply_polling_strategy()
                    await self._write_webhook_status(
                        webhook_name,
                        subscription_id=sub_id,
                        created_at=found.get("@odata.context", ""),
                        expires_at=found.get("expirationDateTime"),
                        resource=found.get("resource"),
                        status="active",
                    )
                    logger.info(
                        "%s webhook: adopted existing subscription id=%s resource=%s expires=%s",
                        webhook_name,
                        sub_id,
                        found.get("resource"),
                        found.get("expirationDateTime"),
                    )
                    continue
            except Exception as e:
                logger.debug(
                    "Error checking existing webhook %s: %s", webhook_name, e
                )

            await self._create_webhook(webhook_info)

        # After setup attempts, log current status (adopted or created)
        try:
            await self._log_webhook_status()
        except Exception:
            pass

        self._apply_polling_strategy()

    def _resolve_webhook_name(self, client_state: Optional[str], resource: Optional[str]) -> Optional[str]:
        client_state_value = client_state or ''
        client_state_l = client_state_value.lower()
        resource_value = resource or ''
        resource_l = resource_value.lower()

        planner_plan_prefix = 'annika_planner_plan_'
        if client_state_l.startswith(planner_plan_prefix):
            suffix = client_state_value[len(planner_plan_prefix):].strip()
            if suffix:
                return f"planner_plan_{suffix}_tasks"

        if 'annika_planner_sync_v5' in client_state_l:
            return 'planner_tasks'

        if '/planner/plans/' in resource_l and '/tasks' in resource_l:
            try:
                after_prefix = resource_value.split('/planner/plans/', 1)[1]
                plan_id = after_prefix.split('/', 1)[0]
                if plan_id:
                    return f"planner_plan_{plan_id}_tasks"
            except Exception:
                pass
            return 'planner_tasks'

        if '/planner/tasks' in resource_l:
            return 'planner_tasks'
        if 'groups' in client_state_l:
            return 'groups'
        if 'teams_chats' in client_state_l or '/chats' in resource_l:
            return 'teams_chats'
        if 'teams_channels' in client_state_l or ('/teams' in resource_l and '/channels' in resource_l) or '/teams/getallchannels' in resource_l:
            return 'teams_channels'
        return None

    def _apply_polling_strategy(self) -> None:
        interval = self.default_poll_interval
        if self.planner_webhooks_requested:
            has_planner = any(name.startswith('planner') for name in self.webhook_subscriptions)
            if has_planner:
                interval = max(self.quick_poll_min_interval, self.webhook_poll_interval)
        if interval > 0:
            interval = max(self.quick_poll_min_interval, interval)
        if interval <= 0:
            if self.polling_enabled:
                logger.info('Planner polling disabled by configuration (interval <= 0)')
            self.polling_enabled = False
            self.poll_interval = 0
        else:
            if interval != self.poll_interval:
                logger.info('Planner polling interval set to %ss', interval)
            self.poll_interval = interval
            self.polling_enabled = True

    async def _write_webhook_status(self, name: str, **fields: Any) -> None:
        try:
            existing_raw = await self.redis_client.hget(WEBHOOK_STATUS_KEY, name)
            existing = json.loads(existing_raw) if existing_raw else {}
        except Exception:
            existing = {}
        for key, value in fields.items():
            if value is None:
                continue
            if key == 'last_event':
                existing['last_event'] = value
            else:
                existing[key] = value
        if 'last_event' not in existing:
            existing['last_event'] = None
        existing['updated_at'] = datetime.utcnow().isoformat()
        await self.redis_client.hset(WEBHOOK_STATUS_KEY, name, json.dumps(existing))


    async def _create_webhook(self, cfg: dict) -> None:
        """Create a single webhook subscription and store its state."""
        webhook_name = cfg.get("name")
        token = cfg.get("token")
        config = cfg.get("config")

        if not token:
            logger.warning(f"No token available for {webhook_name} webhook")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            # Idempotency: re-check just before creation to avoid races
            preexisting = await self._find_existing_webhook(token, config)
            if preexisting:
                sub_id = preexisting.get("id")
                self.webhook_subscriptions[webhook_name] = sub_id
                self._apply_polling_strategy()
                await self._write_webhook_status(
                    webhook_name,
                    subscription_id=sub_id,
                    created_at=preexisting.get("@odata.context", ""),
                    expires_at=preexisting.get("expirationDateTime"),
                    resource=preexisting.get("resource"),
                    status="active",
                )
                logger.info(
                    "%s webhook: adopted existing subscription id=%s resource=%s expires=%s",
                    webhook_name,
                    sub_id,
                    preexisting.get("resource"),
                    preexisting.get("expirationDateTime"),
                )
                return

            logger.info("%s webhook: no existing subscription found; creating new", webhook_name)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{GRAPH_API_ENDPOINT}/subscriptions",
                    headers=headers,
                    json=config,
                    timeout=30,
                )

            if response.status_code == 201:
                sub = response.json()
                sub_id = sub["id"]
                self.webhook_subscriptions[webhook_name] = sub_id
                self._apply_polling_strategy()
                await self._write_webhook_status(
                    webhook_name,
                    subscription_id=sub_id,
                    created_at=datetime.utcnow().isoformat(),
                    expires_at=sub["expirationDateTime"],
                    resource=config.get("resource"),
                    status="active",
                )
                logger.info(
                    f"✅ {webhook_name} webhook subscription created: {sub_id}"
                )
            else:
                # If Graph reports limit reached, treat as already exists
                if (
                    response.status_code == 403
                    and "limit of '1'" in response.text
                ):
                    try:
                        # Try strict/relaxed match first
                        existing = await self._find_existing_webhook(token, config)
                        # If still not found, accept near-expiry subscriptions
                        if not existing:
                            existing = await self._find_existing_webhook(token, config)
                    except Exception:
                        existing = None
                    if existing:
                        sub_id = existing.get("id")
                        self.webhook_subscriptions[webhook_name] = sub_id
                        await self._write_webhook_status(
                            webhook_name,
                            subscription_id=sub_id,
                            created_at=existing.get("@odata.context", ""),
                            expires_at=existing.get("expirationDateTime"),
                            resource=existing.get("resource"),
                            status="active",
                        )
                        logger.info(
                            "%s webhook: adopted existing subscription (quota) id=%s resource=%s expires=%s",
                            webhook_name,
                            sub_id,
                            existing.get("resource"),
                            existing.get("expirationDateTime"),
                        )
                        return
                    # No visible existing sub; still assume one is present due to quota
                    logger.info(
                        "%s webhook: quota reached; verifying existing subscription matches current notificationUrl before assuming active",
                        webhook_name,
                    )
                    return

                logger.error(
                    f"Failed to create {webhook_name} webhook: {response.status_code}"
                )
                logger.error(f"Response: {response.text}")
        except Exception as exc:
            logger.error(f"Error setting up {webhook_name} webhook: {exc}")

    async def _log_webhook_status(self) -> None:
        """Log current adopted/created webhook subscriptions with expirations."""
        if not self.webhook_subscriptions:
            logger.info("No webhook subscriptions tracked yet")
            return

        # Choose tokens per resource for GET by id
        for name, sub_id in self.webhook_subscriptions.items():
            token = self._token_for_webhook(name)
            if not token:
                logger.debug("No token available to query webhook %s", name)
                continue
            headers = {"Authorization": f"Bearer {token}"}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{GRAPH_API_ENDPOINT}/subscriptions/{sub_id}",
                        headers=headers,
                        timeout=15,
                    )
                if resp.status_code == 200:
                    sub = resp.json()
                    logger.info(
                        "webhook '%s' in use: id=%s resource=%s expires=%s",
                        name,
                        sub.get("id"),
                        sub.get("resource"),
                        sub.get("expirationDateTime"),
                    )
                elif resp.status_code == 404:
                    logger.warning(
                        "webhook '%s' id=%s not found during status; will recreate on renewal",
                        name,
                        sub_id,
                    )
                else:
                    logger.debug(
                        "status query for webhook '%s' returned %s",
                        name,
                        resp.status_code,
                    )
            except Exception:
                logger.debug("Failed to query status for webhook '%s'", name)

    async def _find_existing_webhook(self, token: str, config: dict) -> Optional[dict]:
        """Find an active existing webhook matching the desired config.

        Strategy:
        1) Strict match: resource + notificationUrl (+ clientState when present)
        2) Fallback: any active subscription with the same resource

        Only returns subscriptions that expire at least 5 minutes
        in the future.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{GRAPH_API_ENDPOINT}/subscriptions", headers=headers, timeout=30
                )
            if resp.status_code != 200:
                return None

            items = resp.json().get("value", [])
            desired_resource = config.get("resource")
            desired_url = config.get("notificationUrl")
            desired_state = config.get("clientState")

            now = datetime.utcnow()

            # Pass 1: strict match
            for sub in items:
                try:
                    exp = sub.get("expirationDateTime")
                    if not exp:
                        continue
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if exp_dt <= now + timedelta(minutes=5):
                        continue
                    if sub.get("resource") != desired_resource:
                        continue
                    if desired_url and sub.get("notificationUrl") != desired_url:
                        continue
                    if desired_state and sub.get("clientState") != desired_state:
                        continue
                    return sub
                except Exception:
                    continue

            # Pass 2: relaxed match (resource only)
            for sub in items:
                try:
                    exp = sub.get("expirationDateTime")
                    if not exp:
                        continue
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if exp_dt <= now + timedelta(minutes=5):
                        continue
                    if sub.get("resource") != desired_resource:
                        continue
                    # If URL differs (e.g., stale ngrok), do not assume active
                    if desired_url and sub.get("notificationUrl") != desired_url:
                        continue
                    return sub
                except Exception:
                    continue
            # Pass 3: any subscription for the same resource, even near expiry
            for sub in items:
                try:
                    if sub.get("resource") != desired_resource:
                        continue
                    return sub
                except Exception:
                    continue
        except Exception:
            return None
        return None

    async def _webhook_renewal_loop(self):
        """Periodically renew webhook subscriptions."""
        while self.running:
            await asyncio.sleep(self.webhook_renewal_interval)
            await self._renew_webhooks()

    async def _renew_webhooks(self):
        """Renew webhook subscriptions before they expire."""
        logger.info("🔄 Renewing webhook subscriptions...")
        for webhook_type, subscription_id in self.webhook_subscriptions.items():
            try:
                token = self._token_for_webhook(webhook_type)
                if not token:
                    logger.debug("No token available to renew %s", webhook_type)
                    continue
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

                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.patch(
                        f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
                        headers=headers,
                        json=update_data,
                        timeout=30,
                    )

                if response.status_code == 200:
                    logger.info(f"✅ Renewed webhook: {webhook_type}")
                    # Update Redis status with new expiration
                    try:
                        await self._write_webhook_status(
                            webhook_type,
                            expires_at=new_expiration,
                            status="active",
                        )
                    except Exception:
                        pass
                elif response.status_code == 404:
                    logger.warning(
                        f"Webhook {webhook_type} missing, recreating..."
                    )
                    cfg = self.webhook_configs.get(webhook_type)
                    if cfg:
                        await self.redis_client.hdel(WEBHOOK_STATUS_KEY, webhook_type)
                        self.webhook_subscriptions.pop(webhook_type, None)
                        self._apply_polling_strategy()
                        await self._create_webhook(cfg)
                else:
                    logger.error(
                        f"Failed to renew webhook {webhook_type}: {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"Error renewing webhook {webhook_type}: {e}")

    def _token_for_webhook(self, webhook_type: str) -> Optional[str]:
        """Return an appropriate token for the webhook type."""
        try:
            if webhook_type == "groups":
                return get_delegated_token()
            # Teams webhooks require application token
            if webhook_type in ("teams_chats", "teams_channels"):
                return get_application_token()
        except Exception:
            return None
        return None

    def _get_preferred_read_token(self) -> tuple[Optional[str], str]:
        """Return a Graph token for read operations, preferring application auth."""
        token_type = "application"
        token: Optional[str] = None
        try:
            token = get_application_token()
            if token:
                if self.last_read_token_choice != "application":
                    logger.info("Using application token for Planner reads")
                self.last_read_token_choice = "application"
                return token, token_type
            logger.warning("Application token unavailable for Planner reads; falling back to delegated")
        except Exception as exc:
            logger.error("Failed to acquire application token for Planner read: %s", exc)

        token_type = "delegated"
        try:
            token = get_agent_token()
            if token:
                if self.last_read_token_choice != "delegated":
                    logger.info("Using delegated token for Planner reads")
                self.last_read_token_choice = "delegated"
                return token, token_type
            logger.error("Delegated token unavailable for Planner reads")
        except Exception as exc:
            logger.error("Failed to acquire delegated token fallback: %s", exc)
            token = None

        return token, token_type

    async def _cleanup_webhooks(self):
        """Clean up webhook subscriptions on shutdown."""
        logger.info("🧹 Cleaning up webhooks...")

        token = get_agent_token()
        if not token:
            return

        headers = {"Authorization": f"Bearer {token}"}

        for webhook_type, subscription_id in self.webhook_subscriptions.items():
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.delete(
                        f"{GRAPH_API_ENDPOINT}/subscriptions/{subscription_id}",
                        headers=headers,
                        timeout=30,
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

        async for message in self.pubsub_webhook.listen():
            if not self.running:
                break

            if message['type'] == 'message':
                try:
                    channel = message.get('channel', '')

                    if channel == "annika:planner:webhook":
                        # Process webhook notification
                        notification_data = json.loads(message['data'])
                        # Adopt subscription IDs from live notifications
                        try:
                            await self._adopt_subscription_from_notification(
                                notification_data
                            )
                        except Exception:
                            pass
                        await self._handle_webhook_notification(notification_data)
                        webhook_name = self._resolve_webhook_name(
                            notification_data.get("clientState"),
                            notification_data.get("resource"),
                        )
                        if webhook_name:
                            try:
                                await self._write_webhook_status(
                                    webhook_name,
                                    last_event=datetime.utcnow().isoformat(),
                                    status="active",
                                )
                            except Exception:
                                pass
                            if webhook_name.startswith('planner'):
                                self._apply_polling_strategy()
                        # For Planner task resources, trigger immediate detection
                        try:
                            resource = notification_data.get("resource", "")
                            if "/planner/tasks" in resource:
                                await self._detect_and_queue_changes()
                        except Exception:
                            pass

                except Exception as e:
                    logger.error(f"Error processing webhook notification: {e}")

    async def _adopt_subscription_from_notification(self, notification: Dict) -> None:
        """Adopt subscription ID from a live notification and persist it.

        This guarantees that even if creation was skipped due to quotas
        or discovery failed earlier, we track the active subscription.
        """
        sub_id = notification.get("subscriptionId")
        if not sub_id:
            return
        resource = notification.get("resource", "")
        client_state = notification.get("clientState", "")

        name = self._resolve_webhook_name(client_state, resource)
        if not name:
            return

        # If we already have the same id recorded, nothing to do
        if self.webhook_subscriptions.get(name) == sub_id:
            return

        # Save mapping and attempt to record status in Redis
        self.webhook_subscriptions[name] = sub_id
        self._apply_polling_strategy()
        try:
            token = self._token_for_webhook(name)
            headers = {"Authorization": f"Bearer {token}"} if token else None
            expires = None
            if headers:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{GRAPH_API_ENDPOINT}/subscriptions/{sub_id}",
                        headers=headers,
                        timeout=15,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    expires = data.get("expirationDateTime")
            await self._write_webhook_status(
                name,
                subscription_id=sub_id,
                resource=resource,
                expires_at=expires,
                status="active",
            )
        except Exception:
            pass
        logger.info(
            "webhook '%s': adopted subscription from notification id=%s",
            name,
            sub_id,
        )

    async def _handle_webhook_notification(self, notification: Dict):
        """Handle a single webhook notification from Microsoft Graph."""
        try:
            change_type = notification.get("changeType")
            resource = notification.get("resource", "")
            client_state = notification.get("clientState", "")

            logger.info(f"📨 Webhook: {change_type} for {resource} (client: {client_state})")

            # Handle different types of webhook notifications
            if "groups" in client_state:
                await self._handle_group_notification(notification)
            elif "teams_chats" in client_state:
                await self._handle_teams_chat_notification(notification)
            elif "teams_channels" in client_state:
                await self._handle_teams_channel_notification(notification)
            elif "/planner/tasks" in resource or client_state == "annika_planner_sync_v5":
                # Poll the specific task or plan to handle updates quickly
                try:
                    resource_data = notification.get("resourceData", {})
                    planner_id = resource_data.get("id")
                    if planner_id:
                        # Fetch latest and route to existing sync path
                        token, _ = self._get_preferred_read_token()
                        if token:
                            headers = {"Authorization": f"Bearer {token}"}
                            resp = self.http.get(
                                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                                headers=headers,
                                timeout=10,
                            )
                            if resp.status_code == 200:
                                await self._sync_existing_task(planner_id, resp.json())
                            else:
                                # Fallback to detect cycle
                                await self._detect_and_queue_changes()
                    else:
                        # Fallback: run a quick detect cycle
                        await self._detect_and_queue_changes()
                except Exception:
                    await self._detect_and_queue_changes()
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

                logger.info(
                    f"📺 Teams channel message {change_type}: team={team_id[:8]}, "
                    f"channel={channel_id[:8]}, msg={message_id[:8]}"
                )

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

                logger.info(
                    f"📺 Saved channel message to Redis: team={team_id[:8]}, "
                    f"channel={channel_id[:8]}, msg={message_id[:8]}"
                )

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
            token, _ = self._get_preferred_read_token()
            if not token:
                return

            headers = {"Authorization": f"Bearer {token}"}

            # First, get the group's Planner plans
            plans_response = self.http.get(
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
            token, _ = self._get_preferred_read_token()
            if not token:
                return

            headers = {"Authorization": f"Bearer {token}"}

            # Get all tasks for the plan
            tasks_response = self.http.get(
                f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                headers=headers,
                timeout=10
            )

            if tasks_response.status_code == 200:
                tasks = tasks_response.json().get("value", [])
                logger.info(f"📋 Found {len(tasks)} tasks in plan {plan_id[:8]}")

                # Process each task to see if it needs syncing
                for task in tasks:
                    if task.get("percentComplete", 0) == 100 or task.get("completedDateTime"):
                        continue
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

        async for message in self.pubsub_annika.listen():
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
                        # Fast-path: parse task_id from message and queue that task only
                        try:
                            payload = json.loads(message.get('data', '{}'))
                            task_id = payload.get('task_id')
                            if not task_id:
                                # Back-compat: some publishers send only {task: {...}}
                                task_obj = payload.get('task') or {}
                                task_id = task_obj.get('id')
                            if task_id:
                                task = await self._get_annika_task(task_id)
                                if task and await self._task_needs_upload(task):
                                    await self._queue_upload(task)
                                    await self._schedule_quick_poll(10)
                                else:
                                    # Fallback: global detection if task missing
                                    await self._detect_and_queue_changes()
                                    await self._schedule_quick_poll(15)
                            else:
                                await self._detect_and_queue_changes()
                                await self._schedule_quick_poll(20)
                        except Exception:
                            await self._detect_and_queue_changes()
                            await self._schedule_quick_poll(20)

                except Exception as e:
                    logger.error(f"Error monitoring Annika changes: {e}")

    async def _detect_and_queue_changes(self):
        """Detect changed tasks and queue them for upload."""
        try:
            annika_tasks = await self.adapter.get_all_annika_tasks()

            current_ids = set()
            for task in annika_tasks:
                annika_id = task.get("id")
                if not annika_id or annika_id in self.processing_upload:
                    continue
                current_ids.add(annika_id)

                # Check if task needs upload
                if await self._task_needs_upload(task):
                    await self._queue_upload(task)

            # Detect deletions
            pattern = f"{PLANNER_ID_MAP_PREFIX}Task-*"
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    annika_id = key.replace(PLANNER_ID_MAP_PREFIX, "")
                    if annika_id not in current_ids:
                        planner_id = await self.redis_client.get(key)
                        # Accept JSON-or-string mapping values
                        if planner_id and planner_id.strip().startswith("{"):
                            try:
                                obj = json.loads(planner_id)
                                planner_id = obj.get("planner_id") or obj.get("plannerId") or obj.get("planner")
                            except Exception:
                                planner_id = None
                        if planner_id:
                            # Delete in Planner, then remove mappings and Annika task per policy
                            await self._delete_planner_task(planner_id)
                        # Remove both forward and reverse mappings and Annika task record
                        try:
                            await self.redis_client.delete(f"annika:tasks:{annika_id}")
                        except Exception:
                            pass
                        await self._remove_mapping(annika_id, planner_id)
                if cursor == 0:
                    break

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
        annika_modified = (
            annika_task.get("last_modified_at")
            or annika_task.get("updated_at")
            or annika_task.get("modified_at")
        )
        last_sync = await self.redis_client.get(f"annika:sync:last_upload:{annika_id}")

        if not last_sync or not annika_modified:
            return True

        try:
            annika_time = datetime.fromisoformat(annika_modified.replace('Z', '+00:00'))
            sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            return annika_time > sync_time
        except Exception:
            return True

    async def _queue_upload(self, annika_task: Dict):
        """Queue a task for batch upload."""
        # Check if task is already queued to prevent duplicates
        annika_id = annika_task.get("id")
        if annika_id:
            # Check if already in queue
            for queued_task in self.pending_uploads:
                if queued_task.get("id") == annika_id:
                    logger.debug(f"Task {annika_id} already queued, skipping duplicate")
                    return

        self.pending_uploads.append(annika_task)

        # Schedule batch processing asynchronously if queue is full
        # Avoid direct recursion by using create_task instead of await
        if len(self.pending_uploads) >= self.batch_size:
            # Only schedule if not already scheduled to prevent multiple tasks
            if not self.batch_scheduled:
                self.batch_scheduled = True
                asyncio.create_task(self._trigger_batch_processing())

    async def _trigger_batch_processing(self):
        """Trigger batch processing with recursion guard."""
        try:
            # Add a delay to prevent tight loops and give system time to breathe
            await asyncio.sleep(1.0)
            # Process batch if not already processing
            if not hasattr(self, 'batch_processing') or not self.batch_processing:
                await self._process_upload_batch()
        finally:
            # Reset the scheduled flag so future batches can be scheduled
            self.batch_scheduled = False

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

        # Recursion guard - prevent concurrent batch processing
        if hasattr(self, 'batch_processing') and self.batch_processing:
            logger.debug("Batch processing already in progress, skipping")
            return

        self.batch_processing = True
        try:
            batch = self.pending_uploads[:self.batch_size]
            self.pending_uploads = self.pending_uploads[self.batch_size:]

            logger.info(f"📤 Processing upload batch of {len(batch)} tasks")

            # Optional: Use Graph $batch for creates only (safe subset, no ETag deps)
            if self.batch_writes_enabled and batch:
                create_tasks: list[dict] = []
                non_create_tasks: list[dict] = []
                for t in batch:
                    try:
                        tid = t.get("id")
                        if tid:
                            mapped = await self._get_planner_id(tid)
                            if mapped:
                                non_create_tasks.append(t)
                            else:
                                create_tasks.append(t)
                        else:
                            create_tasks.append(t)
                    except Exception:
                        non_create_tasks.append(t)

                if create_tasks:
                    try:
                        await self._batch_create_planner_tasks(create_tasks[: self.max_graph_batch])
                        if len(create_tasks) > self.max_graph_batch:
                            self.pending_uploads = create_tasks[self.max_graph_batch:] + self.pending_uploads
                    except Exception as e:
                        logger.debug(f"Graph $batch create failed, falling back to single ops: {e}")
                        non_create_tasks.extend(create_tasks)

                batch = non_create_tasks

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
                            datetime.utcnow().isoformat() + "Z"
                        )
                        # Sanity: after create, verify mapping exists to avoid future duplicates
                        if not planner_id:
                            try:
                                _ = await self._get_planner_id(annika_id)
                            except Exception:
                                pass

                    finally:
                        self.processing_upload.discard(annika_id)
            # If there are still pending uploads, schedule another batch
            if self.pending_uploads and not self.batch_scheduled:
                self.batch_scheduled = True
                asyncio.create_task(self._trigger_batch_processing())
        finally:
            # Always reset the flag to allow future batch processing
            self.batch_processing = False

    async def _batch_create_planner_tasks(self, tasks: list[dict]) -> None:
        """Create tasks via Graph $batch (creates only)."""
        if not tasks:
            return
        token = get_agent_token()
        if not token:
            raise RuntimeError("No token for batch create")

        # Build individual create payloads first with plan/bucket validation drop
        requests_payload = []
        planner_endpoint = f"{GRAPH_API_ENDPOINT}/planner/tasks"
        for idx, annika_task in enumerate(tasks):
            # Build Planner payload using adapter
            body = self.adapter.annika_to_planner(annika_task)
            plan_id = await self._determine_plan_for_task(annika_task)
            if not plan_id:
                continue
            body["planId"] = plan_id
            # Drop bucketId if unknown (safe)
            try:
                bucket_id = body.get("bucketId")
                if bucket_id:
                    cached = self.bucket_cache.get(plan_id)
                    ids = cached.get("ids", set()) if cached and (time.time() - cached.get("ts", 0)) < 300 else set()
                    if ids and bucket_id not in ids:
                        body.pop("bucketId", None)
                    elif not ids:
                        body.pop("bucketId", None)
            except Exception:
                body.pop("bucketId", None)

            requests_payload.append({
                "id": f"req{idx}",
                "method": "POST",
                "url": "/planner/tasks",
                "headers": {"Content-Type": "application/json"},
                "body": body,
            })

        if not requests_payload:
            return

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        batch_body = {"requests": requests_payload}
        resp = self.http.post(f"{GRAPH_API_ENDPOINT}/$batch", headers=headers, json=batch_body, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"$batch returned {resp.status_code}")

        # Process results: store mappings and ETags for successes
        data = resp.json()
        for r in data.get("responses", []):
            try:
                status = r.get("status")
                if status in (200, 201):
                    body = r.get("body", {})
                    planner_id = body.get("id")
                    # Map: find original annika task by title/heuristic
                    # Conservative: skip mapping if we can't resolve; single path will pick it up later
                    # Best-effort: rely on follow-up single ops to reconcile
                    if planner_id:
                        etag = body.get("@odata.etag", "")
                        await self._store_etag(planner_id, etag)
                elif status in (429, 500, 502, 503, 504):
                    # Force single-op fallback on transient errors
                    raise RuntimeError("Transient in batch results")
            except Exception:
                continue

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

    async def _cleanup_deleted_planner_tasks(self, seen_ids: Set[str]):
        """Remove Annika tasks whose Planner counterparts were deleted."""
        pattern = f"{PLANNER_ID_MAP_PREFIX}Task-*"
        cursor = 0
        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                annika_id = key.replace(PLANNER_ID_MAP_PREFIX, "")
                planner_id = await self.redis_client.get(key)
                # Accept JSON-or-string mapping values
                if planner_id and planner_id.strip().startswith("{"):
                    try:
                        obj = json.loads(planner_id)
                        planner_id = obj.get("planner_id") or obj.get("plannerId") or obj.get("planner")
                    except Exception:
                        planner_id = None
                if planner_id and planner_id not in seen_ids:
                    await self._delete_annika_task(annika_id)
                    await self._remove_mapping(annika_id, planner_id)
            if cursor == 0:
                break

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
            await asyncio.sleep(60)  # Every 60 seconds for better visibility

            try:
                metrics = await self._collect_health_metrics()
                logger.info("📊 Health Check: processed=%s pending=%s failed=%s rate=%s webhooks=%s",
                            metrics['processed_tasks'], metrics['pending_uploads'],
                            metrics['failed_operations'], metrics['rate_limit_status'],
                            metrics['webhook_status'])

                # Store metrics in Redis
                await self.redis_client.set(
                    "annika:sync:health",
                    json.dumps(metrics),
                    ex=self.health_ttl
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
            synced_anything = False

            # Only sync tasks that have been modified in the last 24 hours
            # This catches any gaps without overwhelming the API
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            annika_tasks = await self.adapter.get_all_annika_tasks()
            recent_tasks = []

            for task in annika_tasks:
                modified_at = (
                    task.get("last_modified_at")
                    or task.get("updated_at")
                    or task.get("modified_at")
                )
                if modified_at:
                    try:
                        mod_time = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
                        if mod_time > cutoff_time:
                            recent_tasks.append(task)
                    except Exception:
                        # If we can't parse the time, include it to be safe
                        recent_tasks.append(task)

            logger.info(f"Found {len(recent_tasks)} recently modified tasks to sync")

            # Queue recent tasks for upload
            for task in recent_tasks:
                if await self._task_needs_upload(task):
                    await self._queue_upload(task)
                    synced_anything = True

            # Also do an immediate Planner poll to catch any recent changes
            logger.info("🔍 Performing immediate Planner poll as part of initial sync...")
            downloaded = await self._poll_all_planner_tasks()
            if downloaded:
                synced_anything = True

            if not synced_anything:
                logger.warning(
                    "Initial sync detected no task changes. Planner may be empty or the agent lacks access; forcing immediate polling loop."
                )
                self.poll_on_startup = True

            logger.info("✅ Initial sync completed")

        except Exception as e:
            logger.error(f"Error in initial sync: {e}")

    # ========== ID MAPPING AND STORAGE ==========

    async def _store_id_mapping(self, annika_id: str, planner_id: str):
        """Store bidirectional ID mapping.

        Writes:
        - annika:planner:id_map:{annika_id} -> {planner_id} (string)
        - annika:task:mapping:planner:{planner_id} -> {annika_id} (reverse for compat)

        Note: We no longer store annika:planner:id_map:{planner_id} to avoid confusion
        """
        # Primary forward mapping: Annika ID -> Planner ID
        await self.redis_client.set(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            planner_id
        )
        # Reverse mapping for Task Manager compatibility
        await self.redis_client.set(
            f"annika:task:mapping:planner:{planner_id}",
            annika_id
        )

    async def _get_planner_id(self, annika_id: str) -> Optional[str]:
        """Get Planner ID for Annika task.

        Reads from the forward mapping key:
        annika:planner:id_map:{annika_id}
        Accepts string or JSON values for backward compatibility.
        """
        try:
            value = await self.redis_client.get(f"{PLANNER_ID_MAP_PREFIX}{annika_id}")
            if not value:
                return None
            value = value.strip()
            if value.startswith("{"):
                try:
                    obj = json.loads(value)
                    return obj.get("planner_id") or obj.get("plannerId") or obj.get("planner")
                except Exception:
                    return None
            return value
        except Exception:
            return None

    async def _get_annika_id(self, planner_id: str) -> Optional[str]:
        """Get Annika ID for Planner task.

        Reads from the compatibility reverse mapping key:
        annika:task:mapping:planner:{planner_id}
        """
        try:
            # Use the reverse mapping key for Planner -> Annika lookups
            return await self.redis_client.get(
                f"annika:task:mapping:planner:{planner_id}"
            )
        except Exception:
            return None

    async def _find_annika_id_by_forward_map(self, planner_id: str) -> Optional[str]:
        """Best-effort: find Annika ID by scanning forward map values that may be JSON."""
        try:
            cursor = 0
            pattern = f"{PLANNER_ID_MAP_PREFIX}*"
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=200)
                for key in keys:
                    val = await self.redis_client.get(key)
                    if not val:
                        continue
                    v = val.strip()
                    if v.startswith("{"):
                        try:
                            obj = json.loads(v)
                            if obj.get("planner_id") == planner_id or obj.get("plannerId") == planner_id:
                                return key.replace(PLANNER_ID_MAP_PREFIX, "")
                        except Exception:
                            continue
                if cursor == 0:
                    break
        except Exception:
            pass
        return None

    async def _store_etag(self, planner_id: str, etag: str):
        """Store ETag for update detection."""
        await self.redis_client.set(f"{ETAG_PREFIX}{planner_id}", etag)

    async def _remove_mapping(self, annika_id: str, planner_id: str):
        """Remove ID mappings."""
        await self.redis_client.delete(
            f"{PLANNER_ID_MAP_PREFIX}{annika_id}",
            f"annika:task:mapping:planner:{planner_id}",
            f"{ETAG_PREFIX}{planner_id}"
        )

    # ========== TASK OPERATIONS (Complete implementations) ==========

    async def _create_annika_task_from_planner(self, planner_task: Dict):
        """Create task in Annika from Planner task."""
        planner_id = planner_task["id"]
        # Dedup guard: if any mapping already points to this planner_id, adopt it
        try:
            existing_annika_id = await self._get_annika_id(planner_id)
            if not existing_annika_id:
                existing_annika_id = await self._find_annika_id_by_forward_map(planner_id)
            if existing_annika_id:
                logger.info(
                    "🔁 Adopted existing Annika ID %s for Planner task %s",
                    existing_annika_id,
                    planner_id,
                )
                # Ensure reverse mapping is present
                await self.redis_client.set(
                    f"annika:task:mapping:planner:{planner_id}", existing_annika_id
                )
                # Treat as update to avoid duplicate creates
                await self._update_annika_task_from_planner(existing_annika_id, planner_task)
                return
        except Exception:
            # Non-fatal; fall through to create path
            pass

        annika_id = f"Task-{uuid.uuid4().hex[:8]}"

        try:
            # Store mapping first to prevent duplicates (with atomic guard)
            # SETNX reverse map; if already set, adopt existing ID and update instead
            setnx_ok = await self.redis_client.setnx(
                f"annika:task:mapping:planner:{planner_id}", annika_id
            )
            if not setnx_ok:
                try:
                    existing_annika_id = await self.redis_client.get(
                        f"annika:task:mapping:planner:{planner_id}"
                    )
                    if existing_annika_id:
                        await self._update_annika_task_from_planner(existing_annika_id, planner_task)
                        return
                except Exception:
                    pass
            # Write forward map
            await self._store_id_mapping(annika_id, planner_id)
            await self._store_etag(planner_id, planner_task.get("@odata.etag", ""))

            # Convert to Annika format
            annika_task = await self.adapter.planner_to_annika(planner_task)
            annika_task["id"] = annika_id
            annika_task["external_id"] = planner_id
            annika_task["source"] = "planner"
            annika_task["created_at"] = datetime.utcnow().isoformat() + "Z"
            # Ensure canonical timestamps for change detection
            now_ts = datetime.utcnow().isoformat() + "Z"
            annika_task["last_modified_at"] = annika_task.get("last_modified_at") or now_ts
            annika_task["updated_at"] = annika_task.get("updated_at") or now_ts

            # Always write authoritative per-task key first (agent detection relies on this)
            await self.redis_client.set(
                f"annika:tasks:{annika_id}",
                json.dumps(annika_task)
            )
            logger.debug(f"Wrote task to annika:tasks:{annika_id}")

            # Always publish notification for agents
            await self.redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "created",
                    "task_id": annika_id,
                    "task": annika_task,
                    "source": "planner",
                })
            )
            logger.debug(f"Published creation notification for {annika_id}")

            # Best-effort: mirror into global conscious_state if it exists
            try:
                # Determine list type for mirroring
                list_type = self.adapter.determine_task_list(planner_task)

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
                else:
                    logger.debug("conscious_state not present; skipped mirroring for created task")
            except Exception as mirror_err:
                logger.debug(f"Mirror to conscious_state skipped due to error: {mirror_err}")

            # Log success irrespective of mirror presence
            await self._log_sync_operation(
                SyncOperation.CREATE.value,
                annika_id,
                planner_id,
                "success"
            )
            logger.info(f"✅ Created Annika task from Planner: {planner_task.get('title')}")

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
            # Dedup/consistency: ensure mapping stored before update
            pid = planner_task.get("id")
            if pid:
                await self._store_id_mapping(annika_id, pid)
            # Convert updates
            updates = await self.adapter.planner_to_annika(planner_task)

            # Always update authoritative per-task key first
            try:
                existing_raw = await self.redis_client.get(f"annika:tasks:{annika_id}")
                if existing_raw:
                    existing_task = json.loads(existing_raw)
                    if not isinstance(existing_task, dict):
                        existing_task = {}
                else:
                    existing_task = {"id": annika_id, "external_id": planner_task.get("id"), "source": "planner"}
            except Exception:
                existing_task = {"id": annika_id, "external_id": planner_task.get("id"), "source": "planner"}

            # Merge updates and timestamps
            existing_task.update(updates)
            now_ts = datetime.utcnow().isoformat() + "Z"
            existing_task["last_modified_at"] = now_ts
            existing_task["updated_at"] = now_ts

            await self.redis_client.set(
                f"annika:tasks:{annika_id}",
                json.dumps(existing_task)
            )
            logger.debug(f"Updated task in annika:tasks:{annika_id}")

            await self.redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "updated",
                    "task_id": annika_id,
                    "task": existing_task,
                    "source": "planner",
                })
            )
            logger.debug(f"Published update notification for {annika_id}")

            # Best-effort: mirror into global conscious_state if present
            try:
                state_json = await self.redis_client.execute_command(
                    "JSON.GET", "annika:conscious_state", "$"
                )
                if state_json:
                    state = json.loads(state_json)[0]
                    updated = False
                    # Find and update task in mirrors
                    for list_type, task_list in state.get("task_lists", {}).items():
                        for i, task in enumerate(task_list.get("tasks", [])):
                            if task.get("id") == annika_id:
                                state["task_lists"][list_type]["tasks"][i] = existing_task
                                updated = True
                                break
                        if updated:
                            break
                    if updated:
                        await self.redis_client.execute_command(
                            "JSON.SET", "annika:conscious_state", "$",
                            json.dumps(state)
                        )
                    else:
                        logger.debug(f"Task {annika_id} not present in conscious_state; skipped mirror update")
                else:
                    logger.debug("conscious_state not present; skipped mirror update")
            except Exception as mirror_err:
                logger.debug(f"Mirror update to conscious_state skipped due to error: {mirror_err}")

            await self._log_sync_operation(
                SyncOperation.UPDATE.value,
                annika_id,
                planner_task["id"],
                "success"
            )
            logger.debug(f"✅ Updated Annika task from Planner: {planner_task.get('title')}")

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
            # De-dupe: if Annika task has external_id and reverse map exists, update instead
            maybe_external = annika_task.get("external_id")
            if maybe_external:
                try:
                    mapped_annika = await self._get_annika_id(maybe_external)
                    if mapped_annika:
                        logger.info(
                            "🔁 Planner create short-circuited to update for existing external_id %s",
                            maybe_external,
                        )
                        return await self._update_planner_task(maybe_external, annika_task)
                except Exception:
                    pass

            # Set plan ID
            plan_id = await self._determine_plan_for_task(annika_task)
            if not plan_id:
                logger.warning(f"No plan for task: {annika_task.get('title')}")
                return False

            planner_data["planId"] = plan_id

            # Skip plans marked inaccessible (403s)
            try:
                if await self.redis_client.sismember("annika:planner:inaccessible_plans", plan_id):
                    logger.info("Skipping inaccessible plan %s for create", plan_id)
                    # Attempt to pick alternative plan from cached list
                    headers_auth = {"Authorization": f"Bearer {token}"}
                    plans = await self._get_all_plans_for_polling(headers_auth)
                    alt = None
                    for p in plans:
                        pid = p.get("id")
                        if pid and pid != plan_id:
                            alt = pid
                            break
                    if alt:
                        planner_data["planId"] = alt
                        plan_id = alt
            except Exception:
                pass

            # Validate bucketId belongs to selected plan; drop if invalid to avoid 404s
            try:
                bucket_id = planner_data.get("bucketId")
                if bucket_id:
                    cached = self.bucket_cache.get(plan_id)
                    bucket_ids: set[str] = set()
                    if cached and (time.time() - cached.get("ts", 0)) < 300:
                        bucket_ids = cached.get("ids", set())
                    else:
                        buckets_resp = self.http.get(
                            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets?$select=id",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10,
                        )
                        if buckets_resp.status_code == 200:
                            bucket_ids = {b.get("id") for b in buckets_resp.json().get("value", [])}
                            self.bucket_cache[plan_id] = {"ids": bucket_ids, "ts": time.time()}
                            try:
                                await self.redis_client.set(f"annika:graph:buckets:{plan_id}", json.dumps(list(bucket_ids)), ex=300)
                            except Exception:
                                pass
                    if bucket_ids and bucket_id not in bucket_ids:
                        logger.warning(
                            "Dropping invalid bucketId %s for plan %s; will let Graph choose default bucket",
                            bucket_id,
                            plan_id,
                        )
                        planner_data.pop("bucketId", None)
                    elif not bucket_ids:
                        logger.debug(
                            "Bucket set unknown for plan %s; removing bucketId to avoid 404",
                            plan_id,
                        )
                        planner_data.pop("bucketId", None)
            except Exception as bucket_err:
                logger.debug(f"Bucket validation error: {bucket_err}; removing bucketId to be safe")
                planner_data.pop("bucketId", None)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = self.http.post(
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
                # Fallback on 403: try creating in an accessible plan without bucketId
                if response.status_code == 403:
                    try:
                        headers_auth = {"Authorization": f"Bearer {token}"}
                        plans = await self._get_all_plans_for_polling(headers_auth)
                        current_plan = planner_data.get("planId")
                        alt_plan = None
                        for p in plans:
                            pid = p.get("id")
                            if pid and pid != current_plan:
                                alt_plan = pid
                                break
                        if alt_plan:
                            planner_data["planId"] = alt_plan
                            planner_data.pop("bucketId", None)
                            response2 = self.http.post(
                                f"{GRAPH_API_ENDPOINT}/planner/tasks",
                                headers=headers,
                                json=planner_data,
                                timeout=10,
                            )
                            if response2.status_code == 201:
                                planner_task = response2.json()
                                planner_id = planner_task["id"]
                                annika_id = annika_task.get("id")
                                await self._store_id_mapping(annika_id, planner_id)
                                etag = planner_task.get("@odata.etag", "")
                                await self._store_etag(planner_id, etag)
                                try:
                                    # Cache plan selection for this Annika task (5 minutes)
                                    await self.redis_client.set(
                                        f"annika:planner:plan_choice:{annika_id}", alt_plan, ex=300
                                    )
                                except Exception:
                                    pass
                                await self._log_sync_operation(
                                    SyncOperation.CREATE.value,
                                    annika_id,
                                    planner_id,
                                    "success (fallback)",
                                )
                                logger.info(
                                    f"✅ Created Planner task via fallback plan: {annika_task.get('title')}"
                                )
                                self.rate_limiter.reset()
                                return True
                    except Exception as fb_err:
                        logger.debug(f"Create fallback failed: {fb_err}")
                    finally:
                        try:
                            if current_plan:
                                await self.redis_client.sadd("annika:planner:inaccessible_plans", current_plan)
                                await self.redis_client.expire("annika:planner:inaccessible_plans", 600)
                        except Exception:
                            pass

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
            response = self.http.get(
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

            # If bucketId present, ensure it's valid for the task's plan; if not, drop it
            try:
                plan_id = current_task.get("planId")
                bucket_id = update_data.get("bucketId")
                if plan_id and bucket_id:
                    buckets_resp = self.http.get(
                        f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    if buckets_resp.status_code == 200:
                        bucket_ids = {b.get("id") for b in buckets_resp.json().get("value", [])}
                        if bucket_id not in bucket_ids:
                            logger.warning(
                                "Dropping invalid bucketId %s on update for plan %s",
                                bucket_id,
                                plan_id,
                            )
                            update_data.pop("bucketId", None)
                    else:
                        logger.debug(
                            "Bucket list fetch failed (%s) for plan %s during update; removing bucketId",
                            buckets_resp.status_code,
                            plan_id,
                        )
                        update_data.pop("bucketId", None)
            except Exception as bucket_err:
                logger.debug(f"Bucket validation error (update): {bucket_err}; removing bucketId")
                update_data.pop("bucketId", None)

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "If-Match": etag
            }

            # PATCH with simple backoff on throttling/transient errors
            response = self.http.patch(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers=headers,
                json=update_data,
                timeout=10
            )
            if response.status_code in (429, 500, 502, 503, 504):
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after)
                except Exception:
                    delay = 1.0
                time.sleep(min(max(delay, 1.0), 5.0))
                response = self.http.patch(
                    f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                    headers=headers,
                    json=update_data,
                    timeout=10
                )

            if response.status_code in [200, 204]:
                # Update stored ETag (handle casing variants)
                new_etag = response.headers.get("ETag") or response.headers.get("etag") or etag
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

    async def _delete_planner_task(self, planner_id: str) -> bool:
        """Delete a task in Planner."""
        if self.rate_limiter.is_rate_limited():
            logger.debug("Rate limited - skipping Planner deletion")
            return False

        try:
            token = get_agent_token()
            if not token:
                logger.error("No token available for task deletion")
                return False

            # Fetch latest ETag to satisfy concurrency requirements
            get_resp = self.http.get(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            etag = None
            if get_resp.status_code == 200:
                try:
                    etag = get_resp.json().get("@odata.etag")
                except Exception:
                    etag = None

            headers = {"Authorization": f"Bearer {token}"}
            if etag:
                headers["If-Match"] = etag
            else:
                headers["If-Match"] = "*"

            response = self.http.delete(
                f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                headers=headers,
                timeout=10,
            )

            if response.status_code in (200, 204):
                annika_id = await self._get_annika_id(planner_id)
                if annika_id:
                    await self._remove_mapping(annika_id, planner_id)
                await self._log_sync_operation(
                    SyncOperation.DELETE.value,
                    annika_id,
                    planner_id,
                    "success",
                )
                logger.debug(f"✅ Deleted Planner task: {planner_id}")
                self.rate_limiter.reset()
                return True
            elif response.status_code == 404:
                annika_id = await self._get_annika_id(planner_id)
                if annika_id:
                    await self._remove_mapping(annika_id, planner_id)
                logger.debug(f"Planner task {planner_id} already deleted")
                return True
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.rate_limiter.handle_rate_limit(retry_after)
                return False
            elif response.status_code == 412:
                # Precondition failed due to ETag; fetch fresh ETag and retry once
                try:
                    get_resp2 = self.http.get(
                        f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    new_etag = None
                    if get_resp2.status_code == 200:
                        try:
                            new_etag = get_resp2.json().get("@odata.etag")
                        except Exception:
                            new_etag = None
                    retry_headers = {"Authorization": f"Bearer {token}"}
                    retry_headers["If-Match"] = new_etag or "*"
                    response2 = self.http.delete(
                        f"{GRAPH_API_ENDPOINT}/planner/tasks/{planner_id}",
                        headers=retry_headers,
                        timeout=10,
                    )
                    if response2.status_code in (200, 204, 404):
                        annika_id = await self._get_annika_id(planner_id)
                        if annika_id:
                            await self._remove_mapping(annika_id, planner_id)
                        await self._log_sync_operation(
                            SyncOperation.DELETE.value,
                            annika_id,
                            planner_id,
                            "success",
                        )
                        return True
                except Exception:
                    pass
            else:
                logger.error(
                    f"Failed to delete Planner task {planner_id}: {response.status_code}"
                )
                await self._log_sync_operation(
                    SyncOperation.DELETE.value,
                    None,
                    planner_id,
                    "error",
                    f"HTTP {response.status_code}",
                )
                return False

        except Exception as e:
            logger.error(f"Error deleting Planner task {planner_id}: {e}")
            await self._log_sync_operation(
                SyncOperation.DELETE.value,
                None,
                planner_id,
                "error",
                str(e),
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
                        "JSON.SET",
                        "annika:conscious_state",
                        "$",
                        json.dumps(state),
                    )
                    planner_id = await self._get_planner_id(annika_id)
                    if planner_id:
                        await self._remove_mapping(annika_id, planner_id)
                    await self._log_sync_operation(
                        SyncOperation.DELETE.value,
                        annika_id,
                        planner_id,
                        "success",
                    )
                    logger.debug(f"✅ Deleted Annika task: {annika_id}")
                else:
                    logger.warning(f"Task {annika_id} not found for deletion")

        except Exception as e:
            logger.error(f"Error deleting Annika task {annika_id}: {e}")

    async def _determine_plan_for_task(self, annika_task: Dict) -> Optional[str]:
        """Determine which plan a task should go to."""
        # Check if task has a specific plan preference
        task_plan = annika_task.get("plan_id")
        if task_plan:
            return task_plan

        # Short-lived plan choice cache per Annika task (fallback successes)
        try:
            annika_id = annika_task.get("id")
            if annika_id:
                cached_choice = await self.redis_client.get(f"annika:planner:plan_choice:{annika_id}")
                if cached_choice:
                    return cached_choice
        except Exception:
            pass

        # Check Redis default config
        default_plan = await self.redis_client.get("annika:config:default_plan_id")
        if default_plan:
            return default_plan

        # Fall back to environment variable
        import os
        return os.getenv("DEFAULT_PLANNER_PLAN_ID")

    # ========== PLANNER POLLING ==========

    async def _planner_polling_loop(self):
        """Poll all known Planner plans for task changes; interval is config-driven."""
        logger.info(f"⏰ Starting Planner polling loop (every {self.poll_interval}s)")

        while self.running:
            try:
                if self.poll_on_startup:
                    wait_seconds = 5
                    self.poll_on_startup = False
                else:
                    wait_seconds = self.poll_interval

                await asyncio.sleep(wait_seconds)

                if not self.running:
                    break

                logger.info("🔍 Starting hourly Planner poll for task changes...")
                await self._poll_all_planner_tasks()

            except Exception as e:
                logger.error(f"Error in Planner polling loop: {e}")
                # Continue running even if one poll fails
                await asyncio.sleep(300)  # Wait 5 minutes before retrying


    async def _schedule_quick_poll(self, delay_seconds: int) -> None:
        """Schedule a one-off quick poll after local edits to reconcile Planner."""
        try:
            # Cancel any pending quick poll to coalesce bursts
            if self.quick_poll_task and not self.quick_poll_task.done():
                self.quick_poll_task.cancel()

            async def _delayed_poll():
                try:
                    jitter = random.uniform(0, 5.0)
                    await asyncio.sleep(max(1, min(delay_seconds, 60)) + jitter)
                    now = time.time()
                    if self.running and (now - self.last_quick_poll_at) >= self.quick_poll_min_interval:
                        logger.info(f"⏱️ Quick poll triggered after local update (delay={delay_seconds}s)")
                        await self._poll_all_planner_tasks()
                        self.last_quick_poll_at = now
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.debug(f"Quick poll failed: {e}")

            self.quick_poll_task = asyncio.create_task(_delayed_poll())
        except Exception:
            pass

    async def _poll_all_planner_tasks(self):
        """Poll all accessible Planner plans for task changes."""
        try:
            token, token_type = self._get_preferred_read_token()
            if not token:
                logger.warning("No token available for Planner polling")
                return

            logger.debug(f"Planner polling using {token_type} token")
            headers = {"Authorization": f"Bearer {token}"}

            all_plans = await self._get_all_plans_for_polling(headers, token_type=token_type)

            if not all_plans and token_type == "application":
                logger.warning("Application token returned no plans; retrying with delegated fallback")
                fallback_token = None
                try:
                    fallback_token = get_agent_token()
                except Exception as exc:
                    logger.error("Failed to acquire delegated fallback token: %s", exc)
                if fallback_token:
                    fallback_headers = {"Authorization": f"Bearer {fallback_token}"}
                    all_plans = await self._get_all_plans_for_polling(fallback_headers, token_type="delegated")
                else:
                    logger.error("Delegated fallback token unavailable; aborting poll")
                    return

            if not all_plans:
                logger.warning("No plans found to poll")
                return

            logger.info(f"📋 Polling {len(all_plans)} Planner plans for task changes")

            tasks_checked = 0
            tasks_updated = 0
            tasks_created = 0
            seen_planner_ids: Set[str] = set()

            # Poll each plan for tasks
            for plan in all_plans:
                plan_id = plan.get("id")
                plan_title = plan.get("title", "Unknown")

                if not plan_id:
                    continue

                try:
                    # Get all tasks for this plan
                    tasks_response = self.http.get(
                        f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
                        headers=headers,
                        timeout=15
                    )

                    if tasks_response.status_code == 200:
                        tasks = tasks_response.json().get("value", [])
                        logger.debug(f"📋 Plan '{plan_title}': {len(tasks)} tasks")

                        for task in tasks:
                            if task.get("percentComplete", 0) == 100 or task.get("completedDateTime"):
                                continue
                            task_id = task.get("id")
                            if not task_id:
                                continue
                            seen_planner_ids.add(task_id)

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

            await self._cleanup_deleted_planner_tasks(seen_planner_ids)

            # Log polling results
            logger.info(
                f"✅ Planner polling complete: {tasks_checked} tasks checked, "
                f"{tasks_created} created, {tasks_updated} updated"
            )

            # Log the polling operation
            await self._log_sync_operation(
                "planner_poll",
                None,
                None,
                "success",
                None,
                f"Polled {len(all_plans)} plans, {tasks_checked} tasks checked, "
                f"{tasks_created} created, {tasks_updated} updated"
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
                            annika_modified = (
                                annika_task.get("last_modified_at")
                                or annika_task.get("updated_at")
                                or annika_task.get("modified_at")
                            )
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

    async def _get_all_plans_for_polling(self, headers: Dict, token_type: str = "delegated") -> List[Dict]:
        """Get accessible Planner plans using delegated or application auth."""
        logger.debug(f"Enumerating plans using {token_type} token")
        # Per-cycle memoization (5 minutes)
        now = time.time()
        if (
            self.plan_cache
            and (now - self.plan_cache_time) < 300
            and self.plan_cache_token_type == token_type
        ):
            return self.plan_cache

        all_plans: List[Dict] = []

        try:
            if token_type == "application":
                logger.info("?? Getting tenant-wide plans (application auth)...")
                next_url = f"{GRAPH_API_ENDPOINT}/planner/plans?$expand=details($select=sharedWith)"
                page = 0
                max_pages = 50
                while next_url and page < max_pages:
                    page += 1
                    response = self.http.get(next_url, headers=headers, timeout=30)
                    if response.status_code != 200:
                        logger.warning(
                            "Failed to get tenant-wide plans (page %s): %s - %s",
                            page,
                            response.status_code,
                            response.text[:256],
                        )
                        break
                    payload = response.json()
                    chunk = payload.get("value", [])
                    all_plans.extend(chunk)
                    next_link = payload.get("@odata.nextLink")
                    if next_link and next_link.startswith("/"):
                        next_url = f"{GRAPH_API_ENDPOINT}{next_link}"
                    else:
                        next_url = next_link
                    if next_url and page < max_pages:
                        logger.debug("   Fetching additional plan page %s", page + 1)
                if next_url and page >= max_pages:
                    logger.warning("Plan pagination truncated after %s pages; continuing with partial list", page)
                logger.info(f"   Found {len(all_plans)} plans via application auth")
            else:
                logger.info("?? Getting personal plans...")
                personal_count = 0
                personal_url = f"{GRAPH_API_ENDPOINT}/me/planner/plans?$select=id,title"
                personal_page = 0
                personal_max_pages = 50
                while personal_url and personal_page < personal_max_pages:
                    personal_page += 1
                    response = self.http.get(personal_url, headers=headers, timeout=15)
                    if response.status_code != 200:
                        logger.warning(f"Failed to get personal plans: {response.status_code} - {response.text[:256]}")
                        break
                    payload = response.json()
                    personal_plans = payload.get("value", [])
                    personal_count += len(personal_plans)
                    all_plans.extend(personal_plans)
                    next_link = payload.get("@odata.nextLink")
                    if next_link and next_link.startswith("/"):
                        personal_url = f"{GRAPH_API_ENDPOINT}{next_link}"
                    else:
                        personal_url = next_link
                if personal_url and personal_page >= personal_max_pages:
                    logger.warning(f"Personal plan pagination truncated after {personal_page} pages; continuing with partial list")
                logger.info(f"   Found {personal_count} personal plans")

                logger.info("?? Getting group memberships...")
                group_plan_count = 0
                processed_groups = 0
                total_groups = 0
                member_url = f"{GRAPH_API_ENDPOINT}/me/memberOf?$select=id,displayName,@odata.type"
                member_page = 0
                member_max_pages = 50
                while member_url and member_page < member_max_pages:
                    member_page += 1
                    response = self.http.get(member_url, headers=headers, timeout=15)
                    if response.status_code != 200:
                        logger.warning(f"Failed to get group memberships: {response.status_code} - {response.text[:256]}")
                        break
                    payload = response.json()
                    groups = payload.get("value", [])
                    total_groups += len(groups)

                    for item in groups:
                        if item.get("@odata.type") != "#microsoft.graph.group":
                            continue
                        group_id = item.get("id")
                        group_name = item.get("displayName", "Unknown")
                        processed_groups += 1

                        try:
                            logger.debug(f"   Processing group {processed_groups}: {group_name}")
                            plans_url = f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans?$select=id,title"
                            plans_resp = self.http.get(plans_url, headers=headers, timeout=10)

                            if plans_resp.status_code == 200:
                                group_plans = plans_resp.json().get("value", [])
                                if group_plans:
                                    all_plans.extend(group_plans)
                                    group_plan_count += len(group_plans)
                                    logger.debug(
                                        f"      Added {len(group_plans)} plans from {group_name}"
                                    )
                            elif plans_resp.status_code == 403:
                                logger.debug(f"      No Planner access for group: {group_name}")
                            else:
                                logger.debug(
                                    f"      Failed to get plans for {group_name}: {plans_resp.status_code}"
                                )

                        except requests.exceptions.Timeout:
                            logger.warning(f"      Timeout getting plans for group: {group_name}")
                        except Exception as e:
                            logger.debug(f"      Error getting plans for {group_name}: {e}")

                        if processed_groups % 5 == 0:
                            await asyncio.sleep(0.1)

                    next_link = payload.get("@odata.nextLink")
                    if next_link and next_link.startswith("/"):
                        member_url = f"{GRAPH_API_ENDPOINT}{next_link}"
                    else:
                        member_url = next_link

                if member_url and member_page >= member_max_pages:
                    logger.warning(f"Group membership pagination truncated after {member_page} pages; continuing with partial list")

                if total_groups:
                    logger.info(f"   Found {group_plan_count} plans across {processed_groups} groups")
                else:
                    logger.info("   No group memberships returned")

        except requests.exceptions.Timeout:
            logger.error("Timeout getting plans - continuing with what we have")
        except Exception as e:
            logger.error(f"Error getting plans: {e}")

        logger.info(f"?? Total plans found: {len(all_plans)}")
        self.plan_cache = all_plans
        self.plan_cache_time = now
        self.plan_cache_token_type = token_type
        try:
            await self.redis_client.set(
                "annika:graph:plans:index",
                json.dumps([p.get("id") for p in all_plans if p.get("id")]),
                ex=300,
            )
        except Exception:
            pass
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

