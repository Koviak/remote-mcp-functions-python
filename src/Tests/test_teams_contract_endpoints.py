# mypy: disable-error-code=import-not-found
# pylint: disable=import-error

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
