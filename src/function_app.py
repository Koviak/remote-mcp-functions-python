import json
import logging
import os
import requests
from azure.identity import ClientSecretCredential

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description

    def to_dict(self):
        return {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> str:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


# Microsoft Planner Tools

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


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_groups",
    description="List all Microsoft 365 groups in the organization",
    toolProperties="[]"
)
def list_groups(context) -> str:
    """List all Microsoft 365 groups in the organization"""
    try:
        token = get_access_token()
        if not token:
            return (
                "Authentication failed. "
                "Please check your Azure AD credentials."
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Get groups with teams/planner capabilities
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            "?$filter=groupTypes/any(c:c eq 'Unified')"
            "&$select=id,displayName,description,mail",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            groups = response.json()["value"]
            return json.dumps([{
                "id": g["id"],
                "displayName": g["displayName"],
                "description": g.get("description", ""),
                "mail": g.get("mail", "")
            } for g in groups])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing groups: {str(e)}")
        return f"Error listing groups: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_users",
    description="List all users in the organization with their IDs and names",
    toolProperties="[]"
)
def list_users(context) -> str:
    """List all users in the organization"""
    try:
        token = get_access_token()
        if not token:
            return (
                "Authentication failed. "
                "Please check your Azure AD credentials."
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Get all users with their basic information
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/users"
            "?$select=id,displayName,userPrincipalName,mail"
            "&$orderby=displayName",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            users = response.json()["value"]
            return json.dumps([{
                "id": u["id"],
                "displayName": u["displayName"],
                "userPrincipalName": u.get("userPrincipalName", ""),
                "mail": u.get("mail", "")
            } for u in users])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing users: {str(e)}")
        return f"Error listing users: {str(e)}"


# Define tool properties for Planner tools
tool_properties_list_plans_object = [
    ToolProperty("groupId", "string", "The ID of the Microsoft 365 group")
]
tool_properties_list_plans_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_list_plans_object]
)

tool_properties_create_plan_object = [
    ToolProperty("title", "string", "The title of the plan"),
    ToolProperty("groupId", "string", "The ID of the Microsoft 365 group")
]
tool_properties_create_plan_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_create_plan_object]
)

tool_properties_list_tasks_object = [
    ToolProperty("planId", "string", "The ID of the plan")
]
tool_properties_list_tasks_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_list_tasks_object]
)

tool_properties_create_task_object = [
    ToolProperty("planId", "string", "The ID of the plan"),
    ToolProperty("title", "string", "The title of the task"),
    ToolProperty("bucketId", "string", "The ID of the bucket (optional)")
]
tool_properties_create_task_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_create_task_object]
)

tool_properties_update_task_object = [
    ToolProperty("taskId", "string", "The ID of the task"),
    ToolProperty(
        "percentComplete", "integer", "The completion percentage (0-100)"
    )
]
tool_properties_update_task_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_update_task_object]
)


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_plans",
    description="List all Planner plans for a Microsoft 365 group",
    toolProperties=tool_properties_list_plans_json
)
def list_plans(context) -> str:
    """List all plans for a given Microsoft 365 group"""
    try:
        content = json.loads(context)
        group_id = content["arguments"]["groupId"]
        
        token = get_access_token()
        if not token:
            return (
                "Authentication failed. "
                "Please check your Azure AD credentials."
            )
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans",
            headers=headers
        )
        
        if response.status_code == 200:
            plans = response.json()["value"]
            return json.dumps(
                [{"id": p["id"], "title": p["title"]} for p in plans]
            )
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing plans: {str(e)}")
        return f"Error listing plans: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="create_plan",
    description="Create a new Planner plan",
    toolProperties=tool_properties_create_plan_json
)
def create_plan(context) -> str:
    """Create a new Planner plan"""
    try:
        content = json.loads(context)
        title = content["arguments"]["title"]
        group_id = content["arguments"]["groupId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            json=data
        )
        
        if response.status_code == 201:
            plan = response.json()
            return f"Plan created successfully. ID: {plan['id']}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error creating plan: {str(e)}")
        return f"Error creating plan: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_tasks",
    description="List all tasks in a Planner plan",
    toolProperties=tool_properties_list_tasks_json
)
def list_tasks(context) -> str:
    """List all tasks in a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/planner/plans/{plan_id}/tasks",
            headers=headers
        )
        
        if response.status_code == 200:
            tasks = response.json()["value"]
            return json.dumps([{
                "id": t["id"], 
                "title": t["title"],
                "percentComplete": t.get("percentComplete", 0)
            } for t in tasks])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing tasks: {str(e)}")
        return f"Error listing tasks: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="create_task",
    description="Create a new task in a Planner plan",
    toolProperties=tool_properties_create_task_json
)
def create_task(context) -> str:
    """Create a new task in a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        title = content["arguments"]["title"]
        bucket_id = content["arguments"].get("bucketId")
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            json=data
        )
        
        if response.status_code == 201:
            task = response.json()
            return f"Task created successfully. ID: {task['id']}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error creating task: {str(e)}")
        return f"Error creating task: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="update_task_progress",
    description="Update the progress percentage of a Planner task",
    toolProperties=tool_properties_update_task_json
)
def update_task_progress(context) -> str:
    """Update task progress"""
    try:
        content = json.loads(context)
        task_id = content["arguments"]["taskId"]
        percent_complete = content["arguments"]["percentComplete"]
        
        # Validate percentage
        if not 0 <= percent_complete <= 100:
            return "Error: percentComplete must be between 0 and 100"
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"  # Required for updates
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
            return f"Task progress updated to {percent_complete}%"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error updating task: {str(e)}")
        return f"Error updating task: {str(e)}"


# Additional Tool Properties for New Endpoints

# Plan management properties
tool_properties_get_plan_object = [
    ToolProperty("planId", "string", "The ID of the plan")
]
tool_properties_get_plan_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_get_plan_object]
)

tool_properties_update_plan_object = [
    ToolProperty("planId", "string", "The ID of the plan"),
    ToolProperty("title", "string", "The new title of the plan (optional)")
]
tool_properties_update_plan_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_update_plan_object]
)

tool_properties_delete_plan_object = [
    ToolProperty("planId", "string", "The ID of the plan to delete")
]
tool_properties_delete_plan_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_delete_plan_object]
)

# Task management properties
tool_properties_get_task_object = [
    ToolProperty("taskId", "string", "The ID of the task")
]
tool_properties_get_task_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_get_task_object]
)

tool_properties_update_task_full_object = [
    ToolProperty("taskId", "string", "The ID of the task"),
    ToolProperty("title", "string", "The title of the task (optional)"),
    ToolProperty(
        "percentComplete", "integer", 
        "The completion percentage 0-100 (optional)"
    ),
    ToolProperty("dueDateTime", "string", "The due date in ISO format (optional)"),
    ToolProperty("startDateTime", "string", "The start date in ISO format (optional)")
]
tool_properties_update_task_full_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_update_task_full_object]
)

tool_properties_delete_task_object = [
    ToolProperty("taskId", "string", "The ID of the task to delete")
]
tool_properties_delete_task_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_delete_task_object]
)

# User tasks properties
tool_properties_list_user_tasks_object = [
    ToolProperty("userId", "string", "The ID of the user (optional, defaults to current user)")
]
tool_properties_list_user_tasks_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_list_user_tasks_object]
)

# Bucket management properties
tool_properties_list_buckets_object = [
    ToolProperty("planId", "string", "The ID of the plan")
]
tool_properties_list_buckets_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_list_buckets_object]
)

tool_properties_create_bucket_object = [
    ToolProperty("planId", "string", "The ID of the plan"),
    ToolProperty("name", "string", "The name of the bucket")
]
tool_properties_create_bucket_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_create_bucket_object]
)

tool_properties_get_bucket_object = [
    ToolProperty("bucketId", "string", "The ID of the bucket")
]
tool_properties_get_bucket_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_get_bucket_object]
)

tool_properties_update_bucket_object = [
    ToolProperty("bucketId", "string", "The ID of the bucket"),
    ToolProperty("name", "string", "The new name of the bucket")
]
tool_properties_update_bucket_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_update_bucket_object]
)

tool_properties_delete_bucket_object = [
    ToolProperty("bucketId", "string", "The ID of the bucket to delete")
]
tool_properties_delete_bucket_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_delete_bucket_object]
)


# Additional Plan Management Tools

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_plan",
    description="Get a specific Planner plan by ID",
    toolProperties=tool_properties_get_plan_json
)
def get_plan(context) -> str:
    """Get a specific plan by ID"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            plan = response.json()
            return json.dumps({
                "id": plan["id"],
                "title": plan["title"],
                "owner": plan.get("owner"),
                "createdDateTime": plan.get("createdDateTime")
            })
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting plan: {str(e)}")
        return f"Error getting plan: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="update_plan",
    description="Update a Planner plan",
    toolProperties=tool_properties_update_plan_json
)
def update_plan(context) -> str:
    """Update a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        title = content["arguments"].get("title")
        
        if not title:
            return "Error: title is required for plan update"
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Plan updated successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error updating plan: {str(e)}")
        return f"Error updating plan: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="delete_plan",
    description="Delete a Planner plan",
    toolProperties=tool_properties_delete_plan_json
)
def delete_plan(context) -> str:
    """Delete a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Plan deleted successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error deleting plan: {str(e)}")
        return f"Error deleting plan: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_plan_details",
    description="Get detailed information about a Planner plan",
    toolProperties=tool_properties_get_plan_json
)
def get_plan_details(context) -> str:
    """Get plan details"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting plan details: {str(e)}")
        return f"Error getting plan details: {str(e)}"


# Additional Task Management Tools

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_task",
    description="Get a specific Planner task by ID",
    toolProperties=tool_properties_get_task_json
)
def get_task(context) -> str:
    """Get a specific task by ID"""
    try:
        content = json.loads(context)
        task_id = content["arguments"]["taskId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            task = response.json()
            return json.dumps({
                "id": task["id"],
                "title": task["title"],
                "percentComplete": task.get("percentComplete", 0),
                "planId": task.get("planId"),
                "bucketId": task.get("bucketId"),
                "dueDateTime": task.get("dueDateTime"),
                "startDateTime": task.get("startDateTime"),
                "assignments": task.get("assignments", {})
            })
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting task: {str(e)}")
        return f"Error getting task: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="update_task",
    description="Update a Planner task with full options",
    toolProperties=tool_properties_update_task_full_json
)
def update_task(context) -> str:
    """Update task with full options"""
    try:
        content = json.loads(context)
        task_id = content["arguments"]["taskId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": "*"
        }
        
        # Build update data from provided arguments
        data = {}
        if "title" in content["arguments"]:
            data["title"] = content["arguments"]["title"]
        if "percentComplete" in content["arguments"]:
            percent = content["arguments"]["percentComplete"]
            if not 0 <= percent <= 100:
                return "Error: percentComplete must be between 0 and 100"
            data["percentComplete"] = percent
        if "dueDateTime" in content["arguments"]:
            data["dueDateTime"] = content["arguments"]["dueDateTime"]
        if "startDateTime" in content["arguments"]:
            data["startDateTime"] = content["arguments"]["startDateTime"]
        
        if not data:
            return "Error: No update fields provided"
        
        response = requests.patch(
            f"{GRAPH_API_ENDPOINT}/planner/tasks/{task_id}",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return f"Task updated successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error updating task: {str(e)}")
        return f"Error updating task: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="delete_task",
    description="Delete a Planner task",
    toolProperties=tool_properties_delete_task_json
)
def delete_task(context) -> str:
    """Delete a task"""
    try:
        content = json.loads(context)
        task_id = content["arguments"]["taskId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Task deleted successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error deleting task: {str(e)}")
        return f"Error deleting task: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_task_details",
    description="Get detailed information about a Planner task",
    toolProperties=tool_properties_get_task_json
)
def get_task_details(context) -> str:
    """Get task details"""
    try:
        content = json.loads(context)
        task_id = content["arguments"]["taskId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting task details: {str(e)}")
        return f"Error getting task details: {str(e)}"


# User-Centric Task Tools

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_my_tasks",
    description="List all tasks assigned to the current user across all plans",
    toolProperties="[]"
)
def list_my_tasks(context) -> str:
    """List all my tasks across all plans"""
    try:
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            tasks = response.json()["value"]
            return json.dumps([{
                "id": t["id"],
                "title": t["title"],
                "percentComplete": t.get("percentComplete", 0),
                "planId": t.get("planId"),
                "bucketId": t.get("bucketId"),
                "dueDateTime": t.get("dueDateTime")
            } for t in tasks])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing my tasks: {str(e)}")
        return f"Error listing my tasks: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_user_tasks",
    description="List all tasks assigned to a specific user",
    toolProperties=tool_properties_list_user_tasks_json
)
def list_user_tasks(context) -> str:
    """List all tasks assigned to a specific user"""
    try:
        content = json.loads(context)
        user_id = content["arguments"].get("userId", "me")
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        endpoint = f"{GRAPH_API_ENDPOINT}/users/{user_id}/planner/tasks" if user_id != "me" else f"{GRAPH_API_ENDPOINT}/me/planner/tasks"
        
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            tasks = response.json()["value"]
            return json.dumps([{
                "id": t["id"],
                "title": t["title"],
                "percentComplete": t.get("percentComplete", 0),
                "planId": t.get("planId"),
                "bucketId": t.get("bucketId"),
                "dueDateTime": t.get("dueDateTime")
            } for t in tasks])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing user tasks: {str(e)}")
        return f"Error listing user tasks: {str(e)}"


# Bucket Management Tools

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_buckets",
    description="List all buckets in a Planner plan",
    toolProperties=tool_properties_list_buckets_json
)
def list_buckets(context) -> str:
    """List all buckets in a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            buckets = response.json()["value"]
            return json.dumps([{
                "id": b["id"],
                "name": b["name"],
                "planId": b.get("planId"),
                "orderHint": b.get("orderHint")
            } for b in buckets])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing buckets: {str(e)}")
        return f"Error listing buckets: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="create_bucket",
    description="Create a new bucket in a Planner plan",
    toolProperties=tool_properties_create_bucket_json
)
def create_bucket(context) -> str:
    """Create a new bucket in a plan"""
    try:
        content = json.loads(context)
        plan_id = content["arguments"]["planId"]
        name = content["arguments"]["name"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            bucket = response.json()
            return f"Bucket created successfully. ID: {bucket['id']}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error creating bucket: {str(e)}")
        return f"Error creating bucket: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_bucket",
    description="Get a specific bucket by ID",
    toolProperties=tool_properties_get_bucket_json
)
def get_bucket(context) -> str:
    """Get a specific bucket by ID"""
    try:
        content = json.loads(context)
        bucket_id = content["arguments"]["bucketId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            bucket = response.json()
            return json.dumps({
                "id": bucket["id"],
                "name": bucket["name"],
                "planId": bucket.get("planId"),
                "orderHint": bucket.get("orderHint")
            })
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting bucket: {str(e)}")
        return f"Error getting bucket: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="update_bucket",
    description="Update a bucket name",
    toolProperties=tool_properties_update_bucket_json
)
def update_bucket(context) -> str:
    """Update a bucket"""
    try:
        content = json.loads(context)
        bucket_id = content["arguments"]["bucketId"]
        name = content["arguments"]["name"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Bucket updated successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error updating bucket: {str(e)}")
        return f"Error updating bucket: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="delete_bucket",
    description="Delete a bucket",
    toolProperties=tool_properties_delete_bucket_json
)
def delete_bucket(context) -> str:
    """Delete a bucket"""
    try:
        content = json.loads(context)
        bucket_id = content["arguments"]["bucketId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Bucket deleted successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error deleting bucket: {str(e)}")
        return f"Error deleting bucket: {str(e)}"


# HTTP Endpoints - Direct API Access
# These provide the same functionality as MCP tools but via direct HTTP calls

@app.route(route="groups", methods=["GET"])
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


@app.route(route="users", methods=["GET"])
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
        
        # Get all users with their basic information
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


@app.route(route="plans", methods=["GET"])
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


@app.route(route="plans", methods=["POST"])
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


@app.route(route="tasks", methods=["GET"])
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


@app.route(route="tasks", methods=["POST"])
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


@app.route(route="tasks/{task_id}/progress", methods=["PATCH"])
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
        
        # Validate percentage
        if not isinstance(percent_complete, int) or not 0 <= percent_complete <= 100:
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
            "If-Match": "*"  # Required for updates
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


@app.route(route="hello", methods=["GET"])
def hello_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for connectivity test"""
    return func.HttpResponse(
        "Hello I am MCPTool! (HTTP endpoint)",
        status_code=200,
        mimetype="text/plain"
    )


# Additional HTTP Endpoints for New MCP Tools

# Plan Management HTTP Endpoints

@app.route(route="plans/{plan_id}", methods=["GET"])
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


@app.route(route="plans/{plan_id}", methods=["PATCH"])
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


@app.route(route="plans/{plan_id}", methods=["DELETE"])
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


@app.route(route="plans/{plan_id}/details", methods=["GET"])
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

@app.route(route="tasks/{task_id}", methods=["GET"])
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


@app.route(route="tasks/{task_id}", methods=["PATCH"])
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
        
        # Build update data from request body
        data = {}
        if "title" in req_body:
            data["title"] = req_body["title"]
        if "percentComplete" in req_body:
            percent = req_body["percentComplete"]
            if not isinstance(percent, int) or not 0 <= percent <= 100:
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


@app.route(route="tasks/{task_id}", methods=["DELETE"])
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


@app.route(route="tasks/{task_id}/details", methods=["GET"])
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

@app.route(route="me/tasks", methods=["GET"])
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


@app.route(route="users/{user_id}/tasks", methods=["GET"])
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
        
        endpoint = f"{GRAPH_API_ENDPOINT}/users/{user_id}/planner/tasks" if user_id != "me" else f"{GRAPH_API_ENDPOINT}/me/planner/tasks"
        
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

@app.route(route="plans/{plan_id}/buckets", methods=["GET"])
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


@app.route(route="buckets", methods=["POST"])
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


@app.route(route="buckets/{bucket_id}", methods=["GET"])
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


@app.route(route="buckets/{bucket_id}", methods=["PATCH"])
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


@app.route(route="buckets/{bucket_id}", methods=["DELETE"])
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
