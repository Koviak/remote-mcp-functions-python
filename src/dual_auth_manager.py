"""
Dual Authentication Manager for Phase 2

This module provides both delegated and application-only authentication
for comprehensive monitoring of Teams, Groups, and Planner activities.

Phase 2 Architecture:
- Delegated tokens: For user-specific operations (Annika's context)
- Application tokens: For tenant-wide monitoring (all users/groups)
- Smart token selection: Choose the right token for each operation
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Literal
from datetime import datetime, timedelta
from azure.identity import ClientSecretCredential
from agent_auth_manager import get_agent_token
from mcp_redis_config import get_redis_token_manager

# Load environment variables from local.settings.json if available
def load_local_settings():
    """Load environment variables from local.settings.json"""
    settings_file = Path(__file__).parent / "local.settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                values = settings.get("Values", {})
                for key, value in values.items():
                    if key not in os.environ:  # Don't override existing env vars
                        os.environ[key] = str(value)
        except Exception as e:
            logging.error(f"Error loading local.settings.json: {e}")

# Load settings at module level
load_local_settings()

logger = logging.getLogger(__name__)

TokenType = Literal["delegated", "application"]


class DualAuthManager:
    """Manages both delegated and application-only authentication"""
    
    def __init__(self):
        """Initialize the dual auth manager"""
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self.redis_manager = get_redis_token_manager()
        
        # Token cache
        self._token_cache: Dict[str, Dict] = {}
        
        # Debug configuration
        logger.info(f"Dual auth config - Tenant: {self.tenant_id[:8] if self.tenant_id else 'None'}...")
        logger.info(f"Dual auth config - Client: {self.client_id[:8] if self.client_id else 'None'}...")
        logger.info(f"Dual auth config - Secret: {'***' if self.client_secret else 'None'}")
        
        # Validate configuration
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            logger.error("Missing Azure AD configuration for dual auth")
            logger.error(f"Missing: {[k for k, v in {'tenant_id': self.tenant_id, 'client_id': self.client_id, 'client_secret': self.client_secret}.items() if not v]}")
        else:
            logger.info("✅ Dual auth configuration validated")
    
    def get_token(
        self, 
        token_type: TokenType = "delegated",
        scope: str = ""
    ) -> Optional[str]:
        """
        Get the appropriate token type
        
        Args:
            token_type: "delegated" for user context, "application" for tenant-wide
            scope: The scope to request
            
        Returns:
            Access token string or None
        """
        cache_key = f"{token_type}:{scope}"
        
        # Check cache first
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if cached["expires_at"] > datetime.now():
                logger.debug(f"Using cached {token_type} token")
                return cached["token"]
        
        # Get fresh token
        if token_type == "delegated":
            token = self._get_delegated_token(scope)
            effective_scope = scope
        else:
            effective_scope = scope or "https://graph.microsoft.com/.default"
            token = self._get_application_token(effective_scope)
        
        # Cache the token
        if token:
            expires_at = datetime.now() + timedelta(minutes=50)  # 10min buffer
            self._token_cache[cache_key] = {
                "token": token,
                "expires_at": expires_at
            }
            
            # Only store application tokens here; delegated tokens are stored by agent_auth_manager
            if token_type == "application":
                # Store using the effective scope actually requested
                self._store_token_in_redis(token_type, effective_scope, token)
        
        return token
    
    def _get_delegated_token(self, scope: str) -> Optional[str]:
        """Get delegated access token (user context) honoring requested scopes."""
        try:
            # Pass through scopes so normalization applies in agent_auth_manager
            scope_to_request = (scope or "").strip()
            token = get_agent_token(scope_to_request)
            if token:
                logger.debug("✅ Delegated token acquired via agent auth")
                return token
            else:
                logger.warning("❌ Failed to acquire delegated token")
                return None
                
        except Exception as e:
            logger.error(f"Error acquiring delegated token: {e}")
            return None
    
    def _get_application_token(self, scope: str) -> Optional[str]:
        """Get application-only token (tenant-wide access)"""
        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            token_result = credential.get_token(scope)
            if token_result:
                logger.debug("✅ Application token acquired")
                return token_result.token
            else:
                logger.warning("❌ Failed to acquire application token")
                return None
                
        except Exception as e:
            logger.error(f"Error acquiring application token: {e}")
            return None
    
    def _store_token_in_redis(
        self, 
        token_type: TokenType, 
        scope: str, 
        token: str
    ):
        """Store token in Redis for other services to use"""
        try:
            if self.redis_manager:
                # Calculate expiration timestamp (50 minutes from now)
                expires_on = int((datetime.now() + timedelta(minutes=50)).timestamp())
                
                # Preserve existing application token scope prefix to avoid breaking behavior
                redis_scope = f"{token_type}:{scope}"
                success = self.redis_manager.store_token(
                    token=token,
                    expires_on=expires_on,
                    scope=redis_scope,
                    user_id=None,  # No specific user for these tokens
                    metadata={"type": token_type, "acquired_at": datetime.now().isoformat()}
                )
                
                if success:
                    logger.debug(f"Stored {token_type} token in Redis")
                else:
                    logger.warning(f"Failed to store {token_type} token in Redis")
                
        except Exception as e:
            logger.error(f"Error storing token in Redis: {e}")
    
    def get_best_token_for_operation(self, operation: str) -> Optional[str]:
        """
        Get the best token type for a specific operation
        
        Args:
            operation: The operation being performed
            
        Returns:
            Access token string or None
        """
        # Define which operations need which token type
        application_operations = {
            "tenant_wide_groups",
            "all_teams_monitoring", 
            "tenant_wide_chats",
            "tenant_wide_channels",
            "subscription_management"
        }
        
        delegated_operations = {
            "user_specific_tasks",
            "user_planner_access",
            "user_calendar",
            "user_files"
        }
        
        if operation in application_operations:
            logger.debug(f"Using application token for {operation}")
            return self.get_token("application")
        elif operation in delegated_operations:
            logger.debug(f"Using delegated token for {operation}")
            return self.get_token("delegated")
        else:
            # Default to delegated for unknown operations
            logger.debug(f"Using delegated token (default) for {operation}")
            return self.get_token("delegated")
    
    def validate_permissions(self) -> Dict[str, bool]:
        """
        Validate that both token types have required permissions
        
        Returns:
            Dictionary with validation results
        """
        results = {
            "delegated_token": False,
            "application_token": False,
            "delegated_permissions": [],
            "application_permissions": []
        }
        
        # Test delegated token
        delegated_token = self.get_token("delegated")
        if delegated_token:
            results["delegated_token"] = True
            # Could add permission validation API calls here
        
        # Test application token  
        app_token = self.get_token("application")
        if app_token:
            results["application_token"] = True
            # Could add permission validation API calls here
        
        return results


# Global instance for easy access
_dual_auth_manager = None


def get_dual_auth_manager() -> DualAuthManager:
    """Get the global dual auth manager instance"""
    global _dual_auth_manager
    if _dual_auth_manager is None:
        _dual_auth_manager = DualAuthManager()
    return _dual_auth_manager


def get_token_for_operation(operation: str) -> Optional[str]:
    """
    Convenience function to get the best token for an operation
    
    Args:
        operation: The operation being performed
        
    Returns:
        Access token string or None
    """
    manager = get_dual_auth_manager()
    return manager.get_best_token_for_operation(operation)


def get_delegated_token() -> Optional[str]:
    """Get delegated access token (user context)"""
    manager = get_dual_auth_manager()
    return manager.get_token("delegated")


def get_application_token() -> Optional[str]:
    """Get application-only token (tenant-wide access)"""
    manager = get_dual_auth_manager()
    return manager.get_token("application") 