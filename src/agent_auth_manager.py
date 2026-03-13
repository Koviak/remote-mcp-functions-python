"""
Agent Authentication Manager

This module enables autonomous agents to authenticate and obtain user tokens
for delegated access, working around MCP trigger limitations.

Authentication Methods:
1. Resource Owner Password Credentials (ROPC) - for autonomous agents
2. Client Certificate Authentication - for service principals
3. Managed Identity - for Azure-hosted agents
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import requests
from azure.core.credentials import AccessToken
from azure.identity import CertificateCredential, ManagedIdentityCredential

from mcp_redis_config import RedisTokenManager, get_redis_token_manager


class AgentAuthManager:
    """Manages authentication for autonomous agents"""
    
    def __init__(
        self, redis_token_manager: Optional[RedisTokenManager] = None
    ):
        """
        Initialize the auth manager
        
        Args:
            redis_token_manager: Optional Redis token manager instance
        """
        self.redis_token_manager = redis_token_manager
        self.tenant_id = os.getenv("AZURE_TENANT_ID")
        self.client_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        
        # Agent-specific credentials
        self.agent_username = os.getenv("AGENT_USER_NAME")
        self.agent_password = os.getenv("AGENT_PASSWORD")
        self.certificate_path = os.getenv("AGENT_CERTIFICATE_PATH")
        
        # Local token cache for quick access
        self._token_cache: Dict[str, AccessToken] = {}

    def _normalize_delegated_user(
        self, delegated_user: Optional[str] = None
    ) -> Optional[str]:
        """Normalize an optional delegated-user alias."""
        if delegated_user is None:
            return None
        normalized = str(delegated_user).strip().lower()
        if not normalized:
            return None
        if normalized in {"agent", "default"}:
            return None
        if normalized not in {"annika", "joshua"}:
            raise ValueError(
                "Unsupported delegated_user. Allowed values: annika, joshua"
            )
        return normalized

    def _get_user_credentials(
        self, delegated_user: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Return (username, password, storage_user_id) for a delegated alias."""
        normalized_user = self._normalize_delegated_user(delegated_user)
        if normalized_user in {None, "annika"}:
            return self.agent_username, self.agent_password, None
        if normalized_user == "joshua":
            return (
                os.getenv("TODO_JOSHUA_USER_NAME"),
                os.getenv("TODO_JOSHUA_PASSWORD"),
                "joshua",
            )
        return None, None, None

    def _cache_key(self, scope: str, user_id: Optional[str] = None) -> str:
        """Return the in-memory cache key for a scope/user pair."""
        token_owner = user_id if user_id else "agent"
        return f"{token_owner}::{scope}"
    
    def get_agent_user_token(
        self,
        scope: str = " ".join(
            [
                # Minimal baseline suitable for most /me bootstraps
                "openid",
                "profile",
                "offline_access",
                "User.Read",
            ]
        ),
        delegated_user: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a user token for the autonomous agent
        
        This method tries multiple authentication methods in order:
        1. Cached token (if still valid)
        2. Stored token (from Redis/storage)
        3. Username/Password authentication (ROPC)
        4. Certificate authentication
        5. Managed Identity (if running in Azure)
        
        Args:
            scope: The scope to request
            
        Returns:
            Access token string or None if authentication fails
        """
        # Determine normalized scope (supports master superset)
        normalized_scope = self._determine_normalized_scope(scope)
        username, password, storage_user_id = self._get_user_credentials(
            delegated_user
        )

        # Check cache first
        cached_token = self._get_cached_token(normalized_scope, storage_user_id)
        if cached_token:
            return cached_token
        
        # Check stored token
        stored_token = self._get_stored_token(normalized_scope, storage_user_id)
        if stored_token:
            return stored_token

        if storage_user_id is not None and not (username and password):
            logging.error(
                "Delegated credentials for user '%s' are not configured",
                storage_user_id,
            )
            return None
        
        # Try to acquire new token
        token = None
        
        # Method 1: Username/Password (ROPC) - Best for autonomous agents
        if username and password:
            token = self._acquire_token_with_ropc(
                normalized_scope,
                username=username,
                password=password,
                delegated_user=storage_user_id or "annika",
            )
        
        # Method 2: Certificate authentication
        elif self.certificate_path and os.path.exists(self.certificate_path):
            token = self._acquire_token_with_certificate(normalized_scope)
        
        # Method 3: Managed Identity (for Azure-hosted agents)
        elif self._is_running_in_azure():
            token = self._acquire_token_with_managed_identity(normalized_scope)
        
        # Store and cache the token
        if token:
            # Cache + persist
            self._cache_token(normalized_scope, token, storage_user_id)
            self._store_token(normalized_scope, token, storage_user_id)
            return token.token
        
        # As a last chance, attempt to read a more permissive master token (if present)
        if storage_user_id is None:
            try:
                master = os.getenv("ANNIKA_DELEGATED_MASTER_SCOPES", "").strip()
                if master and master != normalized_scope:
                    master_key = self._determine_normalized_scope(master)
                    stored_master = self._get_stored_token(master_key)
                    if stored_master:
                        # Do not re-store under narrower scope; just return to unblock
                        return stored_master
            except Exception:
                pass
        
        return None

    def _determine_normalized_scope(self, requested_scope: str) -> str:
        """Return a canonical, normalized scope string.

        - If ANNIKA_DELEGATED_MASTER_SCOPES is set, use it as the effective scope.
        - Always include minimal bootstrap scopes.
        - Normalize by dedupe + sort for stable Redis/cache keys.
        """
        env_master = os.getenv("ANNIKA_DELEGATED_MASTER_SCOPES", "").strip()
        effective = env_master if env_master else (requested_scope or "")
        # Build normalized canonical key
        parts = [p for p in effective.split() if p]
        # Ensure minimal bootstrap scopes are present
        baseline = ["openid", "profile", "offline_access", "User.Read"]
        parts.extend(baseline)
        normalized = " ".join(sorted(set(parts)))
        return normalized
    
    def _acquire_token_with_ropc(
        self,
        scope: str,
        *,
        username: str,
        password: str,
        delegated_user: str,
    ) -> Optional[AccessToken]:
        """
        Acquire token using Resource Owner Password Credentials flow
        
        This allows the agent to authenticate with username/password
        """
        try:
            # Azure AD doesn't support ROPC through azure-identity directly
            # We need to use the OAuth2 endpoint directly
            token_endpoint = (
                f"https://login.microsoftonline.com/"
                f"{self.tenant_id}/oauth2/v2.0/token"
            )
            
            data = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                # space-separated delegated scopes
                "scope": scope,
                "username": username,
                "password": password,
            }
            
            response = requests.post(token_endpoint, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                expires_in = token_data.get("expires_in", 3600)
                expires_on = datetime.now().timestamp() + expires_in
                
                logging.info(
                    "Successfully acquired user token via ROPC for delegated user '%s'",
                    delegated_user,
                )
                return AccessToken(
                    token=token_data["access_token"],
                    expires_on=int(expires_on)
                )
            else:
                logging.error(
                    "ROPC authentication failed for delegated user '%s': %s",
                    delegated_user,
                    response.text,
                )
                
        except Exception as e:
            logging.error(
                "Error in ROPC authentication for delegated user '%s': %s",
                delegated_user,
                e,
            )
        
        return None
    
    def _acquire_token_with_certificate(
        self, scope: str
    ) -> Optional[AccessToken]:
        """Acquire token using certificate authentication"""
        try:
            credential = CertificateCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                certificate_path=self.certificate_path
            )
            
            token = credential.get_token(scope)
            logging.info("Successfully acquired token via certificate")
            return token
            
        except Exception as e:
            logging.error(f"Certificate authentication failed: {e}")
            return None
    
    def _acquire_token_with_managed_identity(
        self, scope: str
    ) -> Optional[AccessToken]:
        """Acquire token using managed identity"""
        try:
            credential = ManagedIdentityCredential(client_id=self.client_id)
            token = credential.get_token(scope)
            logging.info("Successfully acquired token via managed identity")
            return token
            
        except Exception as e:
            logging.error(f"Managed identity authentication failed: {e}")
            return None
    
    def _is_running_in_azure(self) -> bool:
        """Check if running in Azure environment"""
        return any([
            os.getenv("WEBSITE_INSTANCE_ID"),  # App Service
            os.getenv("FUNCTIONS_EXTENSION_VERSION"),  # Functions
            os.getenv("CONTAINER_APP_NAME")  # Container Apps
        ])
    
    def _get_cached_token(
        self, scope: str, user_id: Optional[str] = None
    ) -> Optional[str]:
        """Get token from memory cache"""
        cache_key = self._cache_key(scope, user_id)
        if cache_key in self._token_cache:
            token = self._token_cache[cache_key]
            # Check if token is still valid (with 5 min buffer)
            if token.expires_on > (datetime.now().timestamp() + 300):
                return token.token
            else:
                del self._token_cache[cache_key]
        return None
    
    def _cache_token(
        self, scope: str, token: AccessToken, user_id: Optional[str] = None
    ):
        """Cache token in memory"""
        self._token_cache[self._cache_key(scope, user_id)] = token
    
    def _get_stored_token(
        self, scope: str, user_id: Optional[str] = None
    ) -> Optional[str]:
        """Get token from persistent storage (Redis)"""
        if not self.redis_token_manager:
            return None
        
        try:
            # Get token from Redis
            token_data = self.redis_token_manager.get_token(scope, user_id)
            
            if token_data:
                return token_data.get("token")
                    
        except Exception as e:
            logging.error(f"Error retrieving stored token: {e}")
        
        return None
    
    def _store_token(
        self, scope: str, token: AccessToken, user_id: Optional[str] = None
    ):
        """Store token in persistent storage"""
        if not self.redis_token_manager:
            return
        
        try:
            # Store token using Redis token manager
            self.redis_token_manager.store_token(
                token=token.token,
                expires_on=token.expires_on,
                scope=scope,
                user_id=user_id,
                metadata={
                    "acquired_by": "agent_auth_manager",
                    "client_id": self.client_id,
                    "delegated_user": user_id or "annika",
                },
            )
            
        except Exception as e:
            logging.error(f"Error storing token: {e}")


# Global instance for use in MCP tools
_auth_manager = None


def get_auth_manager() -> AgentAuthManager:
    """Get or create the global auth manager instance"""
    global _auth_manager
    if _auth_manager is None:
        # Initialize with Redis token manager
        try:
            redis_manager = get_redis_token_manager()
            _auth_manager = AgentAuthManager(
                redis_token_manager=redis_manager
            )
        except Exception as e:
            logging.warning(
                f"Failed to initialize Redis token manager: {e}. "
                "Falling back to memory-only caching."
            )
            # Fall back to memory-only caching
            _auth_manager = AgentAuthManager()
    
    return _auth_manager


def get_agent_token(
    scope: Optional[str] = None,
    delegated_user: Optional[str] = None,
) -> Optional[str]:
    """
    Convenience function to get agent token.
    
    Defaults to delegated user scopes (ROPC) when no scope is provided,
    avoiding the application-permission `.default` audience which is not
    valid for `/me` endpoints.
    """
    auth_manager = get_auth_manager()
    if scope is None or str(scope).strip() == "":
        return auth_manager.get_agent_user_token(delegated_user=delegated_user)
    return auth_manager.get_agent_user_token(scope, delegated_user=delegated_user)
