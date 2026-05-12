import json
import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import endpoints.mail as ep_mail  # noqa: E402  # type: ignore[import-not-found]


class _FakeResponse:
    def __init__(
        self,
        status_code=200,
        text='{"value":[],"@odata.deltaLink":"https://graph.microsoft.com/v1.0/me/messages/delta?$deltatoken=abc"}',
    ):
        self.status_code = status_code
        self.text = text


def _fake_request(params=None, route_params=None):
    return SimpleNamespace(
        params=params or {},
        route_params=route_params or {},
    )


def test_list_inbox_delta_initial_call(monkeypatch):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_delta_http(_fake_request())

    assert response.status_code == 200
    assert (
        captured["url"]
        == "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta"
    )
    assert "$select" in captured["params"]
    assert captured["params"]["$top"] == "50"


def test_list_inbox_delta_follow_up_with_graph_url(monkeypatch):
    captured = {}
    delta_url = (
        "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/"
        "delta?$deltatoken=abc123"
    )

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_delta_http(
        _fake_request(params={"deltaToken": delta_url})
    )

    assert response.status_code == 200
    assert captured["url"] == delta_url
    assert captured["params"] is None


def test_list_inbox_delta_targets_shared_mailbox(monkeypatch):
    captured = {}
    scope_calls = []

    def _fake_get_token(scope):
        scope_calls.append(scope)
        return "delegated-token", "/me"

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse()

    monkeypatch.setattr(ep_mail, "_get_token_and_base_for_me", _fake_get_token)
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_delta_http(
        _fake_request(params={"userId": "joshua@koviakbuilt.com"})
    )

    assert response.status_code == 200
    assert scope_calls == ["User.Read Mail.ReadWrite.Shared"]
    assert (
        captured["url"]
        == "https://graph.microsoft.com/v1.0/users/joshua@koviakbuilt.com/mailFolders/inbox/messages/delta"
    )


def test_list_inbox_delta_rejects_non_graph_delta_url(monkeypatch):
    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )

    response = ep_mail.list_inbox_delta_http(
        _fake_request(params={"deltaToken": "https://example.com/not-graph"})
    )

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["error"] == "invalid_delta_token"


def test_get_message_http_delegates_delta_message_id(monkeypatch):
    marker = {"called": False}

    def _fake_delta_handler(_req):
        marker["called"] = True
        return ep_mail.func.HttpResponse(
            body='{"ok":true}',
            status_code=200,
            mimetype="application/json",
        )

    monkeypatch.setattr(ep_mail, "list_inbox_delta_http", _fake_delta_handler)

    response = ep_mail.get_message_http(
        _fake_request(route_params={"message_id": "delta"})
    )

    assert marker["called"] is True
    assert response.status_code == 200
