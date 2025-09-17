import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

import azure.functions as func
import requests
from azure.identity import ClientSecretCredential

from graph_metadata_manager import GraphMetadataManager

# Global app instance - will be set by register_http_endpoints
app = None

# Microsoft Graph API endpoint
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

logger = logging.getLogger(__name__)

# Global metadata manager instance
metadata_manager = None

def get_metadata_manager():
    """Get or create the metadata manager instance"""
    global metadata_manager
    if metadata_manager is None:
        metadata_manager = GraphMetadataManager()
    return metadata_manager


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


def _get_agent_user_id() -> str:
    """Return the configured agent user id if available, else empty string."""
    return os.environ.get("AGENT_USER_ID", "").strip()


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
            # Validate bucketId belongs to plan
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
                # else: ignore invalid bucket
            except Exception:
                pass
        
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
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
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
        from agent_auth_manager import get_agent_token
        token = get_agent_token()
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
        
        from agent_auth_manager import get_agent_token
        token = get_agent_token()
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
        
        # Prefer delegated token for /me; fallback to app-only with /users/{id}
        token, base = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token()
            if delegated:
                token, base = delegated, "/me"
        except Exception:
            token, base = (None, None)
        if not token:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, base = app_token, f"/users/{user_id}"
        if not token or not base:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"{GRAPH_API_ENDPOINT}{base}/calendar/calendarView"
        response = requests.get(
            url,
            params={
                "startDateTime": start_date,
                "endDateTime": end_date,
            },
            headers=headers,
            timeout=10,
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
        
        from agent_auth_manager import get_agent_token
        token = get_agent_token("openid profile offline_access User.Read Mail.Read")
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
    app.route(route="me/chats", methods=["GET"])(list_chats_http)
    app.route(route="me/chats/messages", methods=["POST"])(
        post_chat_message_http)
    
    # Files & Sites
    app.route(route="me/drives", methods=["GET"])(list_drives_http)
    app.route(route="me/drive/root/children", methods=["GET"])(
        list_root_items_http)
    app.route(route="drives/{drive_id}/items/{item_id}/content", 
              methods=["GET"])(download_file_http)
    app.route(route="sites", methods=["GET"])(sites_search_http)
    # SharePoint: support compound siteId and listing drives by site
    app.route(route="sites/{site_id}/drives", methods=["GET"])(list_site_drives_http)
    
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
    
    # === NEW WEBHOOK AND AGENT ENDPOINTS ===
    
    # Webhook endpoint
    app.route(
        route="graph_webhook",
        methods=["POST", "GET"],
        auth_level=func.AuthLevel.ANONYMOUS
    )(graph_webhook_http)
    
    # Agent endpoints
    app.route(
        route="metadata",
        methods=["GET"],
        auth_level=func.AuthLevel.FUNCTION
    )(get_metadata_http)
    
    app.route(
        route="agent/tasks",
        methods=["POST"],
        auth_level=func.AuthLevel.FUNCTION
    )(create_agent_task_http)
    
    # Planner sync endpoints
    app.route(
        route="planner/poll",
        methods=["POST"],
        auth_level=func.AuthLevel.FUNCTION
    )(trigger_planner_poll_http)
    
    print("All 73 HTTP endpoints registered successfully!")


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
        # Use delegated token for /me endpoints
        from agent_auth_manager import get_agent_token
        token = get_agent_token("openid profile offline_access User.Read Tasks.Read")
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
        
        # Try to get from cache first
        manager = get_metadata_manager()
        
        # Run async code in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            cached_data = loop.run_until_complete(
                manager.get_cached_metadata("user", user_id)
            )
            
            if cached_data:
                return func.HttpResponse(
                    json.dumps(cached_data),
                    status_code=200,
                    mimetype="application/json"
                )
        finally:
            loop.close()
        
        # If not cached or cache miss, fetch from API
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
            user_data = response.json()
            
            # Cache the result
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    manager.cache_user_metadata(user_id)
                )
            finally:
                loop.close()
            
            return func.HttpResponse(
                json.dumps(user_data),
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
            f"{GRAPH_API_ENDPOINT}/directory/deletedItems/"
            "microsoft.graph.user",
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
        
        # Prefer delegated token for /me sendMail; fallback to app-only with /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token()
            if delegated:
                token, path = delegated, "/me/sendMail"
        except Exception:
            token, path = (None, None)

        if not token:
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
            f"{GRAPH_API_ENDPOINT}{path}",
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
        # Prefer delegated /me; fallback to app-only /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token("openid profile offline_access User.Read Mail.Read")
            if delegated:
                token, path = delegated, "/me/mailFolders/inbox/messages"
        except Exception:
            token, path = (None, None)

        if not token:
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

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
            params={
                "$select": "id,subject,from,receivedDateTime,isRead",
                "$top": "20",
                "$orderby": "receivedDateTime desc",
            },
            headers=headers,
            timeout=10,
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
        from agent_auth_manager import get_agent_token
        token = get_agent_token("openid profile offline_access User.Read")
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
                json.dumps({
                    "id": event["id"], 
                    "message": "Event created successfully"
                }),
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
        # Use delegated token for /me endpoints; if unavailable, surface 503 so tests skip
        from agent_auth_manager import get_agent_token
        token = get_agent_token()
        if not token:
            return func.HttpResponse(
                json.dumps({"status": "unavailable", "reason": "delegated token missing"}),
                status_code=503,
                mimetype="application/json"
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
            f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels/"
            f"{channel_id}/messages",
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


def list_chats_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list Teams chats."""
    try:
        # Prefer delegated /me; fallback to app-only /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token()
            if delegated:
                token, path = delegated, "/me/chats"
        except Exception:
            token, path = (None, None)

        if not token:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/chats"

        if not token or not path:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
            headers=headers,
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

    except Exception as e:  # pragma: no cover - network errors
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500,
        )


def post_chat_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to post message to a Teams chat."""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400,
            )

        chat_id = req_body.get("chatId")
        message = req_body.get("message")
        reply_to = req_body.get("replyToId")

        if not all([chat_id, message]):
            return func.HttpResponse(
                "Missing required fields: chatId, message",
                status_code=400,
            )

        # Prefer delegated token for posting; app-only may lack permissions
        token = None
        try:
            from agent_auth_manager import get_agent_token
            token = get_agent_token()
        except Exception:
            token = None
        if not token:
            return func.HttpResponse(
                json.dumps({
                    "error": "delegated_required",
                    "message": "Posting chat messages requires delegated token",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        data = {"body": {"content": message}}

        if reply_to:
            url = (
                f"{GRAPH_API_ENDPOINT}/chats/{chat_id}/messages/"
                f"{reply_to}/replies"
            )
        else:
            url = f"{GRAPH_API_ENDPOINT}/chats/{chat_id}/messages"

        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code in (200, 201):
            return func.HttpResponse(
                f"Message posted successfully to chat {chat_id}",
                status_code=201,
            )
        return func.HttpResponse(
            f"Error: {response.status_code} - {response.text}",
            status_code=response.status_code,
        )

    except Exception as e:  # pragma: no cover - network errors
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500,
        )


def list_drives_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list drives"""
    try:
        # Prefer delegated /me; fallback to app-only /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token("openid profile offline_access User.Read Files.ReadWrite.All")
            if delegated:
                token, path = delegated, "/me/drives"
        except Exception:
            token, path = (None, None)

        if not token:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/drives"

        if not token or not path:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
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
    """HTTP endpoint to list root items in my drive"""
    try:
        # Prefer delegated /me; fallback to app-only /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token("openid profile offline_access User.Read Files.ReadWrite.All")
            if delegated:
                token, path = delegated, "/me/drive/root/children"
        except Exception:
            token, path = (None, None)

        if not token:
            app_token = get_access_token()
            user_id = _get_agent_user_id()
            if app_token and user_id:
                token, path = app_token, f"/users/{user_id}/drive/root/children"

        if not token or not path:
            return func.HttpResponse(
                json.dumps({
                    "error": "auth_unavailable",
                    "message": "Delegated token missing and app-only fallback not configured",
                }),
                status_code=503,
                mimetype="application/json",
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
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


def list_site_drives_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list drives for a SharePoint site.

    Accepts compound site IDs (e.g., `{hostname},{siteId},{webId}`) via route param
    or `siteId` query param. Falls back to search by `hostname`+`path` if provided.
    """
    try:
        site_id = req.route_params.get('site_id') or req.params.get('siteId')
        hostname = req.params.get('hostname')
        site_path = req.params.get('path')

        if not site_id and not (hostname and site_path):
            return func.HttpResponse(
                "Missing site_id or (hostname and path) parameters",
                status_code=400,
            )

        token = get_access_token()
        if not token:
            return func.HttpResponse(
                "Authentication failed. Check Azure AD credentials.",
                status_code=401,
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        if not site_id:
            # Build id from hostname and path
            # GET /sites/{hostname}:/sites/{path}
            lookup = requests.get(
                f"{GRAPH_API_ENDPOINT}/sites/{hostname}:/sites/{site_path}",
                headers=headers,
                timeout=10,
            )
            if lookup.status_code != 200:
                return func.HttpResponse(
                    f"Error: {lookup.status_code} - {lookup.text}",
                    status_code=lookup.status_code,
                )
            site_id = lookup.json().get("id")
            if not site_id:
                return func.HttpResponse("Site not found", status_code=404)

        # Now list drives
        resp = requests.get(
            f"{GRAPH_API_ENDPOINT}/sites/{site_id}/drives",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            return func.HttpResponse(
                resp.text, status_code=200, mimetype="application/json"
            )
        return func.HttpResponse(
            f"Error: {resp.status_code} - {resp.text}",
            status_code=resp.status_code,
        )

    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)


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
            f"{GRAPH_API_ENDPOINT}/reports/"
            "getOffice365ActiveUserCounts(period='D7')",
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


# MISSING MAIL MESSAGE OPERATIONS

def move_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to move a message to another folder"""
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
        
        destination_id = req_body.get('destinationId')
        if not destination_id:
            return func.HttpResponse(
                "Missing required field: destinationId",
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
        
        data = {"destinationId": destination_id}
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/move",
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


def copy_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to copy a message to another folder"""
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
        
        destination_id = req_body.get('destinationId')
        if not destination_id:
            return func.HttpResponse(
                "Missing required field: destinationId",
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
        
        data = {"destinationId": destination_id}
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/copy",
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


def reply_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to reply to a message"""
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
        
        comment = req_body.get('comment', '')
        
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
        
        data = {"comment": comment}
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/reply",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Reply sent successfully",
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


def reply_all_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to reply all to a message"""
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
        
        comment = req_body.get('comment', '')
        
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
        
        data = {"comment": comment}
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/replyAll",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Reply all sent successfully",
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


def forward_message_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to forward a message"""
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
        
        to_recipients = req_body.get('toRecipients', [])
        comment = req_body.get('comment', '')
        
        if not to_recipients:
            return func.HttpResponse(
                "Missing required field: toRecipients",
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
            "comment": comment,
            "toRecipients": [
                {"emailAddress": {"address": email}} 
                for email in to_recipients
            ]
        }
        
        response = requests.post(
            f"{GRAPH_API_ENDPOINT}/me/messages/{message_id}/forward",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 202:
            return func.HttpResponse(
                "Message forwarded successfully",
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


def graph_webhook_http(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Microsoft Graph webhook notifications"""
    # Ensure capped logging is initialized for this entrypoint
    try:
        from logging_setup import setup_logging
        setup_logging(add_console=True)
    except Exception:
        pass
    
    # Handle subscription validation
    validation_token = req.params.get('validationToken')
    if validation_token:
        logger.info("Graph webhook validation request received")
        return func.HttpResponse(
            validation_token,
            status_code=200,
            mimetype="text/plain"
        )
    
    # Process notifications
    try:
        body = req.get_json()
        
        # Validate notifications
        notifications = body.get("value", [])
        
        # Import and use our new webhook handler
        import asyncio

        from webhook_handler import handle_graph_webhook
        
        # Process each notification through our V5 handler
        for notification in notifications:
            try:
                # Run the async webhook handler
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(handle_graph_webhook(notification))
                    if success:
                        logger.info(f"Successfully processed webhook notification: {notification.get('changeType')} for {notification.get('resource')}")
                    else:
                        logger.warning(f"Failed to process webhook notification: {notification}")
                finally:
                    loop.close()
                    
            except Exception as e:
                logger.error(f"Error processing individual notification: {e}")
                # Continue processing other notifications
        
        return func.HttpResponse("OK", status_code=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)


def process_graph_notification(notification: Dict[str, Any], redis_manager):
    """Process individual Graph notification"""
    resource = notification.get("resource")
    change_type = notification.get("changeType")
    resource_data = notification.get("resourceData", {})
    
    logger.info(f"Processing {change_type} notification for {resource}")
    
    # Publish to Redis for agents
    redis_client = redis_manager._client
    
    notification_data = {
        "type": "graph_notification",
        "resource": resource,
        "changeType": change_type,
        "resourceData": resource_data,
        "subscriptionId": notification.get("subscriptionId"),
        "timestamp": notification.get("subscriptionExpirationDateTime")
    }
    
    # Determine the channel based on resource type
    agent_user_id = os.environ.get('AGENT_USER_ID', '')
    if "/me/" in resource or f"/users/{agent_user_id}/" in resource:
        # This is for Annika's user
        channel = "annika:notifications:user"
    elif "/groups/" in resource:
        channel = "annika:notifications:groups"
    elif "/planner/" in resource:
        channel = "annika:notifications:planner"
    else:
        channel = "annika:notifications:general"
    
    redis_client.publish(channel, json.dumps(notification_data))
    
    # Update cache based on resource type
    manager = get_metadata_manager()
    
    # Cache updates for different resource types
    if "/users/" in resource:
        user_id = resource.split("/users/")[1].split("/")[0]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.cache_user_metadata(user_id))
        finally:
            loop.close()
            
    elif "/groups/" in resource:
        group_id = resource.split("/groups/")[1].split("/")[0]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.cache_group_metadata(group_id))
        finally:
            loop.close()
    
    # For planner tasks, also sync to task cache
    if "/planner/tasks" in resource and change_type in ["created", "updated"]:
        sync_planner_task(resource, resource_data, redis_manager)
        # Also cache task metadata
        task_id = resource_data.get("id")
        if task_id:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.cache_task_metadata(task_id))
            finally:
                loop.close()


def sync_planner_task(resource: str, resource_data: Dict, redis_manager):
    """Sync Planner task to Redis cache"""
    task_id = resource_data.get("id")
    if not task_id:
        return
    
    # Get full task details using delegated token
    from agent_auth_manager import get_agent_token
    token = get_agent_token()
    
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            task = response.json()
            # Store in Redis
            redis_client = redis_manager._client
            redis_client.setex(
                f"annika:planner:tasks:{task_id}",
                3600,
                json.dumps(task)
            )
            
            # Publish standardized task update
            redis_client.publish(
                "annika:tasks:updates",
                json.dumps({
                    "action": "updated",
                    "task_id": task_id,
                    "task": task,
                    "source": "webhook"
                })
            )


def get_metadata_http(req: func.HttpRequest) -> func.HttpResponse:
    """Get cached metadata for users, groups, or plans"""
    try:
        resource_type = req.params.get('type')  # user, group, plan
        resource_id = req.params.get('id')
        
        if not resource_type or not resource_id:
            return func.HttpResponse(
                "Missing required parameters: type and id",
                status_code=400
            )
        
        from mcp_redis_config import get_redis_token_manager
        redis_manager = get_redis_token_manager()
        redis_client = redis_manager._client
        
        # Build key based on resource type
        key_patterns = {
            "user": f"annika:graph:users:{resource_id}",
            "group": f"annika:graph:groups:{resource_id}",
            "plan": f"annika:graph:plans:{resource_id}",
            "task": f"annika:graph:tasks:{resource_id}"
        }
        
        if resource_type not in key_patterns:
            return func.HttpResponse(
                f"Invalid resource type: {resource_type}",
                status_code=400
            )
        
        key = key_patterns[resource_type]
        data = redis_client.get(key)
        
        if data:
            return func.HttpResponse(
                data,
                status_code=200,
                mimetype="application/json"
            )
        else:
            return func.HttpResponse(
                json.dumps({
                    "error": "Resource not found in cache",
                    "type": resource_type,
                    "id": resource_id
                }),
                status_code=404,
                mimetype="application/json"
            )
        
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def create_agent_task_http(req: func.HttpRequest) -> func.HttpResponse:
    """Create a task from an agent (will sync to Planner)"""
    try:
        req_body = req.get_json()
        if not req_body:
            return func.HttpResponse(
                "Request body required",
                status_code=400
            )
        
        # Required fields
        title = req_body.get('title')
        plan_id = req_body.get('planId')
        
        if not title or not plan_id:
            return func.HttpResponse(
                "Missing required fields: title and planId",
                status_code=400
            )
        
        # Create task object
        task = {
            "id": f"agent-task-{datetime.utcnow().timestamp()}",
            "title": title,
            "planId": plan_id,
            "bucketId": req_body.get('bucketId'),
            "assignedTo": req_body.get('assignedTo', []),
            "dueDate": req_body.get('dueDate'),
            "percentComplete": req_body.get('percentComplete', 0),
            "createdBy": "agent",
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }
        
        # Store task in Redis (primary storage)
        from mcp_redis_config import get_redis_token_manager
        redis_manager = get_redis_token_manager()
        redis_client = redis_manager._client
        
        # Store task in Redis (no expiry)
        redis_client.set(
            f"annika:tasks:{task['id']}",
            json.dumps(task)
        )
        
        # Also publish notification
        redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "created",
                "task_id": task.get("id"),
                "task": task,
                "source": "agent"
            })
        )
        
        return func.HttpResponse(
            json.dumps({
                "status": "created",
                "task": task,
                "message": "Task will sync to Planner immediately"
            }),
            status_code=201,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


def list_mail_folders_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to list mail folders"""
    try:
        # Prefer delegated /me; fallback to app-only /users/{id}
        token, path = (None, None)
        try:
            from agent_auth_manager import get_agent_token
            delegated = get_agent_token()
            if delegated:
                token, path = delegated, "/me/mailFolders"
        except Exception:
            token, path = (None, None)

        if not token:
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

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            f"{GRAPH_API_ENDPOINT}{path}",
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


def trigger_planner_poll_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to trigger immediate Planner polling"""
    try:
        # Import the sync service
        import asyncio

        from planner_sync_service_v5 import WebhookDrivenPlannerSync
        
        # Create a temporary sync service instance to trigger polling
        async def run_poll():
            sync_service = WebhookDrivenPlannerSync()
            
            # Initialize Redis connection
            import redis.asyncio as redis
            sync_service.redis_client = redis.Redis(
                host="localhost",
                port=6379,
                password="password",
                decode_responses=True
            )
            await sync_service.redis_client.ping()
            
            # Initialize adapter
            from annika_task_adapter import AnnikaTaskAdapter
            sync_service.adapter = AnnikaTaskAdapter(
                sync_service.redis_client
            )
            
            try:
                # Trigger the poll
                await sync_service._poll_all_planner_tasks()
                return {
                    "status": "success", 
                    "message": "Planner poll completed"
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                if sync_service.redis_client:
                    await sync_service.redis_client.close()
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_poll())
        finally:
            loop.close()
        
        status_code = 200 if result.get("status") == "success" else 500
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=status_code,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )



