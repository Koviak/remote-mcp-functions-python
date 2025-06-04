import json
import logging
import os
import requests
from azure.identity import ClientSecretCredential

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


def register_additional_tools(app):
    """Register additional MCP tools with the function app"""
    
    # Teams Tools
    
    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_teams",
        description="List all Microsoft Teams",
        toolProperties="[]"
    )
    def list_teams(context) -> str:
        """List all teams"""
        try:
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing teams: {str(e)}")
            return f"Error listing teams: {str(e)}"

    tool_properties_list_channels_object = [
        ToolProperty("teamId", "string", "The ID of the team")
    ]
    tool_properties_list_channels_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_list_channels_object]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_channels",
        description="List channels in a team",
        toolProperties=tool_properties_list_channels_json
    )
    def list_channels(context) -> str:
        """List channels in a team"""
        try:
            content = json.loads(context)
            team_id = content["arguments"]["teamId"]
            
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing channels: {str(e)}")
            return f"Error listing channels: {str(e)}"

    tool_properties_post_channel_message_object = [
        ToolProperty("teamId", "string", "The ID of the team"),
        ToolProperty("channelId", "string", "The ID of the channel"),
        ToolProperty("message", "string", "The message content")
    ]
    tool_properties_post_channel_message_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_post_channel_message_object]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="post_channel_message",
        description="Post a message to a Teams channel",
        toolProperties=tool_properties_post_channel_message_json
    )
    def post_channel_message(context) -> str:
        """Post a message to a Teams channel"""
        try:
            content = json.loads(context)
            team_id = content["arguments"]["teamId"]
            channel_id = content["arguments"]["channelId"]
            message = content["arguments"]["message"]
            
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return f"Message posted successfully to channel {channel_id}"
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error posting channel message: {str(e)}")
            return f"Error posting channel message: {str(e)}"

    # Files & Sites Tools

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_drives",
        description="List all drives available to the user",
        toolProperties="[]"
    )
    def list_drives(context) -> str:
        """List all drives"""
        try:
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing drives: {str(e)}")
            return f"Error listing drives: {str(e)}"

    tool_properties_list_root_items_object = [
        ToolProperty("driveId", "string", "The ID of the drive (optional)")
    ]
    tool_properties_list_root_items_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_list_root_items_object]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_root_items",
        description="List items in the root of a drive",
        toolProperties=tool_properties_list_root_items_json
    )
    def list_root_items(context) -> str:
        """List root items in a drive"""
        try:
            content = json.loads(context)
            drive_id = content["arguments"].get("driveId")
            
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing root items: {str(e)}")
            return f"Error listing root items: {str(e)}"

    tool_properties_download_file_object = [
        ToolProperty("driveId", "string", "The ID of the drive"),
        ToolProperty("itemId", "string", "The ID of the file item")
    ]
    tool_properties_download_file_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_download_file_object]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="download_file",
        description="Get download URL for a file",
        toolProperties=tool_properties_download_file_json
    )
    def download_file(context) -> str:
        """Get download URL for a file"""
        try:
            content = json.loads(context)
            drive_id = content["arguments"]["driveId"]
            item_id = content["arguments"]["itemId"]
            
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/drives/{drive_id}/items/"
                f"{item_id}/content",
                headers=headers,
                timeout=10,
                allow_redirects=False
            )
            
            if response.status_code == 302:
                download_url = response.headers.get('Location')
                return f"Download URL: {download_url}"
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error getting download URL: {str(e)}")
            return f"Error getting download URL: {str(e)}"

    tool_properties_sites_search_object = [
        ToolProperty("query", "string", "Search query for SharePoint sites")
    ]
    tool_properties_sites_search_json = json.dumps(
        [prop.to_dict() for prop in tool_properties_sites_search_object]
    )

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="sites_search",
        description="Search for SharePoint sites",
        toolProperties=tool_properties_sites_search_json
    )
    def sites_search(context) -> str:
        """Search for SharePoint sites"""
        try:
            content = json.loads(context)
            query = content["arguments"]["query"]
            
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error searching sites: {str(e)}")
            return f"Error searching sites: {str(e)}"

    # Security & Reporting Tools

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="usage_summary",
        description="Get usage reports summary",
        toolProperties="[]"
    )
    def usage_summary(context) -> str:
        """Get usage reports summary"""
        try:
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{GRAPH_API_ENDPOINT}/reports/getOffice365ActiveUserCounts"
                "(period='D7')",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error getting usage summary: {str(e)}")
            return f"Error getting usage summary: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="get_alerts",
        description="Get security alerts",
        toolProperties="[]"
    )
    def get_alerts(context) -> str:
        """Get security alerts"""
        try:
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error getting alerts: {str(e)}")
            return f"Error getting alerts: {str(e)}"

    @app.generic_trigger(
        arg_name="context",
        type="mcpToolTrigger",
        toolName="list_managed_devices",
        description="List Intune managed devices",
        toolProperties="[]"
    )
    def list_managed_devices(context) -> str:
        """List Intune managed devices"""
        try:
            token = get_access_token()
            if not token:
                return ("Authentication failed. "
                        "Please check your Azure AD credentials.")
            
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
                return response.text
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            logging.error(f"Error listing managed devices: {str(e)}")
            return f"Error listing managed devices: {str(e)}"

    print("Additional MCP tools registered successfully!") 