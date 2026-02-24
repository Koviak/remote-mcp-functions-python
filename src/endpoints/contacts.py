import json

import azure.functions as func
import requests

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    _get_token_and_base_for_me,
    build_json_headers,
)


DEFAULT_CONTACT_SELECT = (
    "id,displayName,givenName,surname,companyName,jobTitle,"
    "emailAddresses,businessPhones,mobilePhone,homePhones,"
    "createdDateTime,lastModifiedDateTime"
)


def list_contacts_http(req: func.HttpRequest) -> func.HttpResponse:
    """List contacts for signed-in user. Delegated token required."""
    try:
        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for contacts.",
                status_code=401,
            )

        params = {
            "$select": req.params.get("$select")
            or req.params.get("select")
            or DEFAULT_CONTACT_SELECT,
            "$top": req.params.get("$top") or req.params.get("top") or "100",
        }
        if req.params.get("$filter") or req.params.get("filter"):
            params["$filter"] = req.params.get("$filter") or req.params.get("filter")
        if req.params.get("$search") or req.params.get("search"):
            params["$search"] = req.params.get("$search") or req.params.get("search")

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/contacts",
            params=params,
            headers=headers,
            timeout=15,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text, status_code=200, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def list_contacts_delta_http(req: func.HttpRequest) -> func.HttpResponse:
    """List contacts delta changes; accepts delta URL or token."""
    try:
        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "auth_unavailable",
                        "message": "Delegated token missing for contacts delta.",
                    }
                ),
                status_code=503,
                mimetype="application/json",
            )

        folder_id = req.params.get("folderId") or req.params.get("folder_id")
        if folder_id:
            path = f"{base}/contactFolders/{folder_id}/contacts/delta"
        else:
            path = f"{base}/contacts/delta"

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
                or DEFAULT_CONTACT_SELECT,
                "$top": req.params.get("$top") or req.params.get("top") or "100",
            }
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}{path}",
                params=params,
                headers=headers,
                timeout=15,
            )

        if response.status_code == 200:
            return func.HttpResponse(
                response.text, status_code=200, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def get_contact_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific contact by id."""
    try:
        contact_id = req.route_params.get("contact_id")
        if not contact_id:
            return func.HttpResponse("Missing contact_id in URL path", status_code=400)
        if contact_id.lower() == "delta":
            return list_contacts_delta_http(req)

        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for contacts.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{base}/contacts/{contact_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text, status_code=200, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def create_contact_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a contact for signed-in user."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for contacts.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}{base}/contacts",
            headers=headers,
            json=req_body,
            timeout=10,
        )
        if response.status_code == 201:
            return func.HttpResponse(
                response.text, status_code=201, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def update_contact_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update a contact for signed-in user."""
    try:
        contact_id = req.route_params.get("contact_id")
        if not contact_id:
            return func.HttpResponse("Missing contact_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for contacts.",
                status_code=401,
            )

        headers = build_json_headers(token)
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}{base}/contacts/{contact_id}",
            headers=headers,
            json=req_body,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(
                response.text, status_code=200, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)


def delete_contact_http(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a contact for signed-in user."""
    try:
        contact_id = req.route_params.get("contact_id")
        if not contact_id:
            return func.HttpResponse("Missing contact_id in URL path", status_code=400)

        token, base = _get_token_and_base_for_me("Contacts.ReadWrite")
        if not token or not base:
            return func.HttpResponse(
                "Authentication failed. Delegated token required for contacts.",
                status_code=401,
            )

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}{base}/contacts/{contact_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 204:
            return func.HttpResponse("Contact deleted successfully", status_code=204)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )
    except Exception as exc:
        return func.HttpResponse(f"Error: {str(exc)}", status_code=500)
