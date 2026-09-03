# mypy: disable-error-code=import-not-found
# pylint: disable=import-error

import json
import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import endpoints.teams as ep_teams  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code=200, text='{"ok":true}'):
        self.status_code = status_code
        self.text = text


def _fake_request(body=None, route_params=None, params=None):
    return SimpleNamespace(
        params=params or {},
        route_params=route_params or {},
        get_json=lambda: body or {},
    )


def test_post_chat_message_http_preserves_rich_message_payload(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=201, text='{"id":"msg-1"}')

    monkeypatch.setattr(
        ep_teams,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_teams.requests, "post", _fake_post)

    response = ep_teams.post_chat_message_http(
        _fake_request(
            body={
                "chatId": "19:test-chat-id@thread.v2",
                "message": (
                    "Deliverable ready<br/>"
                    "<attachment id=\"deliverable-1\"></attachment>"
                ),
                "contentType": "html",
                "importance": "high",
                "attachments": [
                    {
                        "id": "deliverable-1",
                        "name": "budget.xlsx",
                        "contentType": "reference",
                        "contentUrl": "https://example.com/budget.xlsx",
                    }
                ],
                "mentions": [
                    {
                        "id": 0,
                        "mentionText": "Joshua",
                        "mentioned": {
                            "user": {
                                "id": "user-123",
                                "displayName": "Joshua",
                            }
                        },
                    }
                ],
            }
        )
    )

    assert response.status_code == 201
    assert captured["url"] == (
        "https://graph.microsoft.com/v1.0/chats/19:test-chat-id@thread.v2/messages"
    )
    assert captured["json"]["body"]["content"] == (
        "Deliverable ready<br/><attachment id=\"deliverable-1\"></attachment>"
    )
    assert captured["json"]["body"]["contentType"] == "html"
    assert captured["json"]["importance"] == "high"
    assert captured["json"]["attachments"][0]["contentType"] == "reference"
    assert captured["json"]["mentions"][0]["mentionText"] == "Joshua"


def test_post_chat_message_http_uses_graph_reply_with_quote_contract(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=201, text='{"id":"reply-msg-1"}')

    monkeypatch.setattr(
        ep_teams,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_teams.requests, "post", _fake_post)

    response = ep_teams.post_chat_message_http(
        _fake_request(
            body={
                "chatId": "19:test-chat-id@thread.v2",
                "replyToId": "source-message-123",
                "message": "RSI repair finished and replay passed.",
                "contentType": "text",
                "importance": "normal",
            }
        )
    )

    assert response.status_code == 201
    assert captured["url"] == (
        "https://graph.microsoft.com/v1.0/chats/"
        "19:test-chat-id@thread.v2/messages/replyWithQuote"
    )
    assert captured["json"] == {
        "messageIds": ["source-message-123"],
        "replyMessage": {
            "body": {
                "content": "RSI repair finished and replay passed.",
                "contentType": "text",
            },
            "importance": "normal",
        },
    }
    assert response.get_body().decode("utf-8") == '{"id":"reply-msg-1"}'


def _patch_delegated(monkeypatch):
    monkeypatch.setattr(
        ep_teams,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )


def test_get_chat_http_expands_members_on_the_graph_chat_route(monkeypatch):
    captured = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, text='{"id":"19:chat@unq.gbl.spaces"}')

    _patch_delegated(monkeypatch)
    monkeypatch.setattr(ep_teams.requests, "get", _fake_get)

    response = ep_teams.get_chat_http(
        _fake_request(route_params={"chat_id": "19:chat@unq.gbl.spaces"})
    )

    assert response.status_code == 200
    assert captured["url"] == (
        "https://graph.microsoft.com/v1.0/chats/19:chat@unq.gbl.spaces"
    )
    assert captured["params"] == {"$expand": "members"}
    assert captured["headers"]["Authorization"] == "Bearer delegated-token"
    assert response.get_body().decode("utf-8") == '{"id":"19:chat@unq.gbl.spaces"}'


def test_get_chat_http_honors_caller_supplied_expand_and_select(monkeypatch):
    captured = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(status_code=200, text="{}")

    _patch_delegated(monkeypatch)
    monkeypatch.setattr(ep_teams.requests, "get", _fake_get)

    response = ep_teams.get_chat_http(
        _fake_request(
            route_params={"chat_id": "19:chat@unq.gbl.spaces"},
            params={"$expand": "installedApps", "$select": "id,topic"},
        )
    )

    assert response.status_code == 200
    assert captured["params"] == {
        "$expand": "installedApps",
        "$select": "id,topic",
    }


def test_get_chat_http_rejects_missing_chat_id():
    response = ep_teams.get_chat_http(_fake_request(route_params={}))

    assert response.status_code == 400
    assert response.get_body().decode("utf-8") == "Missing chat_id in URL path"


def test_get_chat_http_forwards_graph_error_status(monkeypatch):
    _patch_delegated(monkeypatch)
    monkeypatch.setattr(
        ep_teams.requests,
        "get",
        lambda *a, **k: _FakeResponse(status_code=404, text='{"error":"NotFound"}'),
    )

    response = ep_teams.get_chat_http(
        _fake_request(route_params={"chat_id": "19:missing@unq.gbl.spaces"})
    )

    assert response.status_code == 404
    assert response.get_body().decode("utf-8") == (
        'Error: 404 - {"error":"NotFound"}'
    )


def test_get_chat_http_returns_503_when_no_token(monkeypatch):
    monkeypatch.setattr(ep_teams, "_get_token_and_base_for_me", lambda _s: (None, None))
    monkeypatch.setattr(ep_teams, "get_access_token", lambda: None)

    response = ep_teams.get_chat_http(
        _fake_request(route_params={"chat_id": "19:chat@unq.gbl.spaces"})
    )

    assert response.status_code == 503
    assert json.loads(response.get_body().decode("utf-8"))["error"] == (
        "auth_unavailable"
    )


def test_list_chat_members_http_calls_the_graph_members_route(monkeypatch):
    captured = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(status_code=200, text='{"value":[]}')

    _patch_delegated(monkeypatch)
    monkeypatch.setattr(ep_teams.requests, "get", _fake_get)

    response = ep_teams.list_chat_members_http(
        _fake_request(route_params={"chat_id": "19:chat@unq.gbl.spaces"})
    )

    assert response.status_code == 200
    assert captured["url"] == (
        "https://graph.microsoft.com/v1.0/chats/19:chat@unq.gbl.spaces/members"
    )
    assert captured["params"] is None
    assert response.get_body().decode("utf-8") == '{"value":[]}'


def test_list_chat_members_http_forwards_supported_query_params(monkeypatch):
    captured = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(status_code=200, text='{"value":[]}')

    _patch_delegated(monkeypatch)
    monkeypatch.setattr(ep_teams.requests, "get", _fake_get)

    ep_teams.list_chat_members_http(
        _fake_request(
            route_params={"chat_id": "19:chat@unq.gbl.spaces"},
            params={"$top": "20", "$select": "id,displayName", "$orderby": "id"},
        )
    )

    assert captured["params"] == {"$top": "20", "$select": "id,displayName"}


def test_list_chat_members_http_rejects_missing_chat_id():
    response = ep_teams.list_chat_members_http(_fake_request(route_params={}))

    assert response.status_code == 400
    assert response.get_body().decode("utf-8") == "Missing chat_id in URL path"


def test_list_chat_members_http_forwards_graph_error_status(monkeypatch):
    _patch_delegated(monkeypatch)
    monkeypatch.setattr(
        ep_teams.requests,
        "get",
        lambda *a, **k: _FakeResponse(status_code=403, text='{"error":"Forbidden"}'),
    )

    response = ep_teams.list_chat_members_http(
        _fake_request(route_params={"chat_id": "19:chat@unq.gbl.spaces"})
    )

    assert response.status_code == 403
    assert response.get_body().decode("utf-8") == (
        'Error: 403 - {"error":"Forbidden"}'
    )


def test_chat_read_routes_are_registered_in_the_functions_app():
    """ENDPOINT_MAPPING advertises get_chat/list_chat_members - prove the app serves them."""
    import importlib

    class _RouteCapturingApp:
        def __init__(self):
            self.routes = []

        def route(self, route, methods, **_kwargs):
            def decorator(func):
                self.routes.append((route, tuple(methods)))
                return func

            return decorator

    http_endpoints = importlib.import_module("http_endpoints")
    app = _RouteCapturingApp()
    http_endpoints.register_http_endpoints(app)

    assert ("chats/{chat_id}", ("GET",)) in app.routes
    assert ("chats/{chat_id}/members", ("GET",)) in app.routes
    assert ("chats/{chat_id}/messages", ("GET",)) in app.routes
