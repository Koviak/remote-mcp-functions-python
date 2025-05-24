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
            json=data
        )
        
        if response.status_code == 200:
            return f"Task progress updated to {percent_complete}%"
        else:
            return f"Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        logging.error(f"Error updating task: {str(e)}")
        return f"Error updating task: {str(e)}"
