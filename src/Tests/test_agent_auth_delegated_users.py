# ruff: noqa: E402

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from azure.core.credentials import AccessToken

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_auth_manager import AgentAuthManager
from token_refresh_service import TokenRefreshService


def test_get_agent_user_token_uses_joshua_credentials_and_user_storage(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("AGENT_USER_NAME", "annika@example.com")
    monkeypatch.setenv("AGENT_PASSWORD", "annika-pass")
    monkeypatch.setenv("TODO_JOSHUA_USER_NAME", "joshua@example.com")
    monkeypatch.setenv("TODO_JOSHUA_PASSWORD", "joshua-pass")

    redis_manager = MagicMock()
    manager = AgentAuthManager(redis_token_manager=redis_manager)

    monkeypatch.setattr(manager, "_get_cached_token", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_get_stored_token", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_cache_token", lambda *_args, **_kwargs: None)

    captured: dict = {}

    def fake_ropc(
        scope: str,
        *,
        username: str,
        password: str,
        delegated_user: str,
    ) -> AccessToken:
        captured["scope"] = scope
        captured["username"] = username
        captured["password"] = password
        captured["delegated_user"] = delegated_user
        return AccessToken(
            token="JOSHUA_TOKEN",
            expires_on=int(datetime.now().timestamp()) + 3600,
        )

    monkeypatch.setattr(manager, "_acquire_token_with_ropc", fake_ropc)

    stored: dict = {}

    def fake_store(scope: str, token: AccessToken, user_id=None):
        stored["scope"] = scope
        stored["token"] = token.token
        stored["user_id"] = user_id

    monkeypatch.setattr(manager, "_store_token", fake_store)

    token = manager.get_agent_user_token("Tasks.ReadWrite", delegated_user="joshua")

    assert token == "JOSHUA_TOKEN"
    assert captured["username"] == "joshua@example.com"
    assert captured["password"] == "joshua-pass"
    assert captured["delegated_user"] == "joshua"
    assert stored["user_id"] == "joshua"


def test_refresh_service_uses_user_scoped_delegate(monkeypatch) -> None:
    redis_manager = MagicMock()
    redis_manager.get_all_active_tokens.return_value = [
        {
            "expires_on": int(datetime.now().timestamp()) + 100,
            "scope": "Tasks.ReadWrite",
            "user_id": "joshua",
        }
    ]

    auth_manager = MagicMock()
    auth_manager.get_agent_user_token.return_value = "REFRESHED_TOKEN"

    service = TokenRefreshService(
        redis_manager=redis_manager,
        auth_manager=auth_manager,
        refresh_buffer=900,
    )
    service._refresh_tokens()

    auth_manager.get_agent_user_token.assert_called_once_with(
        "Tasks.ReadWrite",
        delegated_user="joshua",
    )
    redis_manager.update_refresh_count.assert_called_once_with(
        "Tasks.ReadWrite",
        "joshua",
    )
