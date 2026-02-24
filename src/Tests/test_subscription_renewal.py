import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fakeredis.aioredis  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402

import agent_auth_manager  # noqa: E402  # type: ignore[import-not-found]
from chat_subscription_manager import (  # noqa: E402  # type: ignore[import-not-found]
    GRAPH_API_ENDPOINT,
    ChatSubscriptionManager,
)


@pytest.mark.asyncio
async def test_renew_expiring_subscriptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = ChatSubscriptionManager()
    mgr.redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    expiring = (
        (datetime.now(UTC) + timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z")
    )
    await mgr.redis_client.hset(
        "annika:chat_subscriptions:test",
        mapping={"subscription_id": "sub123", "expires_at": expiring},
    )

    monkeypatch.setattr(
        agent_auth_manager,
        "get_agent_token",
        lambda _scope=None: "dummy",
    )
    monkeypatch.setattr(
        "chat_subscription_manager.get_agent_token",
        lambda _scope=None: "dummy",
    )

    with respx.mock(assert_all_called=False) as mock:
        mock.patch(f"{GRAPH_API_ENDPOINT}/subscriptions/sub123").respond(
            200,
            json={},
        )
        await mgr.renew_expiring_subscriptions()

    data = await mgr.redis_client.hgetall("annika:chat_subscriptions:test")
    assert data["status"] == "active"
    assert datetime.fromisoformat(
        data["expires_at"].replace("Z", "+00:00")
    ) > datetime.now(UTC)
