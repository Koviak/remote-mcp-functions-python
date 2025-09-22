import json
import requests
import azure.functions as func

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    get_access_token,
    _get_agent_user_id,
    _get_token_and_base_for_me,
    build_json_headers,
)


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
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        chat_id = req_body.get("chatId")
        message = req_body.get("message")
        reply_to = req_body.get("replyToId")
        if not all([chat_id, message]):
            return func.HttpResponse("Missing required fields: chatId, message", status_code=400)

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
        data = {"body": {"content": message}}
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


