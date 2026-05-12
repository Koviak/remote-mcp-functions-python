import json
from typing import Any

import azure.functions as func
import requests

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    _get_agent_user_id,
    _get_token_and_base_for_me,
    build_json_headers,
    get_access_token,
)


def _safe_get_json(req: func.HttpRequest) -> dict[str, Any]:
    try:
        raw = req.get_json()
    except ValueError:
        return {}
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Request body must be a JSON object")
    return dict(raw)


def _normalize_teams_content_type(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() == "html":
        return "html"
    return "text"


def _normalize_chat_message_importance(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("importance must be one of: normal, high, urgent")
    normalized = value.strip().lower()
    if normalized not in {"normal", "high", "urgent"}:
        raise ValueError("importance must be one of: normal, high, urgent")
    return normalized


def _normalize_chat_collection(
    raw_value: object,
    field_name: str,
) -> list[dict[str, Any]] | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of objects")

    normalized: list[dict[str, Any]] = []
    for item in raw_value:
        if not isinstance(item, dict):
            raise ValueError(f"{field_name} must be a list of objects")
        normalized.append(dict(item))
    return normalized


def _build_chat_message_payload(req_body: dict[str, Any]) -> dict[str, Any]:
    message = req_body.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Missing required field: message")

    payload: dict[str, Any] = {
        "body": {
            "content": message,
            "contentType": _normalize_teams_content_type(req_body.get("contentType")),
        }
    }

    importance = _normalize_chat_message_importance(req_body.get("importance"))
    if importance is not None:
        payload["importance"] = importance

    mentions = _normalize_chat_collection(req_body.get("mentions"), "mentions")
    if mentions:
        payload["mentions"] = mentions

    attachments = _normalize_chat_collection(req_body.get("attachments"), "attachments")
    if attachments:
        payload["attachments"] = attachments

    return payload


def list_teams_http(req: func.HttpRequest) -> func.HttpResponse:
    """List teams. Uses application token (Team.ReadBasic.All)."""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/teams", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_channels_http(req: func.HttpRequest) -> func.HttpResponse:
    """List channels in a team. Uses application token."""
    try:
        team_id = req.route_params.get('team_id')
        if not team_id:
            return func.HttpResponse("Missing team_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def post_channel_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Post message to Teams channel. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        team_id = req_body.get('teamId')
        channel_id = req_body.get('channelId')
        message = req_body.get('message')
        if not all([team_id, channel_id, message]):
            return func.HttpResponse("Missing required fields: teamId, channelId, message", status_code=400)

        delegated, _ = _get_token_and_base_for_me("ChannelMessage.Send")
        token = delegated
        if not token:
            return func.HttpResponse(
                json.dumps({
                    "error": "delegated_required",
                    "message": "Posting channel messages requires delegated token",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        data = {"body": {"content": message}}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels/{channel_id}/messages",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(f"Message posted successfully to channel {channel_id}", status_code=201)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_chats_http(req: func.HttpRequest) -> func.HttpResponse:
    """List chats for the agent user. Delegated preferred; app-only fallback via /users/{id}."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Chat.Read Chat.ReadWrite Chat.ReadBasic")
        if delegated and base:
            token, path = delegated, f"{base}/chats"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/chats"

        if not token or not path:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}{path}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:  # pragma: no cover - network errors
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def post_chat_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Post a message to a Teams chat. Delegated token required."""
    try:
        req_body = _safe_get_json(req)
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        chat_id = req_body.get("chatId")
        reply_to = req_body.get("replyToId")
        if not isinstance(chat_id, str) or not chat_id.strip():
            return func.HttpResponse("Missing required field: chatId", status_code=400)
        try:
            data = _build_chat_message_payload(req_body)
        except ValueError as exc:
            return func.HttpResponse(str(exc), status_code=400)

        delegated, _ = _get_token_and_base_for_me("ChatMessage.Send")
        token = delegated
        if not token:
            return func.HttpResponse(
                json.dumps({
                    "error": "delegated_required",
                    "message": "Posting chat messages requires delegated token",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        if reply_to:
            url = f"{GRAPH_API_ENDPOINT}/chats/{chat_id}/messages/{reply_to}/replies"
        else:
            url = f"{GRAPH_API_ENDPOINT}/chats/{chat_id}/messages"
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code in (200, 201):
            return func.HttpResponse(f"Message posted successfully to chat {chat_id}", status_code=201)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:  # pragma: no cover - network errors
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


