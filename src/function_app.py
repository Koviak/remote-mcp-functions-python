"""
Azure Functions MCP Server with Multiple Authentication Approaches

This function app demonstrates both App-Only and Delegated (OBO)
authentication patterns:

1. App-Only Authentication (Working):
   - Used by MCP tools in additional_tools.py
   - Uses ClientSecretCredential with application permissions
   - Works with all trigger types including MCP triggers

2. Delegated Access (OBO) - Limited Support:
   - Demonstrated in _acquire_downstream_token() function
   - LIMITATION: MCP triggers cannot access HTTP request headers
   - Only works with HTTP triggers that can access X-MS-TOKEN-AAD-ACCESS-TOKEN
   - Requires built-in authentication enabled in Azure App Service

For production use:
- MCP tools use app-only authentication (additional_tools.py)
- HTTP endpoints can use either authentication method (http_endpoints.py)
- Enable built-in auth for true delegated access with HTTP endpoints
"""

import json
import logging
import os

import azure.functions as func
from azure.identity import OnBehalfOfCredential

from additional_tools import register_additional_tools
from http_endpoints import register_http_endpoints
from additional_tools_delegated import register_delegated_tools

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"


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


# Define the tool properties using the ToolProperty class
tool_properties_save_snippets_object = [
    ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."),
    ToolProperty(_SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."),
]

tool_properties_get_snippets_object = [ToolProperty(_SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet.")]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_save_snippets_object])
tool_properties_get_snippets_json = json.dumps([prop.to_dict() for prop in tool_properties_get_snippets_object])


def _acquire_downstream_token() -> str | None:
    """Acquire a delegated access token using OBO.

    The incoming user token is provided by built-in auth via the
    ``X-MS-TOKEN-AAD-ACCESS-TOKEN`` request header.  This helper exchanges that
    token for a new one with the scopes defined in ``DOWNSTREAM_API_SCOPE``.

    Returns ``None`` if no access token is available.
    """

    # IMPORTANT: MCP tool triggers do not have access to HTTP request headers
    # This is a limitation of the MCP trigger binding - it only provides
    # the tool context. For true OBO flow, you would need to use HTTP
    # triggers instead. This implementation shows the pattern but cannot
    # work with MCP triggers
    
    user_assertion = os.environ.get("X_MS_TOKEN_AAD_ACCESS_TOKEN")
    if not user_assertion:
        logging.warning(
            "User access token not found for OBO flow - "
            "MCP triggers cannot access request headers")
        return None

    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    scope = os.getenv("DOWNSTREAM_API_SCOPE")

    if not all([tenant_id, client_id, client_secret, scope]):
        logging.warning("OBO settings are incomplete")
        return None

    credential = OnBehalfOfCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        user_assertion=user_assertion,
    )

    token = credential.get_token(scope)
    return token.token


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_snippet",
    description="Retrieve a snippet by name.",
    toolProperties=tool_properties_get_snippets_json,
)
@app.generic_input_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet from Azure Blob Storage.
        context: The trigger context containing the input arguments.

    Returns:
        str: The content of the snippet or an error message.
    """
    snippet_content = file.read().decode("utf-8")

    # Attempt to acquire a delegated token using OBO
    token = _acquire_downstream_token()
    if token:
        logging.info("Obtained delegated token for downstream call")

    logging.info(f"Retrieved snippet: {snippet_content}")
    return snippet_content


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="save_snippet",
    description="Save a snippet with a name.",
    toolProperties=tool_properties_save_snippets_json,
)
@app.generic_output_binding(arg_name="file", type="blob", connection="AzureWebJobsStorage", path=_BLOB_PATH)
def save_snippet(file: func.Out[str], context) -> str:
    content = json.loads(context)
    snippet_name_from_args = content["arguments"][_SNIPPET_NAME_PROPERTY_NAME]
    snippet_content_from_args = content["arguments"][_SNIPPET_PROPERTY_NAME]

    if not snippet_name_from_args:
        return "No snippet name provided"

    if not snippet_content_from_args:
        return "No snippet content provided"

    file.set(snippet_content_from_args)
    logging.info(f"Saved snippet: {snippet_content_from_args}")
    return f"Snippet '{snippet_content_from_args}' saved successfully"


# Register additional MCP tools and HTTP endpoints
register_additional_tools(app)

# Register HTTP endpoints
register_http_endpoints(app)

# Register delegated access tools for autonomous agents
register_delegated_tools(app)
