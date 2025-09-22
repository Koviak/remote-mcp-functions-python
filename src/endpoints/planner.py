import json
import requests
import azure.functions as func

from endpoints.common import GRAPH_API_ENDPOINT, get_access_token, build_json_headers


def list_plans_http(req: func.HttpRequest) -> func.HttpResponse:
    """List plans for a group. Uses application token."""
    try:
        group_id = req.params.get('groupId')
        if not group_id:
            return func.HttpResponse("Missing required parameter: groupId", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
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


def create_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new plan. Uses application token."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        title = req_body.get('title')
        group_id = req_body.get('groupId')
        if not title or not group_id:
            return func.HttpResponse("Missing required fields: title and groupId", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        data = {"owner": group_id, "title": title}

        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/plans",
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


def list_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    """List tasks in a plan. Uses application token."""
    try:
        plan_id = req.params.get('planId')
        if not plan_id:
            return func.HttpResponse("Missing required parameter: planId", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
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


def create_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new task. Uses application token."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)

        plan_id = req_body.get('planId')
        title = req_body.get('title')
        bucket_id = req_body.get('bucketId')
        if not plan_id or not title:
            return func.HttpResponse("Missing required fields: planId and title", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        data = {"planId": plan_id, "title": title}

        if bucket_id:
            try:
                buckets_resp = requests.get(
                    f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets",
                    headers=headers,
                    timeout=10,
                )
                if buckets_resp.status_code == 200:
                    bucket_ids = {b.get("id") for b in buckets_resp.json().get("value", [])}
                    if bucket_id in bucket_ids:
                        data["bucketId"] = bucket_id
            except Exception:
                pass

        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/tasks",
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


def get_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific plan. Uses application token."""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse("Missing plan_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
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


def update_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update a plan's title. Uses application token."""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse("Missing plan_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        title = req_body.get('title')
        if not title:
            return func.HttpResponse("Missing required field: title", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        headers["If-Match"] = "*"
        data = {"title": title}

        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
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


def delete_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a plan. Uses application token."""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse("Missing plan_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = {"Authorization": f"Bearer {token}", "If-Match": "*"}
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 204:
            return func.HttpResponse("Plan deleted successfully", status_code=204)
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}", status_code=response.status_code
        )
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def update_task_progress_http(req: func.HttpRequest) -> func.HttpResponse:
    """Update task percentComplete. Uses application token."""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)

        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse("Request body required", status_code=400)
        percent_complete = req_body.get('percentComplete')
        if percent_complete is None:
            return func.HttpResponse("Missing required field: percentComplete", status_code=400)
        if (not isinstance(percent_complete, int) or not 0 <= percent_complete <= 100):
            return func.HttpResponse("percentComplete must be an integer between 0 and 100", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        headers["If-Match"] = "*"
        data = {"percentComplete": percent_complete}
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
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


def get_plan_details_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get plan details. Uses application token."""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse("Missing plan_id in URL path", status_code=400)

        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)

        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/details",
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


