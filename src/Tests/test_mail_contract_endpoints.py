# mypy: disable-error-code=import-not-found
# pylint: disable=import-error

import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import endpoints.mail as ep_mail  # noqa: E402


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


def test_send_message_http_accepts_canonical_payload(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=202, text="")

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "post", _fake_post)

    request = _fake_request(
        body={
            "toRecipients": ["alpha@example.com", "beta@example.com"],
            "ccRecipients": ["manager@example.com"],
            "subject": "Weekly update",
            "bodyContent": "Status report attached.",
            "contentType": "HTML",
            "importance": "high",
            "requestDeliveryReceipt": True,
            "requestReadReceipt": False,
            "saveToSentItems": True,
        }
    )

    response = ep_mail.send_message_http(request)

    assert response.status_code == 202
    assert captured["url"] == "https://graph.microsoft.com/v1.0/me/sendMail"
    assert captured["json"]["saveToSentItems"] is True
    message = captured["json"]["message"]
    assert message["subject"] == "Weekly update"
    assert message["body"]["contentType"] == "HTML"
    assert message["body"]["content"] == "Status report attached."
    assert [r["emailAddress"]["address"] for r in message["toRecipients"]] == [
        "alpha@example.com",
        "beta@example.com",
    ]
    assert [r["emailAddress"]["address"] for r in message["ccRecipients"]] == [
        "manager@example.com"
    ]
    assert message["importance"] == "high"
    assert message["isDeliveryReceiptRequested"] is True
    assert message["isReadReceiptRequested"] is False


def test_send_message_http_targets_shared_mailbox(monkeypatch):
    captured = {}
    scope_calls = []

    def _fake_get_token(scope):
        scope_calls.append(scope)
        return "delegated-token", "/me"

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(status_code=202, text="")

    monkeypatch.setattr(ep_mail, "_get_token_and_base_for_me", _fake_get_token)
    monkeypatch.setattr(ep_mail.requests, "post", _fake_post)

    response = ep_mail.send_message_http(
        _fake_request(
            body={
                "userId": "joshua@koviakbuilt.com",
                "toRecipients": ["annika@reddypros.com"],
                "subject": "Shared mailbox send",
                "bodyContent": "Testing shared mailbox routing.",
            }
        )
    )

    assert response.status_code == 202
    assert scope_calls == ["User.Read Mail.Send.Shared"]
    assert (
        captured["url"]
        == "https://graph.microsoft.com/v1.0/users/joshua@koviakbuilt.com/sendMail"
    )
    assert captured["json"]["message"]["from"]["emailAddress"]["address"] == (
        "joshua@koviakbuilt.com"
    )


def test_create_draft_message_http_accepts_canonical_payload(monkeypatch):
    captured = {}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=201, text='{"id":"draft-1"}')

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "post", _fake_post)

    request = _fake_request(
        body={
            "toRecipients": ["recipient@example.com"],
            "bccRecipients": ["audit@example.com"],
            "subject": "Draft subject",
            "bodyContent": "Draft body",
            "contentType": "Text",
        }
    )

    response = ep_mail.create_draft_message_http(request)

    assert response.status_code == 201
    assert captured["url"] == "https://graph.microsoft.com/v1.0/me/messages"
    assert captured["json"]["subject"] == "Draft subject"
    assert captured["json"]["body"]["contentType"] == "Text"
    assert captured["json"]["body"]["content"] == "Draft body"
    to_addresses = [
        recipient["emailAddress"]["address"]
        for recipient in captured["json"]["toRecipients"]
    ]
    bcc_addresses = [
        recipient["emailAddress"]["address"]
        for recipient in captured["json"]["bccRecipients"]
    ]
    assert to_addresses == ["recipient@example.com"]
    assert bcc_addresses == ["audit@example.com"]


def test_list_inbox_http_search_drops_orderby(monkeypatch):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, text='{"value":[]}')

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_http(
        _fake_request(
            params={
                "top": "5",
                "search": "invoice",
            }
        )
    )

    assert response.status_code == 200
    assert captured["url"] == "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
    assert captured["params"]["$top"] == "5"
    assert captured["params"]["$search"] == "invoice"
    assert "$orderby" not in captured["params"]


def test_list_inbox_http_defaults_orderby_without_search(monkeypatch):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, text='{"value":[]}')

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_http(_fake_request(params={"top": "5"}))

    assert response.status_code == 200
    assert captured["params"]["$top"] == "5"
    assert captured["params"]["$orderby"] == "receivedDateTime desc"


def test_list_inbox_http_targets_shared_mailbox(monkeypatch):
    captured = {}
    scope_calls = []

    def _fake_get_token(scope):
        scope_calls.append(scope)
        return "delegated-token", "/me"

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(status_code=200, text='{"value":[]}')

    monkeypatch.setattr(ep_mail, "_get_token_and_base_for_me", _fake_get_token)
    monkeypatch.setattr(ep_mail.requests, "get", _fake_get)

    response = ep_mail.list_inbox_http(
        _fake_request(
            params={
                "userId": "joshua@koviakbuilt.com",
                "top": "3",
            }
        )
    )

    assert response.status_code == 200
    assert scope_calls == ["User.Read Mail.ReadWrite.Shared"]
    assert (
        captured["url"]
        == "https://graph.microsoft.com/v1.0/users/joshua@koviakbuilt.com/mailFolders/inbox/messages"
    )
    assert captured["params"]["$top"] == "3"


def test_mark_as_read_http_patches_message(monkeypatch):
    captured = {}

    def _fake_patch(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            status_code=200,
            text='{"id":"msg-1","isRead":true}',
        )

    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_mail.requests, "patch", _fake_patch)

    response = ep_mail.mark_as_read_http(
        _fake_request(
            body={"isRead": True},
            route_params={"message_id": "msg-1"},
        )
    )

    assert response.status_code == 200
    assert (
        captured["url"] == "https://graph.microsoft.com/v1.0/me/messages/msg-1"
    )
    assert captured["json"] == {"isRead": True}


def test_mark_as_read_http_rejects_non_boolean(monkeypatch):
    monkeypatch.setattr(
        ep_mail,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )

    response = ep_mail.mark_as_read_http(
        _fake_request(
            body={"isRead": "yes"},
            route_params={"message_id": "msg-1"},
        )
    )

    assert response.status_code == 400


def test_mark_as_read_http_targets_shared_mailbox(monkeypatch):
    captured = {}
    scope_calls = []

    def _fake_get_token(scope):
        scope_calls.append(scope)
        return "delegated-token", "/me"

    def _fake_patch(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(
            status_code=200,
            text='{"id":"msg-1","isRead":false}',
        )

    monkeypatch.setattr(ep_mail, "_get_token_and_base_for_me", _fake_get_token)
    monkeypatch.setattr(ep_mail.requests, "patch", _fake_patch)

    response = ep_mail.mark_as_read_http(
        _fake_request(
            body={
                "userId": "joshua@koviakbuilt.com",
                "isRead": False,
            },
            route_params={"message_id": "msg-1"},
        )
    )

    assert response.status_code == 200
    assert scope_calls == ["User.Read Mail.ReadWrite.Shared"]
    assert (
        captured["url"]
        == "https://graph.microsoft.com/v1.0/users/joshua@koviakbuilt.com/messages/msg-1"
    )
    assert captured["json"] == {"isRead": False}
