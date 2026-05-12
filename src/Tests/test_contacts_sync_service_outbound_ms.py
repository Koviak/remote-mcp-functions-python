import json as json_lib
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import contact_sync_service as css  # noqa: E402  # type: ignore[import-not-found]


class _FakeRedis:
    def __init__(self):
        self.json_docs = {}
        self.strings = {}

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

    async def set(self, key, value):
        self.strings[key] = value
        return True

    async def get(self, key):
        return self.strings.get(key)

    async def expire(self, _key, _seconds):
        return True


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return dict(self._payload)


class _FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, _url, headers=None, json=None):
        assert headers is not None
        assert json is not None
        return _FakeResponse(201, {"id": "ms-created-1"})

    async def patch(self, _url, headers=None, json=None):
        return _FakeResponse(200, {})

    async def delete(self, _url, headers=None):
        return _FakeResponse(204, {})


@pytest.mark.asyncio
async def test_execute_microsoft_operation_create_updates_mapping(monkeypatch):
    service = css.ContactSyncService()
    service.redis_client = _FakeRedis()

    async def _fake_token():
        return "token-1", "/me"

    monkeypatch.setattr(service, "_get_graph_token_and_base", _fake_token)
    monkeypatch.setattr(css.httpx, "AsyncClient", lambda timeout: _FakeAsyncClient())

    operation = {
        "provider": "microsoft",
        "operation": "upsert",
        "contact_id": "c-100",
        "payload": {
            "display_name": "Created Contact",
            "phones": [{"value": "+15105551000", "type": "mobile"}],
            "emails": [{"value": "created@example.com", "type": "work"}],
            "source": "canonical",
            "deleted": False,
        },
    }

    ok, error = await service._execute_microsoft_operation(operation)

    assert ok is True
    assert error is None

    id_map = service.redis_client.json_docs.get("annika:contacts:id_map:c-100")
    assert isinstance(id_map, dict)
    assert id_map["microsoft_contact_id"] == "ms-created-1"
    assert (
        service.redis_client.strings["annika:contacts:mapping:microsoft:ms-created-1"]
        == "c-100"
    )
