import json
import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import endpoints.contacts as ep_contacts  # noqa: E402  # type: ignore[import-not-found]


class _FakeResponse:
    def __init__(self, status_code=200, text='{"value": []}'):
        self.status_code = status_code
        self.text = text


def _fake_request(params=None, route_params=None, body=None):
    def _get_json():
        if body is None:
            raise ValueError("No body")
        return body

    return SimpleNamespace(
        params=params or {},
        route_params=route_params or {},
        get_json=_get_json,
    )


def test_list_contacts_delegated_success(monkeypatch):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200, text='{"value":[{"id":"1"}]}')

    monkeypatch.setattr(
        ep_contacts,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )
    monkeypatch.setattr(ep_contacts.requests, "get", _fake_get)

    response = ep_contacts.list_contacts_http(_fake_request())
    assert response.status_code == 200
    assert captured["url"] == "https://graph.microsoft.com/v1.0/me/contacts"


def test_get_contact_delegates_delta_route_id(monkeypatch):
    marker = {"called": False}

    def _fake_delta(_req):
        marker["called"] = True
        return ep_contacts.func.HttpResponse(
            body='{"ok": true}',
            status_code=200,
            mimetype="application/json",
        )

    monkeypatch.setattr(ep_contacts, "list_contacts_delta_http", _fake_delta)
    response = ep_contacts.get_contact_http(
        _fake_request(route_params={"contact_id": "delta"})
    )

    assert response.status_code == 200
    assert marker["called"] is True


def test_list_contacts_delta_rejects_non_graph_url(monkeypatch):
    monkeypatch.setattr(
        ep_contacts,
        "_get_token_and_base_for_me",
        lambda _scope: ("delegated-token", "/me"),
    )

    response = ep_contacts.list_contacts_delta_http(
        _fake_request(params={"deltaToken": "https://example.com/not-graph"})
    )
    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["error"] == "invalid_delta_token"
