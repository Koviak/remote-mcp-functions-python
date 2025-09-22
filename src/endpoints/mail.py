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


def get_mail_folders_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get mail folders for a specific user. Uses application token."""
    try:
        user_id = req.route_params.get('user_id')
        if not user_id:
            return func.HttpResponse("Missing user_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users/{user_id}/mailFolders",
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


def get_mail_folder_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific mail folder for a user. Uses application token."""
    try:
        user_id = req.route_params.get('user_id')
        folder_id = req.route_params.get('folder_id')
        if not user_id or not folder_id:
            return func.HttpResponse("Missing user_id or folder_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users/{user_id}/mailFolders/{folder_id}",
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


def create_mail_folder_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new mail folder for the signed-in user. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        display_name = req_body.get('displayName')
        parent_folder_id = req_body.get('parentFolderId')
        if not display_name:
            return func.HttpResponse("Missing required field: displayName", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"displayName": display_name}
        if parent_folder_id:
            url = f"{GRAPH_API_ENDPOINT}{base}/mailFolders/{parent_folder_id}/childFolders"
        else:
            url = f"{GRAPH_API_ENDPOINT}{base}/mailFolders"
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific message for the signed-in user. Delegated token preferred; app-only fallback supported."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if delegated and base:
            token, path = delegated, f"{base}/messages/{message_id}"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/messages/{message_id}"

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
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def create_draft_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a draft message for the signed-in user. Delegated token required."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        subject = req_body.get('subject')
        body = req_body.get('body')
        to_recipients = req_body.get('toRecipients', [])
        if not subject:
            return func.HttpResponse("Missing required field: subject", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {
            "subject": subject,
            "body": {"contentType": "text", "content": body or ""},
            "toRecipients": [{"emailAddress": {"address": email}} for email in to_recipients],
        }
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def send_draft_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Send a draft message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite Mail.Send")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/send",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Draft message sent successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def delete_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}", headers=headers, timeout=10
        )
        if response.status_code == 204:
            return func.HttpResponse("Message deleted successfully", status_code=204)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_attachments_http(req: func.HttpRequest) -> func.HttpResponse:
    """List attachments on a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/attachments",
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


def add_attachment_http(req: func.HttpRequest) -> func.HttpResponse:
    """Add an attachment to a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        name = req_body.get('name')
        content_bytes = req_body.get('contentBytes')
        content_type = req_body.get('contentType', 'application/octet-stream')
        if not name or not content_bytes:
            return func.HttpResponse("Missing required fields: name, contentBytes", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": name,
            "contentBytes": content_bytes,
            "contentType": content_type,
        }
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/attachments",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_mail_folders_http(req: func.HttpRequest) -> func.HttpResponse:
    """List mail folders for the signed-in user. Delegated preferred with app-only fallback."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if delegated and base:
            token, path = delegated, f"{base}/mailFolders"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/mailFolders"

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
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def send_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Send an email. Delegated preferred; app-only fallback via /users/{id}/sendMail."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        to_email = req_body.get('to')
        subject = req_body.get('subject')
        body = req_body.get('body')
        body_type = req_body.get('bodyType', 'text')
        if not all([to_email, subject, body]):
            return func.HttpResponse("Missing required fields: to, subject, body", status_code=400)

        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Mail.Send")
        if delegated and base:
            token, path = delegated, "/me/sendMail"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/sendMail"

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
        data = {
            "message": {
                "subject": subject,
                "body": {"contentType": body_type, "content": body},
                "toRecipients": [{"emailAddress": {"address": to_email}}],
            }
        }
        response = requests.post(f"{GRAPH_API_ENDPOINT}{path}", headers=headers, json=data, timeout=10)
        if response.status_code == 202:
            return func.HttpResponse(f"Email sent successfully to {to_email}", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_inbox_http(req: func.HttpRequest) -> func.HttpResponse:
    """List inbox messages. Delegated preferred; app-only fallback via /users/{id}."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("User.Read Mail.Read")
        if delegated and base:
            token, path = delegated, f"{base}/mailFolders/inbox/messages"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/mailFolders/inbox/messages"

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
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
            params={"$select": "id,subject,from,receivedDateTime,isRead", "$top": "20", "$orderby": "receivedDateTime desc"},
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


def move_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Move a message to another folder. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        destination_id = req_body.get('destinationId')
        if not destination_id:
            return func.HttpResponse("Missing required field: destinationId", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"destinationId": destination_id}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/move",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def copy_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Copy a message to another folder. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        destination_id = req_body.get('destinationId')
        if not destination_id:
            return func.HttpResponse("Missing required field: destinationId", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"destinationId": destination_id}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/copy",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def reply_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Reply to a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        comment = req_body.get('comment', '')

        token, base = _get_token_and_base_for_me("Mail.Send")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"comment": comment}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/reply",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Reply sent successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def reply_all_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Reply all to a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        comment = req_body.get('comment', '')

        token, base = _get_token_and_base_for_me("Mail.Send")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {"comment": comment}
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/replyAll",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Reply all sent successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def forward_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """Forward a message. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        to_recipients = req_body.get('toRecipients', [])
        comment = req_body.get('comment', '')
        if not to_recipients:
            return func.HttpResponse("Missing required field: toRecipients", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.Send")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        data = {
            "comment": comment,
            "toRecipients": [{"emailAddress": {"address": email}} for email in to_recipients],
        }
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}/forward",
            headers=headers,
            json=data,
            timeout=10,
        )
        if response.status_code == 202:
            return func.HttpResponse("Message forwarded successfully", status_code=202)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


