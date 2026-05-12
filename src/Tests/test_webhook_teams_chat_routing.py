import asyncio
import hashlib
import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webhook_handler import GraphWebhookHandler  # noqa: E402  # type: ignore[import-not-found]


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
        self.lists[key] = items[start:end + 1]
        return True

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True


@pytest.mark.asyncio
async def test_chat_global_resource_without_leading_slash_routes_to_teams_chat():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()
    handler._redis_client_loop = asyncio.get_running_loop()

    notification = {
        "changeType": "created",
        "resource": "chats('19:test-chat-id@thread.v2')/messages('1772208559540')",
        "resourceData": {},
        "subscriptionId": "sub-chat-global-1",
        "clientState": "chat_global",
    }

    ok = await handler.handle_webhook_notification(notification)
    assert ok is True

    chat_message_events = [
        json_lib.loads(payload)
        for channel, payload in handler.redis_client.published
        if channel == "annika:teams:chat_messages"
    ]
    assert len(chat_message_events) == 1
    event = chat_message_events[0]
    assert event["chat_id"] == "19:test-chat-id@thread.v2"
    assert event["message_id"] == "1772208559540"
    assert event["change_type"] == "created"
    expected_conversation_id = (
        "CVteams_"
        + hashlib.sha256(b"19:test-chat-id@thread.v2").hexdigest()[:16]
    )
    assert event["conversation_id"] == expected_conversation_id


@pytest.mark.asyncio
async def test_teams_parenthesized_channel_message_resource_routes_correctly():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()
    handler._redis_client_loop = asyncio.get_running_loop()

    notification = {
        "changeType": "created",
        "resource": "teams('team-123')/channels('channel-456')/messages('msg-789')",
        "resourceData": {},
        "subscriptionId": "sub-channel-1",
        "clientState": "annika_teams_channels_v5",
    }

    ok = await handler.handle_webhook_notification(notification)
    assert ok is True

    channel_events = [
        json_lib.loads(payload)
        for channel, payload in handler.redis_client.published
        if channel == "annika:teams:channel_messages"
    ]
    assert len(channel_events) == 1
    event = channel_events[0]
    assert event["team_id"] == "team-123"
    assert event["channel_id"] == "channel-456"
    assert event["message_id"] == "msg-789"
