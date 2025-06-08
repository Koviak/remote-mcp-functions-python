"""
MCP Tools with Delegated Access for Autonomous Agents

This module provides MCP tools that use delegated permissions through
the agent authentication manager, enabling autonomous agents to perform
operations in their user context.
"""

import json
import logging

import requests

from agent_auth_manager import get_agent_token

# Microsoft Graph API endpoint
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


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


def get_delegated_access_token():
    """
    Get access token with delegated permissions for the agent
    
    This uses the agent auth manager to obtain user tokens,
    enabling delegated access for MCP tools.
    """
    # Get token from agent auth manager
    token = get_agent_token("https://graph.microsoft.com/.default")
    
    if not token:
        # Fall back to trying with specific delegated scopes
        token = get_agent_token("User.Read Mail.Send Files.ReadWrite.All")
    
    return token


def register_delegated_tools(app):
    """Register MCP tools that use delegated permissions"""
    
    # Personal Productivity Tools (Delegated Access)
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="get_my_profile",
        description="Get the agent's user profile",
        toolProperties="[]"
    )
    def get_my_profile(context) -> str:
        """Get agent's profile using delegated permissions"""
        try:
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error getting profile: {str(e)}")
            return f"Error getting profile: {str(e)}"
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_my_files",
        description="List files in the agent's OneDrive",
        toolProperties="[]"
    )
    def list_my_files(context) -> str:
        """List agent's files using delegated permissions"""
        try:
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/drive/root/children",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing files: {str(e)}")
            return f"Error listing files: {str(e)}"
    
    tool_properties_send_email_object = [
        ToolProperty("to", "string", "Recipient email address"),
        ToolProperty("subject", "string", "Email subject"),
        ToolProperty("body", "string", "Email body content"),
        ToolProperty("isHtml", "boolean", "Whether body is HTML (optional)")
    ]
    tool_properties_send_email_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_send_email_object]
    )
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="send_email_as_agent",
        description="Send email as the agent user",
        toolProperties=tool_properties_send_email_json
    )
    def send_email_as_agent(context) -> str:
        """Send email using agent's delegated permissions"""
        try:
            content = json.loads(context)
            to_email = content["arguments"]["to"]
            subject = content["arguments"]["subject"]
            body = content["arguments"]["body"]
            is_html = content["arguments"].get("isHtml", False)
            
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML" if is_html else "Text",
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
            logging.error(f"Error sending email: {str(e)}")
            return f"Error sending email: {str(e)}"
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_my_calendar",
        description="List agent's calendar events",
        toolProperties="[]"
    )
    def list_my_calendar(context) -> str:
        """List agent's calendar using delegated permissions"""
        try:
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Get next 7 days of events
            from datetime import datetime, timedelta
            start_time = datetime.utcnow().isoformat() + "Z"
            end_time = (
                datetime.utcnow() + timedelta(days=7)
            ).isoformat() + "Z"
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/calendarview"
                f"?startDateTime={start_time}&endDateTime={end_time}"
                "&$select=subject,start,end,location,attendees"
                "&$orderby=start/dateTime",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing calendar: {str(e)}")
            return f"Error listing calendar: {str(e)}"
    
    tool_properties_create_task_object = [
        ToolProperty("title", "string", "Task title"),
        ToolProperty("dueDate", "string", "Due date (YYYY-MM-DD) (optional)"),
        ToolProperty("importance", "string", "low/normal/high (optional)"),
        ToolProperty("body", "string", "Task body content (optional)")
    ]
    tool_properties_create_task_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_create_task_object]
    )
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="create_todo_task",
        description="Create a task in agent's To Do",
        toolProperties=tool_properties_create_task_json
    )
    def create_todo_task(context) -> str:
        """Create task using delegated permissions"""
        try:
            content = json.loads(context)
            title = content["arguments"]["title"]
            due_date = content["arguments"].get("dueDate")
            importance = content["arguments"].get("importance", "normal")
            body_content = content["arguments"].get("body", "")
            
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # First, get the default task list
            lists_response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/todo/lists",
                headers=headers,
                timeout=10
            )
            
            if lists_response.status_code != 200:
                return f"Error getting task lists: {lists_response.text}"
            
            lists = lists_response.json()["value"]
            default_list = next(
                (lst for lst in lists if lst.get("isDefault")), 
                lists[0] if lists else None)
            
            if not default_list:
                return "No task lists found"
            
            # Create the task
            data = {
                "title": title,
                "importance": importance
            }
            
            if body_content:
                data["body"] = {
                    "content": body_content,
                    "contentType": "text"
                }
            
            if due_date:
                data["dueDateTime"] = {
                    "dateTime": f"{due_date}T00:00:00Z",
                    "timeZone": "UTC"
                }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/me/todo/lists/"
                f"{default_list['id']}/tasks",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 201:
                return f"Task '{title}' created successfully"
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error creating task: {str(e)}")
            return f"Error creating task: {str(e)}"
    
    # Teams Collaboration Tools (Delegated)
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_my_teams",
        description="List teams the agent is a member of",
        toolProperties="[]"
    )
    def list_my_teams(context) -> str:
        """List agent's teams using delegated permissions"""
        try:
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/joinedTeams",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing teams: {str(e)}")
            return f"Error listing teams: {str(e)}"
    
    tool_properties_post_message_object = [
        ToolProperty("teamId", "string", "The ID of the team"),
        ToolProperty("channelId", "string", "The ID of the channel"),
        ToolProperty("message", "string", "The message content"),
        ToolProperty("isImportant", "boolean", "Mark as important (optional)")
    ]
    tool_properties_post_message_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_post_message_object]
    )
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="post_teams_message_as_agent",
        description="Post a message to Teams channel as the agent",
        toolProperties=tool_properties_post_message_json
    )
    def post_teams_message_as_agent(context) -> str:
        """Post Teams message using agent's delegated permissions"""
        try:
            content = json.loads(context)
            team_id = content["arguments"]["teamId"]
            channel_id = content["arguments"]["channelId"]
            message = content["arguments"]["message"]
            is_important = content["arguments"].get("isImportant", False)
            
            token = get_delegated_access_token()
            if not token:
                return ("Authentication failed. "
                        "Agent credentials not configured.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "body": {
                    "content": message
                },
                "importance": "high" if is_important else "normal"
            }
            
            response = requests.post(
                f"{GRAPH_API_ENDPOINT}/teams/{team_id}/channels/"
                f"{channel_id}/messages",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 201:
                return "Message posted successfully as agent"
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error posting message: {str(e)}")
            return f"Error posting message: {str(e)}"

    tool_properties_list_chats_json = "[]"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_my_chats",
        description="List chats the agent is part of",
        toolProperties=tool_properties_list_chats_json,
    )
    def list_my_chats(context) -> str:
        """List chats using delegated permissions."""
        try:
            token = get_delegated_access_token()
            if not token:
                return (
                    "Authentication failed. "
                    "Agent credentials not configured."
                )

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/me/chats",
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                return response.text
            return f"Error: {response.status_code} - {response.text}"

        except Exception as e:  # pragma: no cover - network errors
            logging.error(f"Error listing chats: {str(e)}")
            return f"Error listing chats: {str(e)}"

    tool_properties_post_chat_obj = [
        ToolProperty("chatId", "string", "The ID of the chat"),
        ToolProperty("message", "string", "The message content"),
        ToolProperty(
            "replyToId",
            "string",
            "ID of the message to reply to (optional)",
        ),
    ]
    tool_properties_post_chat_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_post_chat_obj]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="post_chat_message_as_agent",
        description="Post a message to Teams chat as the agent",
        toolProperties=tool_properties_post_chat_json,
    )
    def post_chat_message_as_agent(context) -> str:
        """Post Teams chat message using delegated permissions."""
        try:
            content = json.loads(context)
            chat_id = content["arguments"]["chatId"]
            message = content["arguments"]["message"]
            reply_to = content["arguments"].get("replyToId")

            token = get_delegated_access_token()
            if not token:
                return (
                    "Authentication failed. "
                    "Agent credentials not configured."
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
                return "Message posted successfully as agent"
            return f"Error: {response.status_code} - {response.text}"

        except Exception as e:  # pragma: no cover - network errors
            logging.error(f"Error posting chat message: {str(e)}")
            return f"Error posting chat message: {str(e)}"
    
    print("Delegated access MCP tools registered successfully!") 