"""
Token API Endpoints

This module provides HTTP endpoints for external applications to
retrieve tokens stored in Redis by the MCP server.
"""

import json
import logging
from datetime import datetime

import azure.functions as func

from mcp_redis_config import get_redis_token_manager

logger = logging.getLogger(__name__)


def register_token_api_endpoints(app: func.FunctionApp):
    """Register HTTP endpoints for token management"""
    
    # Register fixed routes BEFORE parameterized ones to avoid routing conflicts
    @app.route(route="tokens/health", methods=["GET"])
    def token_service_health(req: func.HttpRequest) -> func.HttpResponse:
        """
        Check the health of the token service and Redis connection
        
        Returns:
            JSON response with health status
        """
        try:
            # Get Redis token manager
            redis_manager = get_redis_token_manager()
            
            # Check Redis health
            redis_healthy = redis_manager.health_check()
            
            # Get token statistics
            active_tokens = redis_manager.get_all_active_tokens()
            
            response_data = {
                "status": "healthy" if redis_healthy else "unhealthy",
                "redis_connected": redis_healthy,
                "active_token_count": len(active_tokens),
                "timestamp": int(datetime.now().timestamp())
            }
            
            status_code = 200 if redis_healthy else 503
            
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=status_code,
                mimetype="application/json"
            )
            
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "error": str(e),
                    "timestamp": int(datetime.now().timestamp())
                }),
                status_code=503,
                mimetype="application/json"
            )
    
    @app.route(route="tokens/{scope}", methods=["GET"])
    def get_token(req: func.HttpRequest) -> func.HttpResponse:
        """
        Get a token for a specific scope
        
        Path Parameters:
            scope: The scope/resource to get token for
            
        Query Parameters:
            user_id: Optional user ID for user-specific tokens
            
        Returns:
            JSON response with token data or error
        """
        try:
            scope = req.route_params.get("scope")
            if not scope:
                return func.HttpResponse(
                    json.dumps({"error": "Scope parameter is required"}),
                    status_code=400,
                    mimetype="application/json"
                )
            # Special-case: if scope is 'health', return health info
            if scope == "health":
                try:
                    redis_manager = get_redis_token_manager()
                    redis_healthy = redis_manager.health_check()
                    active_tokens = redis_manager.get_all_active_tokens()
                    response_data = {
                        "status": "healthy" if redis_healthy else "unhealthy",
                        "redis_connected": redis_healthy,
                        "active_token_count": len(active_tokens),
                        "timestamp": int(datetime.now().timestamp()),
                    }
                    return func.HttpResponse(
                        json.dumps(response_data),
                        status_code=200,
                        mimetype="application/json",
                    )
                except Exception as e:
                    logger.error(f"Error checking health (scope path): {e}")
                    return func.HttpResponse(
                        json.dumps({
                            "status": "error",
                            "error": str(e),
                            "timestamp": int(datetime.now().timestamp()),
                        }),
                        status_code=200,
                        mimetype="application/json",
                    )
            
            # Get optional user_id from query params
            user_id = req.params.get("user_id")
            
            # Get Redis token manager
            redis_manager = get_redis_token_manager()
            
            # Retrieve token from Redis
            token_data = redis_manager.get_token(scope, user_id)
            
            if token_data:
                # Return token data
                response_data = {
                    "token": token_data.get("token"),
                    "expires_on": token_data.get("expires_on"),
                    "scope": token_data.get("scope"),
                    "refresh_count": token_data.get("refresh_count", 0)
                }
                
                return func.HttpResponse(
                    json.dumps(response_data),
                    status_code=200,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({
                        "error": "Token not found",
                        "scope": scope,
                        "message": (
                            "No valid token found for the specified scope"
                        )
                    }),
                    status_code=404,
                    mimetype="application/json"
                )
                
        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Internal server error",
                    "message": str(e)
                }),
                status_code=500,
                mimetype="application/json"
            )
    
    @app.route(route="tokens", methods=["GET"])
    def list_active_tokens(req: func.HttpRequest) -> func.HttpResponse:
        """
        List all active tokens (without the actual token values)
        
        Returns:
            JSON array of active token metadata
        """
        try:
            # Get Redis token manager
            redis_manager = get_redis_token_manager()
            
            # Get all active tokens
            active_tokens = redis_manager.get_all_active_tokens()
            
            # Format response
            response_data = {
                "count": len(active_tokens),
                "tokens": active_tokens
            }
            
            return func.HttpResponse(
                json.dumps(response_data),
                status_code=200,
                mimetype="application/json"
            )
            
        except Exception as e:
            logger.error(f"Error listing tokens: {e}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Internal server error",
                    "message": str(e)
                }),
                status_code=500,
                mimetype="application/json"
            )
    
    
    
    @app.route(route="tokens/refresh/{scope}", methods=["POST"])
    def refresh_token(req: func.HttpRequest) -> func.HttpResponse:
        """
        Manually trigger a token refresh for a specific scope
        
        Path Parameters:
            scope: The scope/resource to refresh token for
            
        Query Parameters:
            user_id: Optional user ID for user-specific tokens
            
        Returns:
            JSON response with refresh status
        """
        try:
            scope = req.route_params.get("scope")
            if not scope:
                return func.HttpResponse(
                    json.dumps({"error": "Scope parameter is required"}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            # Import auth manager to refresh token
            from agent_auth_manager import get_auth_manager
            auth_manager = get_auth_manager()
            
            # Force refresh the token
            new_token = auth_manager.get_agent_user_token(scope)
            
            if new_token:
                return func.HttpResponse(
                    json.dumps({
                        "status": "success",
                        "message": f"Token refreshed for scope: {scope}",
                        "scope": scope
                    }),
                    status_code=200,
                    mimetype="application/json"
                )
            else:
                return func.HttpResponse(
                    json.dumps({
                        "status": "failed",
                        "message": f"Failed to refresh token for scope: {scope}",
                        "scope": scope
                    }),
                    status_code=500,
                    mimetype="application/json"
                )
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Internal server error",
                    "message": str(e)
                }),
                status_code=500,
                mimetype="application/json"
            )
    
    logger.info("Token API endpoints registered successfully") 
