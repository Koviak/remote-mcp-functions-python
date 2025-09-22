import requests
import azure.functions as func

from endpoints.common import GRAPH_API_ENDPOINT, get_access_token, build_json_headers


def get_assigned_to_task_board_format_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/assignedToTaskBoardFormat",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_bucket_task_board_format_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/bucketTaskBoardFormat",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


def get_progress_task_board_format_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse("Missing task_id in URL path", status_code=400)
        token = get_access_token()
        if not token:
            return func.HttpResponse("Authentication failed. Application token required.", status_code=401)
        headers = build_json_headers(token)
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/progressTaskBoardFormat",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            return func.HttpResponse(response.text, status_code=200, mimetype="application/json")
        return func.HttpResponse(f"Error: {response.status_code} - {response.text}", status_code=response.status_code)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


