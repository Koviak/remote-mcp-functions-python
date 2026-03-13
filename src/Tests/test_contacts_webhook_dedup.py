import json as json_lib
import os
import sys
import asyncio

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webhook_handler import (  # noqa: E402  # type: ignore[import-not-found]
    CONTACTS_CHANNEL,
    GraphWebhookHandler,
)


class _FakeAsyncRedis:
    def __init__(self):
        self.published = []
        self.lists = {}
        self.strings = {}

    async def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    async def lpush(self, key, payload):
        items = self.lists.setdefault(key, [])
        items.insert(0, payload)
        return len(items)

    async def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        self.lists[key] = items[start : end + 1]
        return True

    async def get(self, key):
        return self.strings.get(key)

    async def set(self, key, value):
        self.strings[key] = value
        return True

    async def setex(self, key, ttl, value):
        self.strings[key] = value
        self.strings[f"__ttl__{key}"] = ttl
        return True


@pytest.mark.asyncio
async def test_duplicate_contact_notification_is_ignored():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()
    handler._redis_client_loop = asyncio.get_running_loop()

    notification = {
        "changeType": "updated",
        "resource": "/me/contacts/CONTACT-DUP-1",
        "resourceData": {"id": "CONTACT-DUP-1"},
        "subscriptionId": "sub-contact-dedup",
        "clientState": "annika_contacts",
    }

    first_ok = await handler.handle_webhook_notification(notification)
    second_ok = await handler.handle_webhook_notification(notification)

    assert first_ok is True
    assert second_ok is True

    contact_publishes = [
        item
        for item in handler.redis_client.published
        if item[0] == CONTACTS_CHANNEL
    ]
    assert len(contact_publishes) == 1

    payload = json_lib.loads(contact_publishes[0][1])
    assert payload["contact_id"] == "CONTACT-DUP-1"
