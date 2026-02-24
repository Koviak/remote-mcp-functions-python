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

DEFAULT_INBOX_SELECT = (
    "id,subject,from,receivedDateTime,isRead,"
    "internetMessageId,changeKey,conversationId,lastModifiedDateTime,"
    "createdDateTime,toRecipients,ccRecipients,bccRecipients,replyTo,hasAttachments"
)


def _normalize_content_type(value: object) -> str:
    """Normalize mail body content type to Graph-supported values."""
    if isinstance(value, str) and value.strip().lower() == "html":
        return "HTML"
    return "Text"


def _normalize_recipients(raw_value: object, field_name: str) -> list[dict[str, dict[str, str]]]:
    """Convert recipient lists into Graph `emailAddress` payload objects."""
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"{field_name} must be a list of email addresses")

    recipients: list[dict[str, dict[str, str]]] = []
    for item in raw_value:
        if isinstance(item, str) and item.strip():
            recipients.append({"emailAddress": {"address": item.strip()}})
            continue

        if isinstance(item, dict):
            email_address = item.get("emailAddress")
            if isinstance(email_address, dict):
                address = email_address.get("address")
                if isinstance(address, str) and address.strip():
                    recipients.append({"emailAddress": {"address": address.strip()}})
                    continue

            address = item.get("address")
            if isinstance(address, str) and address.strip():
                recipients.append({"emailAddress": {"address": address.strip()}})
                continue

        raise ValueError(
            f"{field_name} must contain non-empty email strings or emailAddress objects"
        )

    return recipients


def _build_mail_message(
    req_body: dict,
    *,
    require_to: bool,
    require_subject: bool,
    require_body: bool,
) -> dict:
    """Build canonical Microsoft Graph mail message payload from request body."""
    if not isinstance(req_body, dict):
        raise ValueError("Request body must be a JSON object")

    message: dict = {}

    subject = req_body.get("subject")
    if subject is None:
        if require_subject:
            raise ValueError("Missing required field: subject")
    elif not isinstance(subject, str):
        raise ValueError("subject must be a string")
    else:
        message["subject"] = subject

    body_content = req_body.get("bodyContent")
    if body_content is None:
        if require_body:
            raise ValueError("Missing required field: bodyContent")
    elif not isinstance(body_content, str):
        raise ValueError("bodyContent must be a string")
    else:
        message["body"] = {
            "contentType": _normalize_content_type(req_body.get("contentType")),
            "content": body_content,
        }

    to_recipients = _normalize_recipients(req_body.get("toRecipients"), "toRecipients")
    if require_to and not to_recipients:
        raise ValueError("Missing required field: toRecipients")
    if to_recipients:
        message["toRecipients"] = to_recipients

    cc_recipients = _normalize_recipients(req_body.get("ccRecipients"), "ccRecipients")
    if cc_recipients:
        message["ccRecipients"] = cc_recipients

    bcc_recipients = _normalize_recipients(req_body.get("bccRecipients"), "bccRecipients")
    if bcc_recipients:
        message["bccRecipients"] = bcc_recipients

    importance = req_body.get("importance")
    if importance is not None:
        if not isinstance(importance, str):
            raise ValueError("importance must be one of: low, normal, high")
        normalized = importance.strip().lower()
        if normalized not in {"low", "normal", "high"}:
            raise ValueError("importance must be one of: low, normal, high")
        message["importance"] = normalized

    request_delivery_receipt = req_body.get("requestDeliveryReceipt")
    if request_delivery_receipt is not None:
        if not isinstance(request_delivery_receipt, bool):
            raise ValueError("requestDeliveryReceipt must be a boolean")
        message["isDeliveryReceiptRequested"] = request_delivery_receipt

    request_read_receipt = req_body.get("requestReadReceipt")
    if request_read_receipt is not None:
        if not isinstance(request_read_receipt, bool):
            raise ValueError("requestReadReceipt must be a boolean")
        message["isReadReceiptRequested"] = request_read_receipt

    return message


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
        if message_id.lower() == "delta":
            # Azure Functions route resolution may dispatch /me/messages/delta
            # to /me/messages/{message_id}. Delegate explicitly.
            return list_inbox_delta_http(req)

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

        try:
            data = _build_mail_message(
                req_body,
                require_to=False,
                require_subject=False,
                require_body=False,
            )
        except ValueError as validation_exc:
            return func.HttpResponse(str(validation_exc), status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
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


def mark_as_read_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update a message read-state. Delegated token required."""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse("Missing message_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        if "isRead" not in req_body:
            return func.HttpResponse("Missing required field: isRead", status_code=400)

        is_read = req_body.get("isRead")
        if not isinstance(is_read, bool):
            return func.HttpResponse("isRead must be a boolean", status_code=400)

        token, base = _get_token_and_base_for_me("Mail.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for mail.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}{base}/messages/{message_id}",
            headers=headers,
            json={"isRead": is_read},
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

        try:
            message_payload = _build_mail_message(
                req_body,
                require_to=True,
                require_subject=True,
                require_body=True,
            )
        except ValueError as validation_exc:
            return func.HttpResponse(str(validation_exc), status_code=400)

        save_to_sent_items = req_body.get("saveToSentItems", True)
        if not isinstance(save_to_sent_items, bool):
            return func.HttpResponse("saveToSentItems must be a boolean", status_code=400)

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
            "message": message_payload,
            "saveToSentItems": save_to_sent_items,
        }
        response = requests.post(f"{GRAPH_API_ENDPOINT}{path}", headers=headers, json=data, timeout=10)
        if response.status_code == 202:
            return func.HttpResponse(
                "Email sent successfully",
                status_code=202,
            )
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
        params = {
            "$select": req.params.get("$select") or req.params.get("select") or DEFAULT_INBOX_SELECT,
            "$top": req.params.get("$top") or req.params.get("top") or "20",
        }
        skip = req.params.get("$skip") or req.params.get("skip")
        if skip:
            params["$skip"] = skip
        filter_value = req.params.get("$filter") or req.params.get("filter")
        if filter_value:
            params["$filter"] = filter_value
        search_value = req.params.get("$search") or req.params.get("search")
        if search_value:
            params["$search"] = search_value
        else:
            # Graph rejects $search with $orderby (SearchWithOrderBy), so
            # only apply inbox default ordering when search is not requested.
            params["$orderby"] = (
                req.params.get("$orderby")
                or req.params.get("orderby")
                or "receivedDateTime desc"
            )

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
            params=params,
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


def list_inbox_delta_http(req: func.HttpRequest) -> func.HttpResponse:
    """List inbox message deltas. Supports passing a prior delta URL/token."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("User.Read Mail.Read")
        if delegated and base:
            token, path = delegated, f"{base}/mailFolders/inbox/messages/delta"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/mailFolders/inbox/messages/delta"

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
        delta_token = req.params.get("deltaToken") or req.params.get("delta_token")

        if delta_token:
            if delta_token.startswith("http://") or delta_token.startswith("https://"):
                if not delta_token.startswith(GRAPH_API_ENDPOINT):
                    return func.HttpResponse(
                        json.dumps(
                            {
                                "error": "invalid_delta_token",
                                "message": "deltaToken URL must target Microsoft Graph endpoint",
                            }
                        ),
                        status_code=400,
                        mimetype="application/json",
                    )
                response = requests.get(delta_token, headers=headers, timeout=15)
            else:
                response = requests.get(
                    f"{GRAPH_API_ENDPOINT}{path}",
                    params={"$deltatoken": delta_token},
                    headers=headers,
                    timeout=15,
                )
        else:
            params = {
                "$select": req.params.get("$select")
                or req.params.get("select")
                or DEFAULT_INBOX_SELECT,
                "$top": req.params.get("$top") or req.params.get("top") or "50",
            }
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}{path}",
                params=params,
                headers=headers,
                timeout=15,
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


