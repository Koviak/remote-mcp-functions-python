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


def upload_file_http(req: func.HttpRequest) -> func.HttpResponse:
    """Upload file content to the agent drive (delegated preferred, app fallback)."""
    try:
        route_path = None
        if getattr(req, 'route_params', None):
            route_path = req.route_params.get('file_path') or req.route_params.get('*_file_path') or req.route_params.get('star_file_path')
        query_path = req.params.get('filePath') if req.params else None
        file_path = route_path or query_path
        if file_path and file_path.startswith(':'):
            file_path = file_path[1:]
        if file_path and file_path.endswith(':/content'):
            file_path = file_path[:-9]
        if not file_path:
            return func.HttpResponse("Missing file path", status_code=400)

        normalized_path = file_path.strip()
        if normalized_path.startswith('/'):
            normalized_path = normalized_path[1:]
        if normalized_path.endswith(':'):
            normalized_path = normalized_path[:-1]
        normalized_path = normalized_path.replace('\\', '/')
        if not normalized_path:
            return func.HttpResponse("File path resolved empty", status_code=400)

        conflict = None
        if req.params:
            conflict = req.params.get('conflictBehavior') or req.params.get('@microsoft.graph.conflictBehavior')

        delegated_token, base = _get_token_and_base_for_me("Files.ReadWrite.All")
        graph_path = None
        token = None
        if delegated_token and base:
            token = delegated_token
            graph_path = f"{GRAPH_API_ENDPOINT}{base}/drive/root:/{normalized_path}:/content"
        else:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token = app_token
                graph_path = f"{GRAPH_API_ENDPOINT}/users/{user_id}/drive/root:/{normalized_path}:/content"

        if not token or not graph_path:
            return func.HttpResponse("{\"error\":\"auth_unavailable\",\"message\":\"Delegated token missing and app-only fallback not configured\"}", status_code=503, mimetype="application/json")

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': req.headers.get('Content-Type', 'application/octet-stream') if getattr(req, 'headers', None) else 'application/octet-stream',
        }
        params = {}
        if conflict:
            params['@microsoft.graph.conflictBehavior'] = conflict

        body = req.get_body() or b''
        response = requests.put(
            graph_path,
            headers=headers,
            params=params or None,
            data=body,
            timeout=30,
        )

        content_type = response.headers.get('content-type', '')
        mimetype = 'application/json' if content_type.startswith('application/json') or content_type.startswith('text/json') else None
        return func.HttpResponse(response.text, status_code=response.status_code, mimetype=mimetype)
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


