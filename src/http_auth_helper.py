"""
HTTP Authentication Helper

This module provides authentication helpers for HTTP endpoints that can use
either app-only or delegated access depending on availability.
"""

import os
import logging
from typing import Optional
import azure.functions as func
from azure.identity import ClientSecretCredential
from agent_auth_manager import get_agent_token


def get_http_access_token(req: func.HttpRequest = None,
                          prefer_delegated: bool = True) -> Optional[str]:
    """
    Get access token for HTTP endpoints with fallback logic
    
    Args:
        req: HTTP request object (to check for user token)
        prefer_delegated: If True, prefer delegated access when available
        
    Returns:
        Access token or None
    """
    # Fully autonomous: do not attempt OBO; always use agent delegated when preferred
    
    # Agent delegated (ROPC via agent_auth_manager)
    if prefer_delegated:
        agent_token = get_agent_token()
        if agent_token:
            logging.info("Using agent delegated access for HTTP endpoint")
            return agent_token
    
    # Fall back to app-only authentication
    try:
        credential = ClientSecretCredential(
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            client_id=os.getenv("AZURE_CLIENT_ID"),
            client_secret=os.getenv("AZURE_CLIENT_SECRET")
        )
        
        token = credential.get_token("https://graph.microsoft.com/.default")
        logging.info("Using app-only access for HTTP endpoint")
        return token.token
        
    except Exception as e:
        logging.error(f"App-only authentication failed: {e}")
        return None


def create_auth_response(token: Optional[str],
                         auth_type: str = "unknown") -> dict:
    """
    Create a response dict with authentication info
    
    Args:
        token: The access token
        auth_type: Type of authentication used
        
    Returns:
        Dict with auth info
    """
    return {
        "authenticated": bool(token),
        "auth_type": auth_type if token else "none",
        "has_token": bool(token)
    } 