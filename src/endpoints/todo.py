import os
from typing import Any

import azure.functions as func
import requests

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    _get_token_and_base_for_me,
    build_json_headers,
)

TODO_DELEGATED_SCOPE = "Tasks.ReadWrite"
DEFAULT_TODO_LIST_NAME = "defaultList"
DEFAULT_DELEGATED_USER = "joshua"
ALLOWED_DELEGATED_USERS = {"annika", "joshua"}
TODO_QUERY_PARAM_ALIASES = {
    "$top": "top",
    "$skip": "skip",
    "$select": "select",
    "$filter": "filter",
    "$orderby": "orderby",
}


def _safe_get_json(req: func.HttpRequest) -> dict[str, Any]:
    """Return a JSON object body or an empty dict when no body is supplied."""
    try:
        raw = req.get_json()
    except ValueError:
        return {}
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Request body must be a JSON object")
    return dict(raw)


def _resolve_delegated_user(req: func.HttpRequest, req_body: dict[str, Any]) -> str:
    """Resolve the requested delegated user alias for Microsoft To Do."""
    raw_value = req_body.get("delegatedUser")
    if raw_value is None:
        raw_value = req.params.get("delegatedUser")
    if raw_value is None:
        raw_value = os.getenv("TODO_DEFAULT_DELEGATED_USER", DEFAULT_DELEGATED_USER)

    normalized = str(raw_value).strip().lower()
    if not normalized:
        normalized = DEFAULT_DELEGATED_USER
    if normalized not in ALLOWED_DELEGATED_USERS:
        raise ValueError(
            "delegatedUser must be one of: annika, joshua"
        )
    return normalized


def _get_todo_context(
    delegated_user: str | None = None,
) -> tuple[str | None, str | None]:
    """Return delegated To Do auth context."""
    return _get_token_and_base_for_me(
        TODO_DELEGATED_SCOPE,
        delegated_user=delegated_user,
    )


def _build_query_params(req: func.HttpRequest) -> dict[str, str]:
    """Pass through supported Graph query options."""
    params: dict[str, str] = {}
    for graph_key, alias in TODO_QUERY_PARAM_ALIASES.items():
        value = req.params.get(graph_key) or req.params.get(alias)
        if value:
            params[graph_key] = value
    return params


def _extract_list_id(req: func.HttpRequest, req_body: dict[str, Any]) -> str | None:
    """Resolve a To Do list id from route params or request body."""
    route_list_id = req.route_params.get("todo_list_id")
    if isinstance(route_list_id, str) and route_list_id.strip():
        return route_list_id.strip()

    for field in ("listId", "todoListId"):
        value = req_body.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _default_todo_list_id(
    headers: dict[str, str],
    base: str,
) -> tuple[str | None, func.HttpResponse | None]:
    """Fetch the user's default To Do list id."""
    response = requests.get(
        f"{GRAPH_API_ENDPOINT}{base}/todo/lists",
        headers=headers,
        timeout=10,
    )
    if response.status_code != 200:
        return (
            None,
            func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code,
            ),
        )

    lists = response.json().get("value", [])
    if not isinstance(lists, list) or not lists:
        return None, func.HttpResponse("No To Do task lists found", status_code=404)

    default_list = next(
        (
            todo_list
            for todo_list in lists
            if isinstance(todo_list, dict)
            and (
                todo_list.get("wellknownListName") == DEFAULT_TODO_LIST_NAME
                or todo_list.get("isDefault") is True
            )
        ),
        None,
    )
    if isinstance(default_list, dict) and default_list.get("id"):
        return str(default_list["id"]), None

    first_list = next(
        (
            todo_list
            for todo_list in lists
            if isinstance(todo_list, dict) and todo_list.get("id")
        ),
        None,
    )
    if isinstance(first_list, dict):
        return str(first_list["id"]), None

    return None, func.HttpResponse("No To Do task lists found", status_code=404)


def list_todo_lists_http(req: func.HttpRequest) -> func.HttpResponse:
    """List the signed-in user's Microsoft To Do lists."""
    try:
        delegated_user = _resolve_delegated_user(req, {})
        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists",
            params=_build_query_params(req),
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def list_todo_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    """List tasks in a specific Microsoft To Do list."""
    try:
        todo_list_id = req.route_params.get("todo_list_id")
        if not todo_list_id:
            return func.HttpResponse(
                "Missing todo_list_id in URL path",
                status_code=400,
            )

        delegated_user = _resolve_delegated_user(req, {})
        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists/{todo_list_id}/tasks",
            params=_build_query_params(req),
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def create_todo_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a task in a specified or default Microsoft To Do list."""
    try:
        req_body = _safe_get_json(req)
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        title = req_body.get("title")
        if not isinstance(title, str) or not title.strip():
            return func.HttpResponse("Missing required field: title", status_code=400)

        delegated_user = _resolve_delegated_user(req, req_body)
        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = build_json_headers(token)
        todo_list_id = _extract_list_id(req, req_body)
        if not todo_list_id:
            todo_list_id, error_response = _default_todo_list_id(headers, base)
            if error_response is not None:
                return error_response

        payload = dict(req_body)
        payload.pop("listId", None)
        payload.pop("todoListId", None)
        payload.pop("delegatedUser", None)

        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists/{todo_list_id}/tasks",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(
                response.text,
                status_code=201,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def get_todo_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a Microsoft To Do task from a specific list."""
    try:
        todo_list_id = req.route_params.get("todo_list_id")
        todo_task_id = req.route_params.get("todo_task_id")
        if not todo_list_id or not todo_task_id:
            return func.HttpResponse(
                "Missing todo_list_id or todo_task_id in URL path",
                status_code=400,
            )

        delegated_user = _resolve_delegated_user(req, {})
        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists/{todo_list_id}/tasks/{todo_task_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def update_todo_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update a Microsoft To Do task."""
    try:
        todo_list_id = req.route_params.get("todo_list_id")
        todo_task_id = req.route_params.get("todo_task_id")
        if not todo_list_id or not todo_task_id:
            return func.HttpResponse(
                "Missing todo_list_id or todo_task_id in URL path",
                status_code=400,
            )

        req_body = _safe_get_json(req)
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        payload = dict(req_body)
        payload.pop("listId", None)
        payload.pop("todoListId", None)
        delegated_user = _resolve_delegated_user(req, req_body)
        payload.pop("delegatedUser", None)
        if not payload:
            return func.HttpResponse("No update fields provided", status_code=400)

        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists/{todo_list_id}/tasks/{todo_task_id}",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def delete_todo_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a Microsoft To Do task."""
    try:
        todo_list_id = req.route_params.get("todo_list_id")
        todo_task_id = req.route_params.get("todo_task_id")
        if not todo_list_id or not todo_task_id:
            return func.HttpResponse(
                "Missing todo_list_id or todo_task_id in URL path",
                status_code=400,
            )

        delegated_user = _resolve_delegated_user(req, {})
        token, base = _get_todo_context(delegated_user)
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for Microsoft To Do.",
                status_code=401,
            )

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}{base}/todo/lists/{todo_list_id}/tasks/{todo_task_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 204:
            return func.HttpResponse("Task deleted successfully", status_code=204)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except ValueError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)
