import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chat_subscription_manager as chat_module  # noqa: E402  # type: ignore[import-not-found]


class _DeleteResponse:
    status_code = 204


class _DeleteClient:
    def __init__(self, deleted_urls):
        self._deleted_urls = deleted_urls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def delete(self, url, headers=None, timeout=10):
        self._deleted_urls.append(url)
        return _DeleteResponse()


@pytest.mark.asyncio
async def test_dedupe_global_chat_subscriptions_keeps_chat_global(monkeypatch):
    manager = chat_module.ChatSubscriptionManager()

    async def _fake_list(headers):
        return [
            {
                "id": "sub-annika-user",
                "resource": "/me/chats/getAllMessages",
                "clientState": "annika_user_chat_messages",
                "expirationDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "sub-chat-global",
                "resource": "/me/chats/getAllMessages",
                "clientState": "chat_global",
                "expirationDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "sub-chat-stale",
                "resource": "/me/chats/getAllMessages",
                "clientState": "chat_global",
                "expirationDateTime": "2098-01-01T00:00:00Z",
            },
        ]

    monkeypatch.setattr(manager, "_list_subscriptions", _fake_list)
    deleted_urls = []
    monkeypatch.setattr(
        chat_module.httpx,
        "AsyncClient",
        lambda: _DeleteClient(deleted_urls),
    )

    kept = await manager._dedupe_global_chat_subscriptions({"Authorization": "Bearer x"})

    assert kept is not None
    assert kept["id"] == "sub-chat-global"
    assert len(deleted_urls) == 2
    assert any(
        url.endswith("/subscriptions/sub-annika-user") for url in deleted_urls
    )
    assert any(
        url.endswith("/subscriptions/sub-chat-stale") for url in deleted_urls
    )
