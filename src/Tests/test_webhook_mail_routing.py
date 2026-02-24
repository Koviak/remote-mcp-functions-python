import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import graph_subscription_manager as gsm  # noqa: E402  # type: ignore[import-not-found]
from graph_subscription_manager import GraphSubscriptionManager  # noqa: E402  # type: ignore[import-not-found]
from webhook_handler import (
    GraphWebhookHandler,
    MAIL_MESSAGES_CHANNEL,
    MAIL_MESSAGES_HISTORY_KEY,
)  # noqa: E402  # type: ignore[import-not-found]


class _FakeAsyncRedis:
    def __init__(self):
        self.published = []
        self.lists = {}
        self.expirations = {}

    async def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    async def lpush(self, key, payload):
        items = self.lists.setdefault(key, [])
        items.insert(0, payload)
        return len(items)

    async def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        if end < 0:
            self.lists[key] = items[start:]
        else:
            self.lists[key] = items[start:end + 1]
        return True

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end < 0:
            return items[start:]
        return items[start:end + 1]

    async def close(self):
        return True


@pytest.mark.asyncio
async def test_mail_notification_publishes_to_mail_channel_and_history():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()

    notification = {
        "changeType": "created",
        "resource": "/me/messages/AAMkAGI2TAAA=",
        "resourceData": {"id": "AAMkAGI2TAAA="},
        "subscriptionId": "sub-123",
        "clientState": "annika_mail_messages",
    }

    ok = await handler.handle_webhook_notification(notification)

    assert ok is True
    assert handler.redis_client.published
    channel, payload_raw = handler.redis_client.published[0]
    assert channel == MAIL_MESSAGES_CHANNEL
    payload = json_lib.loads(payload_raw)
    assert payload["type"] == "mail_message"
    assert payload["message_id"] == "AAMkAGI2TAAA="
    assert payload["change_type"] == "created"
    assert payload["subscription_id"] == "sub-123"
    assert MAIL_MESSAGES_HISTORY_KEY in handler.redis_client.lists


@pytest.mark.asyncio
async def test_mail_notification_extracts_message_id_from_resource_path():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()

    notification = {
        "changeType": "updated",
        "resource": "Users('abc')/Messages('MSG-ID-42')",
        "resourceData": {},
        "subscriptionId": "sub-456",
        "clientState": "annika_mail_messages",
    }

    ok = await handler.handle_webhook_notification(notification)

    assert ok is True
    channel, payload_raw = handler.redis_client.published[0]
    assert channel == MAIL_MESSAGES_CHANNEL
    payload = json_lib.loads(payload_raw)
    assert payload["message_id"] == "MSG-ID-42"


class _FakeSyncRedis:
    def __init__(self):
        self.calls = []

    def setex(self, key, ttl, value):
        self.calls.append((key, ttl, value))
        return True


class _FakeResponse:
    status_code = 201

    def json(self):
        return {
            "id": "sub-mail-1",
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }


def _build_manager_with_fake_redis(monkeypatch):
    fake_redis = _FakeSyncRedis()
    fake_manager = type("FakeRedisManager", (), {"_client": fake_redis})()
    monkeypatch.setattr(gsm, "get_redis_token_manager", lambda: fake_manager)
    return GraphSubscriptionManager(), fake_redis


def test_create_mail_subscription_uses_mail_client_state(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(gsm, "get_agent_token", lambda: "test-token")
    monkeypatch.setattr(gsm.requests, "post", _fake_post)

    mgr, fake_redis = _build_manager_with_fake_redis(monkeypatch)

    sub_id = mgr.create_mail_subscription()

    assert sub_id == "sub-mail-1"
    assert captured["json"]["resource"] == "/me/messages"
    assert captured["json"]["clientState"] == gsm.MAIL_CLIENT_STATE
    assert len(fake_redis.calls) == 1


def test_store_subscription_handles_zulu_expiry_without_datetime_error(monkeypatch):
    mgr, fake_redis = _build_manager_with_fake_redis(monkeypatch)

    mgr._store_subscription(
        {
            "id": "sub-mail-zulu",
            "expirationDateTime": "2099-01-01T00:00:00Z",
        }
    )

    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == "annika:subscriptions:sub-mail-zulu"
    assert ttl > 0
    assert "sub-mail-zulu" in value


def test_renew_subscription_updates_cache_with_timezone_aware_expiry(monkeypatch):
    class _RenewResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "id": "sub-renew-1",
                "expirationDateTime": "2099-01-01T00:00:00Z",
            }

    def _fake_patch(url, headers=None, json=None, timeout=None):
        assert url.endswith("/subscriptions/sub-renew-1")
        assert timeout == 10
        assert headers["Authorization"] == "Bearer test-token"
        assert "expirationDateTime" in json
        return _RenewResponse()

    monkeypatch.setattr(gsm, "get_agent_token", lambda: "test-token")
    monkeypatch.setattr(gsm.requests, "patch", _fake_patch)

    mgr, fake_redis = _build_manager_with_fake_redis(monkeypatch)

    ok = mgr.renew_subscription("sub-renew-1")

    assert ok is True
    assert len(fake_redis.calls) == 1
