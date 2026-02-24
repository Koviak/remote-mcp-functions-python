import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contact_sync_service import (  # noqa: E402  # type: ignore[import-not-found]
    CONTACTS_DELTA_STATE_KEY,
    ContactSyncService,
)


class _FakeRedis:
    def __init__(self):
        self.json_docs = {}

    async def execute_command(self, command, key, path=None, value=None):
        if command == "JSON.SET":
            self.json_docs[key] = json_lib.loads(value)
            return "OK"
        if command == "JSON.GET":
            payload = self.json_docs.get(key)
            if payload is None:
                return None
            return json_lib.dumps([payload])
        raise RuntimeError(f"Unsupported command: {command}")

    async def get(self, _key):
        return None

    async def set(self, _key, _value):
        return True

    async def expire(self, _key, _seconds):
        return True


@pytest.mark.asyncio
async def test_delta_cursor_round_trip():
    service = ContactSyncService()
    service.redis_client = _FakeRedis()

    delta_link = "https://graph.microsoft.com/v1.0/me/contacts/delta?$deltatoken=abc"
    await service.set_delta_cursor(delta_link)
    restored = await service.get_delta_cursor()

    assert restored == delta_link
    assert CONTACTS_DELTA_STATE_KEY in service.redis_client.json_docs
