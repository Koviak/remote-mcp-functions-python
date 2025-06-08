import json
import os
import sys
from collections.abc import Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import additional_tools_delegated as tools

GRAPH = tools.GRAPH_API_ENDPOINT


def _patch_token(monkeypatch):
    monkeypatch.setattr(
        tools,
        "get_delegated_access_token",
        lambda: "dummy",
    )


class DummyApp:
    def __init__(self) -> None:
        self.registered: dict[str, Callable] = {}

    def generic_trigger(self, **kwargs):
        def decorator(func):
            self.registered[kwargs.get("toolName", func.__name__)] = func
            return func
        return decorator


class DummyResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_list_my_chats(monkeypatch):
    _patch_token(monkeypatch)
    app = DummyApp()
    tools.register_delegated_tools(app)
    func = app.registered["list_my_chats"]

    def fake_get(*args, **kwargs):
        return DummyResponse(200, json.dumps({"value": []}))

    monkeypatch.setattr(tools.requests, "get", fake_get)
    result = func(json.dumps({"arguments": {}}))
    assert json.loads(result) == {"value": []}


def test_post_chat_message(monkeypatch):
    _patch_token(monkeypatch)
    app = DummyApp()
    tools.register_delegated_tools(app)
    func = app.registered["post_chat_message_as_agent"]
    chat_id = "chat123"

    def fake_post(url, *args, **kwargs):
        assert url.endswith(f"/chats/{chat_id}/messages")
        return DummyResponse(201)

    monkeypatch.setattr(tools.requests, "post", fake_post)
    ctx = json.dumps({"arguments": {"chatId": chat_id, "message": "hi"}})
    result = func(ctx)
    assert "successfully" in result


def test_post_chat_message_reply(monkeypatch):
    _patch_token(monkeypatch)
    app = DummyApp()
    tools.register_delegated_tools(app)
    func = app.registered["post_chat_message_as_agent"]
    chat_id = "chat123"
    msg = "abc"

    def fake_post(url, *args, **kwargs):
        assert url.endswith(f"/chats/{chat_id}/messages/{msg}/replies")
        return DummyResponse(201)

    monkeypatch.setattr(tools.requests, "post", fake_post)
    ctx = json.dumps({"arguments": {"chatId": chat_id, "message": "hi", "replyToId": msg}})
    result = func(ctx)
    assert "successfully" in result
