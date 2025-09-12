"""
Azure Functions MCP Server with Annika-Planner Integration

Updated to use the new planner_sync_service_v2.py with automatic
bi-directional synchronization between Annika AGI and MS Planner.

Key Changes:
- Uses AnnikaPlannerSync instead of old PlannerSyncService
- Automatically configures required settings
- Includes health monitoring and auto-restart
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime

import azure.functions as func
from azure.identity import OnBehalfOfCredential

from additional_tools import register_additional_tools
from additional_tools_delegated import register_delegated_tools
from http_endpoints import register_http_endpoints
from token_api_endpoints import register_token_api_endpoints
from token_refresh_service import start_token_refresh_service

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lightweight readiness endpoint for external health checks
@app.route(route="health/ready")
def readiness_check(req: func.HttpRequest) -> func.HttpResponse:
    """Fast readiness probe that does minimal work.

    Returns 200 as soon as the function host is up and routing requests.
    """
    try:
        body = {
            "status": "ready",
            "timestamp": int(datetime.utcnow().timestamp())
        }
        return func.HttpResponse(
            json.dumps(body),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as exc:
        logging.error("Readiness check failure: %s", exc)
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": str(exc)
            }),
            status_code=503,
            mimetype="application/json"
        )


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

# Initialize webhook handler for V5 sync service (skipped if disabled)
DISABLE_LOCAL = os.getenv("DISABLE_LOCAL_SERVICES", "0") == "1"

try:
    if DISABLE_LOCAL:
        logger.info("Local services disabled via DISABLE_LOCAL_SERVICES=1; skipping webhook handler init")
        raise RuntimeError("Local services disabled")
    from chat_subscription_manager import (
        chat_subscription_manager,
        initialize_chat_subscription_manager,
    )
    from webhook_handler import initialize_webhook_handler

    def init_webhook_handler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_webhook_handler())
            logger.info("✅ Webhook handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize webhook handler: {e}")
        finally:
            loop.close()
    
    # Initialize in background thread
    webhook_thread = threading.Thread(
        target=init_webhook_handler,
        daemon=True,
        name="WebhookInit"
    )
    webhook_thread.start()

except Exception as e:
    if not DISABLE_LOCAL:
        logger.error(f"Failed to start webhook handler initialization: {e}")

# Initialize chat subscription manager (skipped if disabled)
try:
    if DISABLE_LOCAL:
        logger.info("Local services disabled; skipping chat subscription manager init")
        raise RuntimeError("Local services disabled")
    def init_chat_sub_manager():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_chat_subscription_manager())
            loop.run_until_complete(
                chat_subscription_manager.subscribe_to_all_existing_chats()
            )
            logger.info("✅ Chat subscription manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize chat subscriptions: {e}")
        finally:
            loop.close()

    chat_thread = threading.Thread(
        target=init_chat_sub_manager,
        daemon=True,
        name="ChatSubsInit",
    )
    chat_thread.start()

except Exception as e:
    if not DISABLE_LOCAL:
        logger.error(f"Failed to start chat subscription initialization: {e}")


# Start Enhanced Local Development Services (includes everything) unless disabled
if os.environ.get("FUNCTIONS_WORKER_RUNTIME_VERSION") is None and not DISABLE_LOCAL:
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
            logger.info(
                "✅ Configuration validated. Sync service will be started "
                "by start_all_services.py"
            )
            logger.info(
                "Note: Function app now uses start_all_services.py for "
                "comprehensive service management"
            )
            
            # Add health check endpoint
            @app.route(route="health/sync")
            def sync_health_check(
                req: func.HttpRequest
            ) -> func.HttpResponse:
                """Check sync service health."""
                
                status = {
                    "running": False,
                    "restart_count": 0,
                    "redis_connected": False,
                    "last_sync": None,
                    "message": (
                        "Sync service managed by start_all_services.py"
                    )
                }
                
                status_code = 200
                
                return func.HttpResponse(
                    json.dumps(status),
                    status_code=status_code,
                    mimetype="application/json"
                )

            @app.route(route="health/chats")
            async def chat_sub_health(req: func.HttpRequest) -> func.HttpResponse:
                """Return chat subscription manager health."""
                health = await chat_subscription_manager.get_subscription_health()
                return func.HttpResponse(
                    json.dumps(health), mimetype="application/json"
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

    # Type check to satisfy mypy
    if not isinstance(tenant_id, str) or not isinstance(client_id, str):
        logging.warning("Invalid tenant_id or client_id type")
        return None
    if not isinstance(scope, str):
        logging.warning("Invalid scope type")
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
def hello_mcp(context) -> str:
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