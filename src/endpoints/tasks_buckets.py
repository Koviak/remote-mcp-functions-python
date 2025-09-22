import requests
import azure.functions as func

from .common import GRAPH_API_ENDPOINT, get_access_token, build_json_headers


def get_task_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def update_task_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        headers["If-Match"] = "*"
        data = {}
        if "title" in req_body:
            data["title"] = req_body["title"]
        if "percentComplete" in req_body:
            percent = req_body["percentComplete"]
            if (not isinstance(percent, int) or not 0 <= percent <= 100):
                return func.HttpResponse("percentComplete must be an integer between 0 and 100", status_code=400)
            data["percentComplete"] = percent
        if "dueDateTime" in req_body:
            data["dueDateTime"] = req_body["dueDateTime"]
        if "startDateTime" in req_body:
            data["startDateTime"] = req_body["startDateTime"]
        if not data:
            return func.HttpResponse("No update fields provided", status_code=400)
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}", headers=headers, json=data, timeout=10
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def delete_task_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = {"Authorization": f"Bearer {token}", "If-Match": "*"}
        response = requests.delete(f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}", headers=headers, timeout=10)
        if response.status_code == 204:
            return func.HttpResponse("Task deleted successfully", status_code=204)
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_task_details_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/details", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_my_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Keep as delegated endpoint for /me
        from agent_auth_manager import get_agent_token
        token = get_agent_token("Tasks.ReadWrite")
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/me/planner/tasks", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_user_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.route_params.get('user_id', 'me')
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        if user_id != "me":
            endpoint = f"{GRAPH_API_ENDPOINT}/users/{user_id}/planner/tasks"
        else:
            endpoint = f"{GRAPH_API_ENDPOINT}/me/planner/tasks"
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def list_buckets_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse("Missing plan_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def create_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        plan_id = req_body.get('planId')
        name = req_body.get('name')
        if not plan_id or not name:
            return func.HttpResponse("Missing required fields: planId and name", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        data = {"planId": plan_id, "name": name}
        response = requests.post(f"{GRAPH_API_ENDPOINT}/planner/buckets", headers=headers, json=data, timeout=10)
        if response.status_code == 201:
            return func.HttpResponse(response.text, status_code=201, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse("Missing bucket_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}", headers=headers, timeout=10)
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def update_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse("Missing bucket_id in URL path", status_code=400)
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        name = req_body.get('name')
        if not name:
            return func.HttpResponse("Missing required field: name", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = build_json_headers(token)
        headers["If-Match"] = "*"
        data = {"name": name}
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}", headers=headers, json=data, timeout=10
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def delete_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse("Missing bucket_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Check Azure AD credentials.", status_code=401)
        headers = {"Authorization": f"Bearer {token}", "If-Match": "*"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}", headers=headers, timeout=10
        )
        if response.status_code == 204:
            return func.HttpResponse("Bucket deleted successfully", status_code=204)
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


