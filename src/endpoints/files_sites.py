import requests
import azure.functions as func

from endpoints.common import (
    GRAPH_API_ENDPOINT,
    get_access_token,
    _get_agent_user_id,
    _get_token_and_base_for_me,
    build_json_headers,
)


def list_drives_http(req: func.HttpRequest) -> func.HttpResponse:
    """List drives for the agent user. Delegated preferred; app-only fallback via /users/{id}."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Files.ReadWrite.All")
        if delegated and base:
            token, path = delegated, f"{base}/drives"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/drives"

        if not token or not path:
            return func.HttpResponse(
                "{\"error\":\"auth_unavailable\",\"message\":\"Delegated token missing and app-only fallback not configured\"}",
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}{path}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_root_items_http(req: func.HttpRequest) -> func.HttpResponse:
    """List root items for the agent user drive. Delegated preferred; fallback app-only."""
    try:
        token, path = (None, None)
        delegated, base = _get_token_and_base_for_me("Files.ReadWrite.All")
        if delegated and base:
            token, path = delegated, f"{base}/drive/root/children"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/drive/root/children"

        if not token or not path:
            return func.HttpResponse(
                "{\"error\":\"auth_unavailable\",\"message\":\"Delegated token missing and app-only fallback not configured\"}",
                status_code=503,
                mimetype="application/json",
            )

        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}{path}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def download_file_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get file download URL. Application token used."""
    try:
        drive_id = req.route_params.get('drive_id')
        item_id = req.route_params.get('item_id')
        if not all([drive_id, item_id]):
            return func.HttpResponse("Missing drive_id or item_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/drives/{drive_id}/items/{item_id}/content",
            headers=headers,
            timeout=10,
            allow_redirects=False,
        )
        if response.status_code == 302:
            download_url = response.headers.get('Location')
            return func.HttpResponse(
                f"{{\"downloadUrl\":\"{download_url}\"}}",
                status_code=200,
                mimetype="application/json",
            )
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def sites_search_http(req: func.HttpRequest) -> func.HttpResponse:
    """Search SharePoint sites. Application token used."""
    try:
        query = req.params.get('query')
        if not query:
            return func.HttpResponse("Missing required parameter: query", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/sites?search={query}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_site_drives_http(req: func.HttpRequest) -> func.HttpResponse:
    """List drives for a SharePoint site. Application token used."""
    try:
        site_id = req.route_params.get('site_id') or req.params.get('siteId')
        hostname = req.params.get('hostname')
        site_path = req.params.get('path')
        if not site_id and not (hostname and site_path):
            return func.HttpResponse("Missing site_id or (hostname and path) parameters", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)

        if not site_id:
            lookup = requests.get(
                f"{GRAPH_API_ENDPOINT}/sites/{hostname}:/sites/{site_path}",
                headers=headers,
                timeout=10,
            )
            if lookup.status_code != 200:
                return func.HttpResponse(f"Error: {lookup.status_code} - {lookup.text}", status_code=lookup.status_code)
            site_id = lookup.json().get("id")
            if not site_id:
                return func.HttpResponse("Site not found", status_code=404)

        resp = requests.get(f"{GRAPH_API_ENDPOINT}/sites/{site_id}/drives", headers=headers, timeout=10)
        if resp.status_code == 200:
            return func.HttpResponse(resp.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {resp.status_code} - {resp.text}", status_code=resp.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


