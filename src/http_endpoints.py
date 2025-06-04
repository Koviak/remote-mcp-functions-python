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
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
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


# Mail HTTP Endpoints

def get_mail_folders_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get mail folders"""
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
            f"{GRAPH_API_ENDPOINT}/users/{user_id}/mailFolders",
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


def get_mail_folder_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific mail folder"""
    try:
        user_id = req.route_params.get('user_id')
        folder_id = req.route_params.get('folder_id')
        if not user_id or not folder_id:
            return func.HttpResponse(
                "Missing user_id or folder_id in URL path",
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
            f"{GRAPH_API_ENDPOINT}/users/{user_id}/mailFolders/{folder_id}",
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


def create_mail_folder_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a new mail folder"""
    try:
        user_id = req.route_params.get('user_id')
        if not user_id:
            return func.HttpResponse(
                "Missing user_id in URL path",
                "Request body required",
                status_code=400
            )
        
        display_name = req_body.get('displayName')
        parent_folder_id = req_body.get('parentFolderId')
        
        if not display_name:
            return func.HttpResponse(
                "Missing required field: displayName",
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
        
        data = {"displayName": display_name}
        
        if parent_folder_id:
            url = (f"{GRAPH_API_ENDPOINT}/me/mailFolders/"
                   f"{parent_folder_id}/childFolders")
        else:
            url = f"{GRAPH_API_ENDPOINT}/me/mailFolders"
        
        response = requests.post(
            url,
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


# Calendar Operations

def list_calendars_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list calendars"""
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
            f"{GRAPH_API_ENDPOINT}/me/calendars",
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


def create_calendar_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a calendar"""
    try:
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
            "Content-Type": "application/json"
        }
        
        data = {"name": name}
        color = req_body.get('color')
        if color:
            data['color'] = color
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/calendars",
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


def accept_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to accept an event invitation"""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse(
                "Missing event_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        comment = req_body.get('comment', '') if req_body else ''
        send_response = (req_body.get('sendResponse', True) 
                         if req_body else True)
        
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
            "comment": comment,
            "sendResponse": send_response
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/events/{event_id}/accept",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Event accepted successfully",
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


def decline_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to decline an event invitation"""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse(
                "Missing event_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        comment = req_body.get('comment', '') if req_body else ''
        send_response = (req_body.get('sendResponse', True) 
                         if req_body else True)
        
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
            "comment": comment,
            "sendResponse": send_response
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/events/{event_id}/decline",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Event declined successfully",
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


def find_meeting_times_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to find meeting times"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        attendees = req_body.get('attendees', [])
        time_constraint = req_body.get('timeConstraint')
        meeting_duration = req_body.get('meetingDuration', 'PT1H')
        
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
            "attendees": [
                {"emailAddress": {"address": email}} 
                for email in attendees
            ],
            "meetingDuration": meeting_duration
        }
        
        if time_constraint:
            data['timeConstraint'] = time_constraint
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/findMeetingTimes",
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


# Planner Task Board Format Endpoints

def get_assigned_to_task_board_format_http(
    req: func.HttpRequest
) -> func.HttpResponse:
    """HTTP endpoint to get assigned to task board format"""
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
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/"
            "assignedToTaskBoardFormat",
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


def get_bucket_task_board_format_http(
    req: func.HttpRequest
) -> func.HttpResponse:
    """HTTP endpoint to get bucket task board format"""
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
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/"
            "bucketTaskBoardFormat",
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


def get_progress_task_board_format_http(
    req: func.HttpRequest
) -> func.HttpResponse:
    """HTTP endpoint to get progress task board format"""
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
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}/"
            "progressTaskBoardFormat",
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


# Additional Mail Endpoints

def get_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific message"""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse(
                "Missing message_id in URL path",
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
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}",
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


def create_draft_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to create a draft message"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        subject = req_body.get('subject')
        body = req_body.get('body')
        to_recipients = req_body.get('toRecipients', [])
        
        if not subject:
            return func.HttpResponse(
                "Missing required field: subject",
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
            "body": {
                "contentType": "text",
                "content": body or ""
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} 
                for email in to_recipients
            ]
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages",
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


def send_draft_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to send a draft message"""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse(
                "Missing message_id in URL path",
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
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/send",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Draft message sent successfully",
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


def delete_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to delete a message"""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse(
                "Missing message_id in URL path",
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
        }
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                "Message deleted successfully",
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


# Calendar View Endpoints

def get_calendar_view_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get calendar view"""
    try:
        start_date = req.params.get('startDateTime')
        end_date = req.params.get('endDateTime')
        
        if not start_date or not end_date:
            return func.HttpResponse(
                "Missing required parameters: startDateTime, endDateTime",
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
            f"{GRAPH_API_ENDPOINT}/me/calendar/calendarView"
            f"?startDateTime={start_date}&endDateTime={end_date}",
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


def get_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to get a specific event"""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse(
                "Missing event_id in URL path",
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
            f"{GRAPH_API_ENDPOINT}/me/events/{event_id}",
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


def update_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to update an event"""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse(
                "Missing event_id in URL path",
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
            "Content-Type": "application/json"
        }
        
        # Allow updating various event properties
        data = {}
        if "subject" in req_body:
            data["subject"] = req_body["subject"]
        if "start" in req_body:
            data["start"] = req_body["start"]
        if "end" in req_body:
            data["end"] = req_body["end"]
        if "body" in req_body:
            data["body"] = req_body["body"]
        if "location" in req_body:
            data["location"] = req_body["location"]
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/me/events/{event_id}",
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


def delete_event_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to delete an event"""
    try:
        event_id = req.route_params.get('event_id')
        if not event_id:
            return func.HttpResponse(
                "Missing event_id in URL path",
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
        }
        
        response = requests.delete(
            f"{GRAPH_API_ENDPOINT}/me/events/{event_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 204:
            return func.HttpResponse(
                "Event deleted successfully",
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


# Mail Attachment Endpoints

def list_attachments_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list message attachments"""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse(
                "Missing message_id in URL path",
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
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/attachments",
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


def add_attachment_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to add attachment to message"""
    try:
        message_id = req.route_params.get('message_id')
        if not message_id:
            return func.HttpResponse(
                "Missing message_id in URL path",
                status_code=400
            )
        
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        name = req_body.get('name')
        content_bytes = req_body.get('contentBytes')
        content_type = req_body.get('contentType', 'application/octet-stream')
        
        if not name or not content_bytes:
            return func.HttpResponse(
                "Missing required fields: name, contentBytes",
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
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": name,
            "contentBytes": content_bytes,
            "contentType": content_type
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/attachments",
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
    app.route(route="users/resetPassword", methods=["POST"])(
        reset_password_http)
    
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
    
    # === NEW COMPREHENSIVE MAIL ENDPOINTS ===
    
    # Mail Message Operations
    app.route(route="me/messages/{message_id}", methods=["GET"])(
        get_message_http)
    app.route(route="me/messages", methods=["POST"])(
        create_draft_message_http)
    app.route(route="me/messages/{message_id}/send", methods=["POST"])(
        send_draft_message_http)
    app.route(route="me/messages/{message_id}", methods=["DELETE"])(
        delete_message_http)
    app.route(route="me/messages/{message_id}/move", methods=["POST"])(
        move_message_http)
    app.route(route="me/messages/{message_id}/copy", methods=["POST"])(
        copy_message_http)
    app.route(route="me/messages/{message_id}/reply", methods=["POST"])(
        reply_message_http)
    app.route(route="me/messages/{message_id}/replyAll", methods=["POST"])(
        reply_all_message_http)
    app.route(route="me/messages/{message_id}/forward", methods=["POST"])(
        forward_message_http)
    
    # Mail Folder Operations
    app.route(route="me/mailFolders", methods=["GET"])(
        list_mail_folders_http)
    app.route(route="me/mailFolders", methods=["POST"])(
        create_mail_folder_http)
    
    # Mail Attachments
    app.route(route="me/messages/{message_id}/attachments", methods=["GET"])(
        list_attachments_http)
    app.route(route="me/messages/{message_id}/attachments", methods=["POST"])(
        add_attachment_http)
    
    # === NEW COMPREHENSIVE CALENDAR ENDPOINTS ===
    
    # Calendar Operations
    app.route(route="me/calendars", methods=["GET"])(list_calendars_http)
    app.route(route="me/calendars", methods=["POST"])(create_calendar_http)
    app.route(route="me/calendar/calendarView", methods=["GET"])(
        get_calendar_view_http)
    
    # Event Operations
    app.route(route="me/events/{event_id}", methods=["GET"])(get_event_http)
    app.route(route="me/events/{event_id}", methods=["PATCH"])(
        update_event_http)
    app.route(route="me/events/{event_id}", methods=["DELETE"])(
        delete_event_http)
    
    # Event Actions
    app.route(route="me/events/{event_id}/accept", methods=["POST"])(
        accept_event_http)
    app.route(route="me/events/{event_id}/decline", methods=["POST"])(
        decline_event_http)
    app.route(route="me/findMeetingTimes", methods=["POST"])(
        find_meeting_times_http)
    
    # === NEW PLANNER TASK BOARD FORMAT ENDPOINTS ===
    
    # Task Board Formats
    app.route(
        route="planner/tasks/{task_id}/assignedToTaskBoardFormat", 
        methods=["GET"]
    )(get_assigned_to_task_board_format_http)
    app.route(
        route="planner/tasks/{task_id}/bucketTaskBoardFormat", 
        methods=["GET"]
    )(get_bucket_task_board_format_http)
    app.route(
        route="planner/tasks/{task_id}/progressTaskBoardFormat",
        methods=["GET"]
    )(get_progress_task_board_format_http)
    
    print("All 56 HTTP endpoints registered successfully!")
