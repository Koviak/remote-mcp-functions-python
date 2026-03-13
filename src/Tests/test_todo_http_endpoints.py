# ruff: noqa: E402

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import azure.functions as func

from endpoints import todo
from http_endpoints import register_http_endpoints


class _RouteCapturingApp:
    def __init__(self) -> None:
        self.routes: list[tuple[str, tuple[str, ...]]] = []

    def route(self, route: str, methods: list[str], **_kwargs):
        def decorator(handler):
            self.routes.append((route, tuple(methods)))
            return handler

        return decorator


class _FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str | None = None):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or "{}"

    def json(self):
        return self._body


def _make_request(
    *,
    method: str,
    url: str,
    params: dict | None = None,
    route_params: dict | None = None,
    body: bytes = b"",
) -> func.HttpRequest:
    return func.HttpRequest(
        method=method,
        url=url,
        headers={},
        params=params or {},
        route_params=route_params or {},
        body=body,
    )


def test_register_http_endpoints_includes_todo_routes() -> None:
    app = _RouteCapturingApp()
    register_http_endpoints(app)  # type: ignore[arg-type]
    routes = set(app.routes)

    assert ("me/todo/lists", ("GET",)) in routes
    assert ("me/todo/lists/{todo_list_id}/tasks", ("GET",)) in routes
    assert ("me/todo/tasks", ("POST",)) in routes
    assert ("me/todo/lists/{todo_list_id}/tasks", ("POST",)) in routes
    assert ("me/todo/lists/{todo_list_id}/tasks/{todo_task_id}", ("GET",)) in routes
    assert ("me/todo/lists/{todo_list_id}/tasks/{todo_task_id}", ("PATCH",)) in routes
    assert ("me/todo/lists/{todo_list_id}/tasks/{todo_task_id}", ("DELETE",)) in routes


def test_list_todo_lists_accepts_plain_query_params(monkeypatch) -> None:
    captured: dict = {}

    def fake_context(delegated_user: str | None = None):
        captured["delegated_user"] = delegated_user
        return ("TOKEN", "/me")

    def fake_get(url: str, params: dict, headers: dict, timeout: int):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(200, {"value": []}, text='{"value":[]}')

    monkeypatch.setattr(todo, "_get_todo_context", fake_context)
    monkeypatch.setattr(todo.requests, "get", fake_get)

    response = todo.list_todo_lists_http(
        _make_request(
            method="GET",
            url="http://localhost:7071/api/me/todo/lists",
            params={"top": "5", "select": "id,displayName"},
        )
    )

    assert response.status_code == 200
    assert captured["delegated_user"] == "joshua"
    assert captured["url"].endswith("/me/todo/lists")
    assert captured["params"] == {"$top": "5", "$select": "id,displayName"}


def test_create_todo_task_uses_default_list_name(monkeypatch) -> None:
    captured: dict = {}

    def fake_context(delegated_user: str | None = None):
        captured["delegated_user"] = delegated_user
        return ("TOKEN", "/me")

    def fake_get(url: str, headers: dict, timeout: int):
        captured["lists_url"] = url
        return _FakeResponse(
            200,
            {
                "value": [
                    {"id": "LIST-2", "displayName": "Tasks"},
                    {"id": "LIST-1", "wellknownListName": "defaultList"},
                ]
            },
            text='{"value":[{"id":"LIST-2"},{"id":"LIST-1","wellknownListName":"defaultList"}]}',
        )

    def fake_post(url: str, headers: dict, json: dict, timeout: int):
        captured["post_url"] = url
        captured["post_json"] = json
        return _FakeResponse(201, {"id": "TASK-1"}, text='{"id":"TASK-1"}')

    monkeypatch.setattr(todo, "_get_todo_context", fake_context)
    monkeypatch.setattr(todo.requests, "get", fake_get)
    monkeypatch.setattr(todo.requests, "post", fake_post)

    response = todo.create_todo_task_http(
        _make_request(
            method="POST",
            url="http://localhost:7071/api/me/todo/tasks",
            body=b'{"title":"Buy milk","body":{"content":"2 gallons","contentType":"text"}}',
        )
    )

    assert response.status_code == 201
    assert captured["delegated_user"] == "joshua"
    assert captured["post_url"].endswith("/me/todo/lists/LIST-1/tasks")
    assert captured["post_json"] == {
        "title": "Buy milk",
        "body": {"content": "2 gallons", "contentType": "text"},
    }


def test_create_todo_task_accepts_explicit_annika_delegate(monkeypatch) -> None:
    captured: dict = {}

    def fake_context(delegated_user: str | None = None):
        captured["delegated_user"] = delegated_user
        return ("TOKEN", "/me")

    def fake_get(url: str, headers: dict, timeout: int):
        return _FakeResponse(
            200,
            {"value": [{"id": "LIST-1", "wellknownListName": "defaultList"}]},
            text='{"value":[{"id":"LIST-1","wellknownListName":"defaultList"}]}',
        )

    def fake_post(url: str, headers: dict, json: dict, timeout: int):
        captured["post_json"] = json
        return _FakeResponse(201, {"id": "TASK-2"}, text='{"id":"TASK-2"}')

    monkeypatch.setattr(todo, "_get_todo_context", fake_context)
    monkeypatch.setattr(todo.requests, "get", fake_get)
    monkeypatch.setattr(todo.requests, "post", fake_post)

    response = todo.create_todo_task_http(
        _make_request(
            method="POST",
            url="http://localhost:7071/api/me/todo/tasks",
            body=b'{"title":"Use Annika list","delegatedUser":"annika"}',
        )
    )

    assert response.status_code == 201
    assert captured["delegated_user"] == "annika"
    assert captured["post_json"] == {"title": "Use Annika list"}


def test_list_todo_lists_rejects_invalid_delegate(monkeypatch) -> None:
    response = todo.list_todo_lists_http(
        _make_request(
            method="GET",
            url="http://localhost:7071/api/me/todo/lists",
            params={"delegatedUser": "bruce"},
        )
    )

    assert response.status_code == 400
    assert "delegatedUser must be one of" in response.get_body().decode("utf-8")
