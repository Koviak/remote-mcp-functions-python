import json
import logging
import os
import requests
from azure.identity import ClientSecretCredential

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class ToolProperty:
    def __init__(self, property_name: str, property_type: str,
                 description: str):
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
            "&$select=id,displayName,description,mail,hasPlanner",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            groups = response.json()["value"]
            return json.dumps([{
                "id": g["id"],
                "displayName": g["displayName"],
                "description": g.get("description", ""),
                "mail": g.get("mail", ""),
                "hasPlanner": g.get("hasPlanner", False)
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


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_groups_with_planner",
    description=(
        "List only Microsoft 365 groups that have at least one Planner plan"
    ),
    toolProperties="[]"
)
def list_groups_with_planner(context) -> str:
    """List only groups that have Planner plans"""
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
        
        # Get only groups that have Planner plans
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
                "mail": g.get("mail", ""),
                "hasPlanner": g.get("hasPlanner", False)
            } for g in groups])
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing groups with planner: {str(e)}")
        return f"Error listing groups with planner: {str(e)}"


tool_properties_check_group_planner_object = [
    ToolProperty(
        "groupDisplayName", "string", "The display name of the group to check"
    )
]
tool_properties_check_group_planner_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_check_group_planner_object]
)


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="check_group_planner_status",
    description="Check if a specific group has Planner enabled and list its plans",
    toolProperties=tool_properties_check_group_planner_json
)
def check_group_planner_status(context) -> str:
    """Check if a group has Planner and list its plans"""
    try:
        content = json.loads(context)
        group_name = content["arguments"]["groupDisplayName"]
        
        token = get_access_token()
        if not token:
            return ("Authentication failed. "
                   "Please check your Azure AD credentials.")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Find the group by display name
        response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups"
            f"?$filter=displayName eq '{group_name}'"
            "&$select=id,displayName,hasPlanner",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return f"Error finding group: {response.status_code} - {response.text}"
        
        groups = response.json()["value"]
        if not groups:
            return f"No group found with display name: {group_name}"
        
        group = groups[0]
        result = {
            "groupId": group["id"],
            "displayName": group["displayName"],
            "hasPlanner": group.get("hasPlanner", False)
        }
        
        # Try to get plans for this group
        plans_response = requests.get(
            f"{GRAPH_API_ENDPOINT}/groups/{group['id']}/planner/plans",
            headers=headers,
            timeout=10
        )
        
        if plans_response.status_code == 200:
            plans = plans_response.json()["value"]
            result["plans"] = [{"id": p["id"], "title": p["title"]} for p in plans]
            result["planCount"] = len(plans)
        else:
            result["plansError"] = (
                f"{plans_response.status_code} - {plans_response.text}"
            )
        
        return json.dumps(result)
        
    except Exception as e:
        logging.error(f"Error checking group planner status: {str(e)}")
        return f"Error checking group planner status: {str(e)}"


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
            headers=headers,
            timeout=10
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
            json=data,
            timeout=10
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
            headers=headers,
            timeout=10
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
            json=data,
            timeout=10
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


# Register HTTP endpoints from separate module
from http_endpoints import register_http_endpoints

# Additional User & Group Management Tools

# Tool properties for new endpoints
tool_properties_get_user_object = [
    ToolProperty("userId", "string", "Azure AD user ID")
]
tool_properties_get_user_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_get_user_object]
)

tool_properties_list_group_members_object = [
    ToolProperty("groupId", "string", "The ID of the group")
]
tool_properties_list_group_members_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_list_group_members_object]
)

tool_properties_add_user_to_group_object = [
    ToolProperty("groupId", "string", "The ID of the group"),
    ToolProperty("userId", "string", "The ID of the user to add")
]
tool_properties_add_user_to_group_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_add_user_to_group_object]
)

tool_properties_reset_password_object = [
    ToolProperty("userId", "string", "The ID of the user"),
    ToolProperty("temporaryPassword", "string", "The temporary password to set")
]
tool_properties_reset_password_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_reset_password_object]
)

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_user",
    description="Get full profile for a user by ID",
    toolProperties=tool_properties_get_user_json
)
def get_user(context) -> str:
    """Get a specific user by ID"""
    try:
        content = json.loads(context)
        user_id = content["arguments"]["userId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error getting user: {str(e)}")
        return f"Error getting user: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_deleted_users",
    description="List all deleted users in the organization",
    toolProperties="[]"
)
def list_deleted_users(context) -> str:
    """List all deleted users"""
    try:
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing deleted users: {str(e)}")
        return f"Error listing deleted users: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_group_members",
    description="List all members of a specific group",
    toolProperties=tool_properties_list_group_members_json
)
def list_group_members(context) -> str:
    """List all members of a group"""
    try:
        content = json.loads(context)
        group_id = content["arguments"]["groupId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing group members: {str(e)}")
        return f"Error listing group members: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="add_user_to_group",
    description="Add a user to a group",
    toolProperties=tool_properties_add_user_to_group_json
)
def add_user_to_group(context) -> str:
    """Add a user to a group"""
    try:
        content = json.loads(context)
        group_id = content["arguments"]["groupId"]
        user_id = content["arguments"]["userId"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"User {user_id} added to group {group_id} successfully"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error adding user to group: {str(e)}")
        return f"Error adding user to group: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="reset_password",
    description="Reset a user's password",
    toolProperties=tool_properties_reset_password_json
)
def reset_password(context) -> str:
    """Reset a user's password"""
    try:
        content = json.loads(context)
        user_id = content["arguments"]["userId"]
        temp_password = content["arguments"]["temporaryPassword"]
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Password reset successfully for user {user_id}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error resetting password: {str(e)}")
        return f"Error resetting password: {str(e)}"


# Mail & Calendar Tools

tool_properties_send_message_object = [
    ToolProperty("to", "string", "Recipient email address"),
    ToolProperty("subject", "string", "Email subject"),
    ToolProperty("body", "string", "Email body content"),
    ToolProperty("bodyType", "string", "Body type: 'text' or 'html' (optional, defaults to 'text')")
]
tool_properties_send_message_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_send_message_object]
)

tool_properties_create_event_object = [
    ToolProperty("subject", "string", "Event subject"),
    ToolProperty("start", "string", "Start time in ISO format"),
    ToolProperty("end", "string", "End time in ISO format"),
    ToolProperty("attendees", "string", "Comma-separated list of attendee emails (optional)")
]
tool_properties_create_event_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_create_event_object]
)

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="send_message",
    description="Send an email message",
    toolProperties=tool_properties_send_message_json
)
def send_message(context) -> str:
    """Send an email message"""
    try:
        content = json.loads(context)
        to_email = content["arguments"]["to"]
        subject = content["arguments"]["subject"]
        body = content["arguments"]["body"]
        body_type = content["arguments"].get("bodyType", "text")
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Email sent successfully to {to_email}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error sending message: {str(e)}")
        return f"Error sending message: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_inbox",
    description="List messages in the user's inbox",
    toolProperties="[]"
)
def list_inbox(context) -> str:
    """List inbox messages"""
    try:
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing inbox: {str(e)}")
        return f"Error listing inbox: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="create_event",
    description="Create a calendar event",
    toolProperties=tool_properties_create_event_json
)
def create_event(context) -> str:
    """Create a calendar event"""
    try:
        content = json.loads(context)
        subject = content["arguments"]["subject"]
        start_time = content["arguments"]["start"]
        end_time = content["arguments"]["end"]
        attendees_str = content["arguments"].get("attendees", "")
        
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return f"Event created successfully. ID: {event['id']}"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error creating event: {str(e)}")
        return f"Error creating event: {str(e)}"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="list_upcoming",
    description="List upcoming calendar events",
    toolProperties="[]"
)
def list_upcoming(context) -> str:
    """List upcoming calendar events"""
    try:
        token = get_access_token()
        if not token:
            return "Authentication failed. Please check your Azure AD credentials."
        
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
            return response.text
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error listing upcoming events: {str(e)}")
        return f"Error listing upcoming events: {str(e)}"


register_http_endpoints(app)

# Register additional tools
from additional_tools import register_additional_tools
register_additional_tools(app)
