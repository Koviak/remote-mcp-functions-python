import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from webhook_handler import (  # noqa: E402  # type: ignore[import-not-found]
    CONTACTS_CHANNEL,
    CONTACTS_HISTORY_KEY,
    GraphWebhookHandler,
)


class _FakeAsyncRedis:
    def __init__(self):
        self.published = []
        self.lists = {}

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


@pytest.mark.asyncio
async def test_contacts_notification_publishes_to_contacts_channel():
    handler = GraphWebhookHandler()
    handler.redis_client = _FakeAsyncRedis()

    notification = {
        "changeType": "created",
        "resource": "/me/contacts/CONTACT-ID-1",
        "resourceData": {"id": "CONTACT-ID-1"},
        "subscriptionId": "sub-contact-1",
        "clientState": "annika_contacts",
    }
    ok = await handler.handle_webhook_notification(notification)

    assert ok is True
    assert handler.redis_client.published
    channel, payload_raw = handler.redis_client.published[0]
    assert channel == CONTACTS_CHANNEL
    payload = json_lib.loads(payload_raw)
    assert payload["type"] == "contact"
    assert payload["contact_id"] == "CONTACT-ID-1"
    assert payload["change_type"] == "created"
    assert CONTACTS_HISTORY_KEY in handler.redis_client.lists
