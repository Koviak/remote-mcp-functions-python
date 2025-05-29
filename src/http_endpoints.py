import os
import json
import requests
from azure.identity import ClientSecretCredential
import azure.functions as func

# Global app instance - will be set by register_http_endpoints
app = None

# Microsoft Graph API endpoint
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def get_access_token():
    """Get access token for Microsoft Graph API"""
    tenant_id = os.environ.get("TENANT_ID")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        return None
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token


# HTTP Endpoint Functions (without decorators)

def list_groups_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list Microsoft 365 groups"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_users_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list all users in the organization"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users"
            "?$select=id,displayName,userPrincipalName,mail"
            "&$orderby=displayName",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_groups_with_planner_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list only groups that have Planner plans"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def check_group_planner_status_http(
    req: func.HttpRequest
) -> func.HttpResponse:
    """HTTP endpoint to check if a group has Planner enabled"""
    try:
        group_name = req.params.get('displayName')
        if not group_name:
            return func.HttpResponse(
                "Missing required parameter: displayName",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            f"?$filter=displayName eq '{group_name}'"
            "&$select=id,displayName,hasPlanner",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return func.HttpResponse(
                f"Error finding group: {response.status_code} - "
                f"{response.text}",
                status_code=response.status_code
            )
        
        groups = response.json()["value"]
        if not groups:
            return func.HttpResponse(
                f"No group found with display name: {group_name}",
                status_code=404
            )
        
        group = groups[0]
        result = {
            "groupId": group["id"],
            "displayName": group["displayName"],
            "hasPlanner": group.get("hasPlanner", False)
        }
        
        plans_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group['id']}/planner/plans",
            headers=headers,
            timeout=10
        )
        
        if plans_response.status_code == 200:
            plans = plans_response.json()["value"]
            result["plans"] = [
                {"id": p["id"], "title": p["title"]} for p in plans
            ]
            result["planCount"] = len(plans)
        else:
            result["plansError"] = (
                f"{plans_response.status_code} - {plans_response.text}"
            )
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def hello_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for connectivity test"""
    return func.HttpResponse(
        "Hello I am MCPTool! (HTTP endpoint)",
        status_code=200,
        mimetype="text/plain"
    )


def list_plans_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list plans for a group"""
    try:
        group_id = req.params.get('groupId')
        if not group_id:
            return func.HttpResponse(
                "Missing required parameter: groupId",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def create_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a new plan"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        title = req_body.get('title')
        group_id = req_body.get('groupId')
        
        if not title or not group_id:
            return func.HttpResponse(
                "Missing required fields: title and groupId",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "owner": group_id,
            "title": title
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/plans",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            return func.HttpResponse(
                response.text,
                status_code=201,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list tasks in a plan"""
    try:
        plan_id = req.params.get('planId')
        if not plan_id:
            return func.HttpResponse(
                "Missing required parameter: planId",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def create_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a new task"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        plan_id = req_body.get('planId')
        title = req_body.get('title')
        bucket_id = req_body.get('bucketId')  # Optional
        
        if not plan_id or not title:
            return func.HttpResponse(
                "Missing required fields: planId and title",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "planId": plan_id,
            "title": title
        }
        
        if bucket_id:
            data["bucketId"] = bucket_id
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/tasks",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            return func.HttpResponse(
                response.text,
                status_code=201,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def update_task_progress_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to update task progress"""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse(
                "Missing task_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        percent_complete = req_body.get('percentComplete')
        if percent_complete is None:
            return func.HttpResponse(
                "Missing required field: percentComplete",
                status_code=400
            )
        
        if (not isinstance(percent_complete, int) or
                not 0 <= percent_complete <= 100):
            return func.HttpResponse(
                "percentComplete must be an integer between 0 and 100",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"
        }
        
        data = {
            "percentComplete": percent_complete
        }
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# Plan Management HTTP Endpoints

def get_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific plan"""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse(
                "Missing plan_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def update_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to update a plan"""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse(
                "Missing plan_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        title = req_body.get('title')
        if not title:
            return func.HttpResponse(
                "Missing required field: title",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"
        }
        
        data = {"title": title}
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def delete_plan_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to delete a plan"""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse(
                "Missing plan_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "If-Match": "*"
        }
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                "Plan deleted successfully",
                status_code=204
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def get_plan_details_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get plan details"""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse(
                "Missing plan_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/details",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# Task Management HTTP Endpoints

def get_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific task"""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse(
                "Missing task_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def update_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to update a task with full options"""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse(
                "Missing task_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"
        }
        
        data = {}
        if "title" in req_body:
            data["title"] = req_body["title"]
        if "percentComplete" in req_body:
            percent = req_body["percentComplete"]
            if (not isinstance(percent, int) or
                    not 0 <= percent <= 100):
                return func.HttpResponse(
                    "percentComplete must be an integer between 0 and 100",
                    status_code=400
                )
            data["percentComplete"] = percent
        if "dueDateTime" in req_body:
            data["dueDateTime"] = req_body["dueDateTime"]
        if "startDateTime" in req_body:
            data["startDateTime"] = req_body["startDateTime"]
        
        if not data:
            return func.HttpResponse(
                "No update fields provided",
                status_code=400
            )
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def delete_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to delete a task"""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse(
                "Missing task_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "If-Match": "*"
        }
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                "Task deleted successfully",
                status_code=204
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def get_task_details_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get task details"""
    try:
        task_id = req.route_params.get('task_id')
        if not task_id:
            return func.HttpResponse(
                "Missing task_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/details",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# User-Centric Task HTTP Endpoints

def list_my_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list my tasks"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/me/planner/tasks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_user_tasks_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list user tasks"""
    try:
        user_id = req.route_params.get('user_id', 'me')
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if user_id != "me":
            endpoint = f"{GRAPH_API_ENDPOINT}/users/{user_id}/planner/tasks"
        else:
            endpoint = f"{GRAPH_API_ENDPOINT}/me/planner/tasks"
        
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# Bucket Management HTTP Endpoints

def list_buckets_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list buckets in a plan"""
    try:
        plan_id = req.route_params.get('plan_id')
        if not plan_id:
            return func.HttpResponse(
                "Missing plan_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/buckets",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def create_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a bucket"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        plan_id = req_body.get('planId')
        name = req_body.get('name')
        
        if not plan_id or not name:
            return func.HttpResponse(
                "Missing required fields: planId and name",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "planId": plan_id,
            "name": name
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/planner/buckets",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            return func.HttpResponse(
                response.text,
                status_code=201,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def get_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific bucket"""
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse(
                "Missing bucket_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def update_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to update a bucket"""
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse(
                "Missing bucket_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        name = req_body.get('name')
        if not name:
            return func.HttpResponse(
                "Missing required field: name",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"
        }
        
        data = {"name": name}
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def delete_bucket_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to delete a bucket"""
    try:
        bucket_id = req.route_params.get('bucket_id')
        if not bucket_id:
            return func.HttpResponse(
                "Missing bucket_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "If-Match": "*"
        }
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/planner/buckets/{bucket_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                "Bucket deleted successfully",
                status_code=204
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# Additional HTTP Endpoints for new tools

def get_user_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific user"""
    try:
        user_id = req.route_params.get('user_id')
        if not user_id:
            return func.HttpResponse(
                "Missing user_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users/{user_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_deleted_users_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list deleted users"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/directory/deletedItems/microsoft.graph.user",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_group_members_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list group members"""
    try:
        group_id = req.route_params.get('group_id')
        if not group_id:
            return func.HttpResponse(
                "Missing group_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/members",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def send_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to send an email"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        to_email = req_body.get('to')
        subject = req_body.get('subject')
        body = req_body.get('body')
        body_type = req_body.get('bodyType', 'text')
        
        if not all([to_email, subject, body]):
            return func.HttpResponse(
                "Missing required fields: to, subject, body",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            }
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/sendMail",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                f"Email sent successfully to {to_email}",
                status_code=202
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_inbox_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list inbox messages"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/me/mailFolders/inbox/messages"
            "?$select=id,subject,from,receivedDateTime,isRead"
            "&$top=20&$orderby=receivedDateTime desc",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_teams_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list teams"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/teams",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def add_user_to_group_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to add user to group"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        group_id = req_body.get('groupId')
        user_id = req_body.get('userId')
        
        if not all([group_id, user_id]):
            return func.HttpResponse(
                "Missing required fields: groupId, userId",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "@odata.id": f"{GRAPH_API_ENDPOINT}/users/{user_id}"
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/members/$ref",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                f"User {user_id} added to group {group_id} successfully",
                status_code=204
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def reset_password_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to reset user password"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        user_id = req_body.get('userId')
        temp_password = req_body.get('temporaryPassword')
        
        if not all([user_id, temp_password]):
            return func.HttpResponse(
                "Missing required fields: userId, temporaryPassword",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": temp_password
            }
        }
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/users/{user_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                f"Password reset successfully for user {user_id}",
                status_code=204
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def create_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create calendar event"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        subject = req_body.get('subject')
        start_time = req_body.get('start')
        end_time = req_body.get('end')
        attendees_str = req_body.get('attendees', '')
        
        if not all([subject, start_time, end_time]):
            return func.HttpResponse(
                "Missing required fields: subject, start, end",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "subject": subject,
            "start": {
                "dateTime": start_time,
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "UTC"
            }
        }
        
        if attendees_str:
            attendees = []
            for email in attendees_str.split(","):
                email = email.strip()
                if email:
                    attendees.append({
                        "emailAddress": {
                            "address": email
                        }
                    })
            data["attendees"] = attendees
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/events",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            event = response.json()
            return func.HttpResponse(
                json.dumps({"id": event["id"], "message": "Event created successfully"}),
                status_code=201,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_upcoming_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list upcoming events"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/me/events"
            "?$select=id,subject,start,end,attendees"
            "&$top=20&$orderby=start/dateTime",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


# Additional endpoints for Teams, Files, Security
def list_channels_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list channels in a team"""
    try:
        team_id = req.route_params.get('team_id')
        if not team_id:
            return func.HttpResponse(
                "Missing team_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def post_channel_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to post message to Teams channel"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        team_id = req_body.get('teamId')
        channel_id = req_body.get('channelId')
        message = req_body.get('message')
        
        if not all([team_id, channel_id, message]):
            return func.HttpResponse(
                "Missing required fields: teamId, channelId, message",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "body": {
                "content": message
            }
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels/{channel_id}/messages",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            return func.HttpResponse(
                f"Message posted successfully to channel {channel_id}",
                status_code=201
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_drives_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list drives"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/me/drives",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_root_items_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list root items in drive"""
    try:
        drive_id = req.params.get('driveId')
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if drive_id:
            endpoint = f"{GRAPH_API_ENDPOINT}/drives/{drive_id}/root/children"
        else:
            endpoint = f"{GRAPH_API_ENDPOINT}/me/drive/root/children"
        
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def download_file_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get file download URL"""
    try:
        drive_id = req.route_params.get('drive_id')
        item_id = req.route_params.get('item_id')
        
        if not all([drive_id, item_id]):
            return func.HttpResponse(
                "Missing drive_id or item_id in URL path",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/drives/{drive_id}/items/{item_id}/content",
            headers=headers,
            timeout=10,
            allow_redirects=False
        )
        
        if response.status_code == 302:
            download_url = response.headers.get('Location')
            return func.HttpResponse(
                json.dumps({"downloadUrl": download_url}),
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def sites_search_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to search SharePoint sites"""
    try:
        query = req.params.get('query')
        if not query:
            return func.HttpResponse(
                "Missing required parameter: query",
                status_code=400
            )
        
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/sites?search={query}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def usage_summary_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get usage summary"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/reports/getOffice365ActiveUserCounts(period='D7')",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def get_alerts_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get security alerts"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/security/alerts",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_managed_devices_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list managed devices"""
    try:
        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/deviceManagement/managedDevices",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return func.HttpResponse(
                response.text,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                f"Error: {response.status_code} - {response.text}",
                status_code=response.status_code
            )
            
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def register_http_endpoints(function_app):
    """Register all HTTP endpoints with the provided function app instance"""
    global app
    app = function_app
    
    # Basic endpoints
    app.route(route="groups", methods=["GET"])(list_groups_http)
    app.route(route="users", methods=["GET"])(list_users_http)
    app.route(route="groups/with-planner", methods=["GET"])(
        list_groups_with_planner_http)
    app.route(route="groups/check-planner", methods=["GET"])(
        check_group_planner_status_http)
    app.route(route="hello", methods=["GET"])(hello_http)
    
    # Plan endpoints
    app.route(route="plans", methods=["GET"])(list_plans_http)
    app.route(route="plans", methods=["POST"])(create_plan_http)
    app.route(route="plans/{plan_id}", methods=["GET"])(get_plan_http)
    app.route(route="plans/{plan_id}", methods=["PATCH"])(update_plan_http)
    app.route(route="plans/{plan_id}", methods=["DELETE"])(delete_plan_http)
    app.route(route="plans/{plan_id}/details", methods=["GET"])(
        get_plan_details_http)
    
    # Task endpoints
    app.route(route="tasks", methods=["GET"])(list_tasks_http)
    app.route(route="tasks", methods=["POST"])(create_task_http)
    app.route(route="tasks/{task_id}", methods=["GET"])(get_task_http)
    app.route(route="tasks/{task_id}", methods=["PATCH"])(update_task_http)
    app.route(route="tasks/{task_id}", methods=["DELETE"])(delete_task_http)
    app.route(route="tasks/{task_id}/details", methods=["GET"])(
        get_task_details_http)
    app.route(route="tasks/{task_id}/progress", methods=["PATCH"])(
        update_task_progress_http)
    
    # User task endpoints
    app.route(route="me/tasks", methods=["GET"])(list_my_tasks_http)
    app.route(route="users/{user_id}/tasks", methods=["GET"])(
        list_user_tasks_http)
    
    # Bucket endpoints
    app.route(route="plans/{plan_id}/buckets", methods=["GET"])(
        list_buckets_http)
    app.route(route="buckets", methods=["POST"])(create_bucket_http)
    app.route(route="buckets/{bucket_id}", methods=["GET"])(get_bucket_http)
    app.route(route="buckets/{bucket_id}", methods=["PATCH"])(
        update_bucket_http)
    app.route(route="buckets/{bucket_id}", methods=["DELETE"])(
        delete_bucket_http)
    
    # Additional endpoints
    app.route(route="users/{user_id}", methods=["GET"])(get_user_http)
    app.route(route="directory/deletedItems/microsoft.graph.user", 
              methods=["GET"])(list_deleted_users_http)
    app.route(route="groups/{group_id}/members", 
              methods=["GET"])(list_group_members_http)
    app.route(route="me/sendMail", methods=["POST"])(send_message_http)
    app.route(route="me/messages", methods=["GET"])(list_inbox_http)
    app.route(route="teams", methods=["GET"])(list_teams_http)
    
    # User & Group Management
    app.route(route="groups/members", methods=["POST"])(add_user_to_group_http)
    app.route(route="users/resetPassword", methods=["POST"])(reset_password_http)
    
    # Calendar
    app.route(route="me/events", methods=["POST"])(create_event_http)
    app.route(route="me/events/upcoming", methods=["GET"])(list_upcoming_http)
    
    # Teams
    app.route(route="teams/{team_id}/channels", methods=["GET"])(
        list_channels_http)
    app.route(route="teams/messages", methods=["POST"])(
        post_channel_message_http)
    
    # Files & Sites
    app.route(route="me/drives", methods=["GET"])(list_drives_http)
    app.route(route="me/drive/root/children", methods=["GET"])(
        list_root_items_http)
    app.route(route="drives/{drive_id}/items/{item_id}/content", 
              methods=["GET"])(download_file_http)
    app.route(route="sites", methods=["GET"])(sites_search_http)
    
    # Security & Reporting
    app.route(route="reports/usage", methods=["GET"])(usage_summary_http)
    app.route(route="security/alerts", methods=["GET"])(get_alerts_http)
    app.route(route="deviceManagement/managedDevices", methods=["GET"])(
        list_managed_devices_http)
    
    print("All 34 HTTP endpoints registered successfully!") 