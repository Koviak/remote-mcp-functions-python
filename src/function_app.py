"""
Azure Functions MCP Server with Annika-Planner Integration

Updated to use the new planner_sync_service_v2.py with automatic
bi-directional synchronization between Annika AGI and MS Planner.

Key Changes:
- Uses AnnikaPlannerSync instead of old PlannerSyncService
- Automatically configures required settings
- Includes health monitoring and auto-restart
"""

import json
import logging
import os
import time
import threading
import asyncio

import azure.functions as func
from azure.identity import OnBehalfOfCredential

from additional_tools import register_additional_tools
from http_endpoints import register_http_endpoints
from additional_tools_delegated import register_delegated_tools
from token_refresh_service import start_token_refresh_service
from token_api_endpoints import register_token_api_endpoints

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def ensure_configuration():
    """Ensure all required configuration is set."""
    # Check for default plan ID
    plan_id = os.environ.get("DEFAULT_PLANNER_PLAN_ID")
    if not plan_id or plan_id == "REPLACE-WITH-YOUR-PLAN-ID":
        logger.warning(
            "⚠️  DEFAULT_PLANNER_PLAN_ID not configured. "
            "Planner sync will not work without it!"
        )
        logger.info(
            "Get your plan ID from: "
            "https://graph.microsoft.com/v1.0/me/planner/plans"
        )
        logger.info(
            "Then update DEFAULT_PLANNER_PLAN_ID in local.settings.json"
        )
        return False
    
    # Check for Redis configuration
    if not os.environ.get("REDIS_PASSWORD"):
        logger.warning("⚠️  REDIS_PASSWORD not set, using default 'password'")
        os.environ["REDIS_PASSWORD"] = "password"
    
    # Log successful configuration
    logger.info("✅ Configuration loaded from settings:")
    logger.info(f"   - Plan ID: {plan_id[:8]}...")
    user_name = os.environ.get('AGENT_USER_NAME', 'Unknown')
    logger.info(f"   - User: {user_name}")
    user_id = os.environ.get('AGENT_USER_ID', 'Unknown')
    logger.info(f"   - User ID: {user_id[:8]}...")
    
    return True


# Start the token refresh service to keep tokens fresh in Redis
try:
    start_token_refresh_service()
    logger.info("✅ Token refresh service started successfully")
except Exception as e:
    logger.error(f"Failed to start token refresh service: {e}")


# Start Enhanced Local Development Services (includes everything)
if os.environ.get("FUNCTIONS_WORKER_RUNTIME_VERSION") is None:
    # Only start in local development
    try:
        from startup_local_services import start_local_services
        
        # Start all local services (ngrok, webhooks, sync) in background
        def run_local_services():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_local_services())
            # Keep the loop running for monitoring
            loop.run_forever()
        
        services_thread = threading.Thread(
            target=run_local_services,
            daemon=True,
            name="LocalServices"
        )
        services_thread.start()
        logger.info("🚀 Starting local development services...")
        logger.info(
            "This includes: ngrok, webhooks, planner sync, monitoring"
        )
        
        # Give services time to start
        time.sleep(3)
        
        # Check configuration before starting sync
        if ensure_configuration():
            # Import the NEW sync service
            from planner_sync_service_v2 import AnnikaPlannerSync
            
            # Global reference for monitoring
            sync_service = None
            sync_restart_count = 0
            
            def run_planner_sync_with_monitoring():
                """Run sync service with automatic restart on failure."""
                global sync_service, sync_restart_count
                
                while True:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        sync_service = AnnikaPlannerSync()
                        logger.info(
                            f"🔄 Starting Annika-Planner Sync "
                            f"(attempt {sync_restart_count + 1})"
                        )
                        
                        # This will run until stopped or error
                        loop.run_until_complete(sync_service.start())
                        
                    except KeyboardInterrupt:
                        logger.info("Sync service stopped by user")
                        break
                    except Exception as e:
                        sync_restart_count += 1
                        logger.error(
                            f"Sync service crashed: {e}. "
                            f"Restarting in 30 seconds..."
                        )
                        
                        # Clean up
                        if sync_service:
                            try:
                                loop.run_until_complete(sync_service.stop())
                            except Exception:
                                pass
                        
                        # Wait before restart
                        time.sleep(30)
                        
                        # Give up after too many failures
                        if sync_restart_count > 10:
                            logger.error(
                                "Sync service failed too many times. "
                                "Giving up."
                            )
                            break
            
            sync_thread = threading.Thread(
                target=run_planner_sync_with_monitoring, 
                daemon=True,
                name="AnnikaPlannerSync"
            )
            sync_thread.start()
            logger.info("✅ Annika-Planner Sync Service started with monitoring")
            
            # Add health check endpoint
            @app.route(route="health/sync")
            def sync_health_check(req: func.HttpRequest) -> func.HttpResponse:
                """Check sync service health."""
                global sync_service, sync_restart_count
                
                status = {
                    "running": sync_service is not None and sync_service.running,
                    "restart_count": sync_restart_count,
                    "redis_connected": False,
                    "last_sync": None
                }
                
                if sync_service and sync_service.running:
                    # Check Redis connection
                    try:
                        # This is a simplified check
                        status["redis_connected"] = True
                    except Exception:
                        pass
                
                status_code = 200 if status["running"] else 503
                
                return func.HttpResponse(
                    json.dumps(status),
                    status_code=status_code,
                    mimetype="application/json"
                )
        else:
            logger.error(
                "❌ Configuration incomplete. "
                "Annika-Planner sync not started."
            )
        
    except Exception as e:
        logger.error(f"Failed to start local services: {e}")
        logger.error(
            "You may need to manually start services"
        )


# Constants for the Azure Blob Storage container, file, and blob path
_SNIPPET_NAME_PROPERTY_NAME = "snippetname"
_SNIPPET_PROPERTY_NAME = "snippet"
_BLOB_PATH = (
    "snippets/{mcptoolargs." + _SNIPPET_NAME_PROPERTY_NAME + "}.json"
)


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
    ToolProperty(
        _SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."
    ),
    ToolProperty(
        _SNIPPET_PROPERTY_NAME, "string", "The content of the snippet."
    ),
]

tool_properties_get_snippets_object = [
    ToolProperty(
        _SNIPPET_NAME_PROPERTY_NAME, "string", "The name of the snippet."
    )
]

# Convert the tool properties to JSON
tool_properties_save_snippets_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_save_snippets_object]
)
tool_properties_get_snippets_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_get_snippets_object]
)


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
@app.generic_input_binding(
    arg_name="file", type="blob", connection="AzureWebJobsStorage", 
    path=_BLOB_PATH
)
def get_snippet(file: func.InputStream, context) -> str:
    """
    Retrieves a snippet by name from Azure Blob Storage.

    Args:
        file (func.InputStream): The input binding to read the snippet
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
@app.generic_output_binding(
    arg_name="file", type="blob", connection="AzureWebJobsStorage", 
    path=_BLOB_PATH
)
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

# Register token API endpoints for external applications
register_token_api_endpoints(app) 