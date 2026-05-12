import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contact_sync_service import (  # noqa: E402  # type: ignore[import-not-found]
    ContactSyncService,
    CONTACTS_INGEST_CHANNEL,
)


class _FakeRedis:
    def __init__(self):
        self.published = []
        self.json_docs = {}

    async def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    async def execute_command(self, command, key, path=None, value=None):
        if command == "JSON.SET":
            data = json_lib.loads(value) if isinstance(value, str) else value
            self.json_docs[key] = data
            return "OK"
        if command == "JSON.GET":
            if key not in self.json_docs:
                return None
            return json_lib.dumps([self.json_docs[key]])
        raise RuntimeError(f"Unsupported command: {command}")

    async def get(self, _key):
        return None

    async def set(self, _key, _value):
        return True

    async def expire(self, _key, _seconds):
        return True


@pytest.mark.asyncio
async def test_apply_webhook_payload_publishes_ingest_event(monkeypatch):
    service = ContactSyncService()
    service.redis_client = _FakeRedis()

    async def _fake_fetch(_contact_id):
        return {
            "id": "ms-777",
            "displayName": "Webhook Contact",
            "givenName": "Webhook",
            "surname": "Contact",
            "businessPhones": ["+15105550777"],
            "emailAddresses": [{"address": "webhook@example.com"}],
            "lastModifiedDateTime": "2026-02-22T13:00:00Z",
        }

    monkeypatch.setattr(service, "_fetch_graph_contact", _fake_fetch)

    await service._apply_webhook_payload(
        {
            "change_type": "created",
            "contact_id": "ms-777",
            "subscription_id": "sub-1",
            "timestamp": "2026-02-22T13:00:00Z",
        }
    )

    assert service.redis_client.published, "expected publish calls"
    ingest = [
        item for item in service.redis_client.published if item[0] == CONTACTS_INGEST_CHANNEL
    ]
    assert len(ingest) == 1
    event = json_lib.loads(ingest[0][1])
    assert event["provider"] == "microsoft"
    assert event["payload"]["microsoft_contact_id"] == "ms-777"
    assert event["payload"]["display_name"] == "Webhook Contact"
