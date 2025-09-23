import logging
import os
from datetime import UTC, datetime, timedelta

import httpx
import redis.asyncio as redis

try:
    # When running as a package (python -m src.start_all_services)
    from src.agent_auth_manager import get_agent_token  # type: ignore
except ModuleNotFoundError:
    # When running from inside src/ (python start_all_services.py)
    from agent_auth_manager import get_agent_token  # type: ignore

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
WEBHOOK_URL = os.environ.get(
    "GRAPH_WEBHOOK_URL", "https://agency-swarm.ngrok.app/api/graph_webhook"
)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "password")
REDIS_PREFIX = "annika:chat_subscriptions:"


class ChatSubscriptionManager:
    """Manage Microsoft Teams chat message subscriptions."""

    def __init__(self) -> None:
        self.redis_client: redis.Redis | None = None

    async def initialize(self) -> None:
        if self.redis_client is None:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("ChatSubscriptionManager connected to Redis")

    async def discover_all_chats(self) -> list[str]:
        """Return all chat ids for the agent user."""
        # Explicitly request delegated chat read scopes to ensure /me/chats works
        token = get_agent_token("Chat.Read Chat.ReadWrite Chat.ReadBasic")
        if not token:
            logger.warning("No agent token available for chat discovery")
            return []

        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{GRAPH_API_ENDPOINT}/me/chats", headers=headers, timeout=10
                )
                if resp.status_code == 200:
                    chats = resp.json().get("value", [])
                    return [c.get("id") for c in chats if c.get("id")]
                logger.warning("Failed to list chats: %s", resp.status_code)
        except Exception as exc:
            logger.error("Error discovering chats: %s", exc)
        return []

    async def create_chat_subscription(self, chat_id: str) -> str | None:
        """Create a chat message subscription for the given chat."""
        # Global and per-chat subscriptions require delegated Chat.Read/Chat.ReadWrite
        token = get_agent_token("Chat.Read Chat.ReadWrite")
        if not token:
            logger.warning("Cannot create chat subscription without token")
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        sub = {
            "changeType": "created,updated",
            "notificationUrl": WEBHOOK_URL,
            "resource": f"/chats/{chat_id}/messages",
            "expirationDateTime": (
                datetime.now(UTC) + timedelta(hours=1)
            ).isoformat().replace("+00:00", "Z"),
            "clientState": f"chat_{chat_id[:8]}",
            "lifecycleNotificationUrl": WEBHOOK_URL,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{GRAPH_API_ENDPOINT}/subscriptions",
                    headers=headers,
                    json=sub,
                    timeout=10,
                )
            if resp.status_code == 201:
                data = resp.json()
                now_iso = datetime.now(UTC).isoformat()
                await self.redis_client.hset(
                    f"{REDIS_PREFIX}{chat_id}",
                    mapping={
                        "subscription_id": data.get("id"),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                        "expires_at": data.get("expirationDateTime"),
                        "status": "active",
                        "mode": "per_chat",
                    },
                )
                logger.info("Created chat subscription for %s", chat_id)
                return data.get("id")
            logger.error(
                "Failed to create chat subscription %s: %s",
                chat_id,
                resp.status_code,
            )
        except Exception as exc:
            logger.error("Error creating chat subscription for %s: %s", chat_id, exc)
        return None

    async def subscribe_to_all_existing_chats(self) -> int:
        """Create a single subscription for all chat messages."""
        if not self.redis_client:
            await self.initialize()

        existing = await self.redis_client.hgetall(f"{REDIS_PREFIX}global")
        if existing.get("subscription_id") and existing.get("expires_at"):
            try:
                exp = datetime.fromisoformat(
                    existing["expires_at"].replace("Z", "+00:00")
                )
                if exp > datetime.now(UTC) - timedelta(minutes=5):
                    logger.info("Global chat subscription already exists")
                    return 1
            except Exception:
                pass

        # Use delegated chat read scopes for global subscription covering /me/chats
        token = get_agent_token("Chat.Read Chat.ReadWrite")
        if not token:
            logger.warning("Cannot create chat subscription without token")
            return 0

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        sub = {
            "changeType": "created,updated",
            "notificationUrl": WEBHOOK_URL,
            "resource": "/me/chats/getAllMessages",
            "expirationDateTime": (
                datetime.now(UTC) + timedelta(hours=1)
            ).isoformat().replace("+00:00", "Z"),
            "clientState": "chat_global",
            "lifecycleNotificationUrl": WEBHOOK_URL,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{GRAPH_API_ENDPOINT}/subscriptions",
                    headers=headers,
                    json=sub,
                    timeout=10,
                )
            if resp.status_code == 201:
                data = resp.json()
                now_iso = datetime.now(UTC).isoformat()
                await self.redis_client.hset(
                    f"{REDIS_PREFIX}global",
                    mapping={
                        "subscription_id": data.get("id"),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                        "expires_at": data.get("expirationDateTime"),
                        "status": "active",
                        "mode": "global",
                    },
                )
                logger.info("Created global chat subscription")
                return 1

            # Permission/visibility failures: 403
            if resp.status_code == 403:
                snippet = resp.text[:200] if hasattr(resp, "text") else ""
                logger.error(
                    "Failed to create global chat subscription: 403. Falling back to per-chat subscriptions. Response: %s",
                    snippet,
                )
                # Mark global key as failed_permission (do not retry aggressively)
                await self.redis_client.hset(
                    f"{REDIS_PREFIX}global",
                    mapping={
                        "status": "failed_permission",
                        "mode": "per_chat",
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                # Fallback: enumerate chats and create per-chat subscriptions
                created = 0
                chat_ids = await self.discover_all_chats()
                for cid in chat_ids:
                    sub_id = await self.create_chat_subscription(cid)
                    if sub_id:
                        created += 1
                logger.info("Per-chat subscriptions created: %d", created)
                return created

            logger.error(
                "Failed to create global chat subscription: %s", resp.status_code
            )
        except Exception as exc:
            logger.error("Error creating global chat subscription: %s", exc)
        return 0

    async def handle_new_chat_created(self, chat_id: str) -> None:
        # Global subscription covers all chats; nothing to do
        logger.debug("New chat %s created; global subscription already active", chat_id)

    async def renew_expiring_subscriptions(self) -> None:
        """Renew subscriptions that expire within 15 minutes."""
        token = get_agent_token("Chat.Read Chat.ReadWrite")
        if not token or not self.redis_client:
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        keys = await self.redis_client.keys(f"{REDIS_PREFIX}*")
        for key in keys:
            data = await self.redis_client.hgetall(key)
            sub_id = data.get("subscription_id")
            expires = data.get("expires_at")
            if not sub_id or not expires:
                continue
            try:
                exp_time = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except Exception:
                continue
            if exp_time - datetime.now(UTC) < timedelta(minutes=15):
                new_exp = (
                    datetime.now(UTC) + timedelta(hours=1)
                ).isoformat().replace("+00:00", "Z")
                async with httpx.AsyncClient() as client:
                    resp = await client.patch(
                        f"{GRAPH_API_ENDPOINT}/subscriptions/{sub_id}",
                        headers=headers,
                        json={"expirationDateTime": new_exp},
                        timeout=10,
                    )
                if resp.status_code == 200:
                    await self.redis_client.hset(
                        key,
                        mapping={
                            "expires_at": new_exp,
                            "status": "active",
                            "updated_at": datetime.now(UTC).isoformat(),
                        },
                    )
                elif resp.status_code == 404:
                    logger.warning("Chat subscription missing, recreating")
                    await self.redis_client.delete(key)
                    await self.subscribe_to_all_existing_chats()
                else:
                    await self.redis_client.hset(
                        key,
                        mapping={
                            "status": "failed",
                            "updated_at": datetime.now(UTC).isoformat(),
                        },
                    )

    async def cleanup_failed_subscriptions(self) -> None:
        if not self.redis_client:
            return
        keys = await self.redis_client.keys(f"{REDIS_PREFIX}*")
        for key in keys:
            data = await self.redis_client.hgetall(key)
            if data.get("status") == "failed":
                await self.redis_client.delete(key)

    async def get_subscription_health(self) -> dict[str, int]:
        if not self.redis_client:
            return {"tracked": 0, "active": 0, "expired": 0}
        keys = await self.redis_client.keys(f"{REDIS_PREFIX}*")
        active = 0
        expired = 0
        for key in keys:
            data = await self.redis_client.hgetall(key)
            expires = data.get("expires_at")
            if not expires:
                continue
            try:
                exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if exp > datetime.now(UTC):
                    active += 1
                else:
                    expired += 1
            except Exception:
                expired += 1
        return {"tracked": len(keys), "active": active, "expired": expired}


chat_subscription_manager = ChatSubscriptionManager()


async def initialize_chat_subscription_manager() -> None:
    await chat_subscription_manager.initialize()

