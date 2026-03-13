import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import planner_sync_service_v5 as planner_sync_module  # noqa: E402  # type: ignore[import-not-found]


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return _FakeResponse(self._payload)


@pytest.mark.asyncio
async def test_find_existing_webhook_prefers_strict_match_with_timezone_aware_expiry(
    monkeypatch,
):
    payload = {
        "value": [
            {
                "id": "sub-wrong-url",
                "resource": "/chats",
                "notificationUrl": "https://old-ngrok.example/api/graph_webhook",
                "clientState": "annika_teams_chats_v5",
                "expirationDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "sub-correct-url",
                "resource": "/chats",
                "notificationUrl": "https://agency-swarm.ngrok.app/api/graph_webhook",
                "clientState": "annika_teams_chats_v5",
                "expirationDateTime": "2099-01-01T00:00:00Z",
            },
        ]
    }

    monkeypatch.setattr(
        planner_sync_module.httpx,
        "AsyncClient",
        lambda timeout=30.0: _FakeAsyncClient(payload),
    )

    sync = planner_sync_module.WebhookDrivenPlannerSync()
    config = {
        "resource": "/chats",
        "notificationUrl": "https://agency-swarm.ngrok.app/api/graph_webhook",
        "clientState": "annika_teams_chats_v5",
    }

    found = await sync._find_existing_webhook("fake-token", config)

    assert found is not None
    assert found["id"] == "sub-correct-url"
