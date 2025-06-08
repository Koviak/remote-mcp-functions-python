"""
Token Refresh Service

This module provides a background service that monitors and refreshes
tokens stored in Redis before they expire, ensuring other applications
always have access to valid tokens.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional
import threading
import time

from mcp_redis_config import get_redis_token_manager, RedisTokenManager
from agent_auth_manager import get_auth_manager, AgentAuthManager

# Configure logging
logger = logging.getLogger(__name__)


class TokenRefreshService:
    """Service that refreshes tokens before they expire"""
    
    def __init__(
        self,
        redis_manager: Optional[RedisTokenManager] = None,
        auth_manager: Optional[AgentAuthManager] = None,
        refresh_interval: int = 300,  # 5 minutes
        refresh_buffer: int = 900      # 15 minutes before expiry
    ):
        """
        Initialize the token refresh service
        
        Args:
            redis_manager: Redis token manager instance
            auth_manager: Agent authentication manager
            refresh_interval: How often to check tokens (seconds)
            refresh_buffer: Refresh tokens this many seconds before expiry
        """
        self.redis_manager = redis_manager or get_redis_token_manager()
        self.auth_manager = auth_manager or get_auth_manager()
        self.refresh_interval = refresh_interval
        self.refresh_buffer = refresh_buffer
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the token refresh service"""
        if self.is_running:
            logger.warning("Token refresh service is already running")
            return
        
        # Acquire initial tokens before starting the refresh loop
        logger.info("Acquiring initial tokens...")
        self._acquire_initial_tokens()
        
        self.is_running = True
        self._thread = threading.Thread(
            target=self._run_refresh_loop,
            daemon=True,
            name="TokenRefreshService"
        )
        self._thread.start()
        logger.info("Token refresh service started")
    
    def stop(self):
        """Stop the token refresh service"""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Token refresh service stopped")
    
    def _run_refresh_loop(self):
        """Main refresh loop"""
        while self.is_running:
            try:
                self._refresh_tokens()
            except Exception as e:
                logger.error(f"Error in token refresh loop: {e}")
            
            # Sleep for the refresh interval
            time.sleep(self.refresh_interval)
    
    def _acquire_initial_tokens(self):
        """Acquire initial tokens for common scopes"""
        try:
            # Common scopes that should have tokens
            scopes = [
                "https://graph.microsoft.com/.default",
                "User.Read Mail.Send Files.ReadWrite.All",
                "Tasks.ReadWrite"
            ]
            
            for scope in scopes:
                logger.info(f"Acquiring initial token for scope: {scope}")
                token = self.auth_manager.get_agent_user_token(scope)
                
                if token:
                    logger.info(
                        f"✅ Successfully acquired initial token for {scope}"
                    )
                else:
                    logger.warning(
                        f"⚠️  Failed to acquire initial token for {scope}"
                    )
                    
        except Exception as e:
            logger.error(f"Error acquiring initial tokens: {e}")
    
    def _refresh_tokens(self):
        """Check and refresh tokens that are close to expiry"""
        try:
            # Get all active tokens
            active_tokens = self.redis_manager.get_all_active_tokens()
            
            if not active_tokens:
                logger.debug("No active tokens to refresh")
                return
            
            current_time = datetime.now().timestamp()
            
            for token_info in active_tokens:
                expires_on = token_info.get("expires_on", 0)
                scope = token_info.get("scope", "")
                user_id = token_info.get("user_id")
                
                # Check if token needs refresh
                time_until_expiry = expires_on - current_time
                
                if time_until_expiry <= self.refresh_buffer:
                    logger.info(
                        f"Token for scope '{scope}' expiring in "
                        f"{time_until_expiry:.0f} seconds, refreshing..."
                    )
                    
                    # Refresh the token
                    self._refresh_single_token(scope, user_id)
        
        except Exception as e:
            logger.error(f"Error refreshing tokens: {e}")
    
    def _refresh_single_token(
        self, scope: str, user_id: Optional[str] = None
    ):
        """Refresh a single token"""
        try:
            # Get a new token using the auth manager
            # For now, we'll use the agent's credentials
            new_token = self.auth_manager.get_agent_user_token(scope)
            
            if new_token:
                # The auth manager will automatically store it in Redis
                self.redis_manager.update_refresh_count(scope, user_id)
                logger.info(f"Successfully refreshed token for scope: {scope}")
            else:
                logger.error(f"Failed to refresh token for scope: {scope}")
                
        except Exception as e:
            logger.error(f"Error refreshing token for scope '{scope}': {e}")


class AsyncTokenRefreshService:
    """Async version of the token refresh service for Azure Functions"""
    
    def __init__(
        self,
        redis_manager: Optional[RedisTokenManager] = None,
        auth_manager: Optional[AgentAuthManager] = None,
        refresh_interval: int = 300,
        refresh_buffer: int = 900
    ):
        self.redis_manager = redis_manager or get_redis_token_manager()
        self.auth_manager = auth_manager or get_auth_manager()
        self.refresh_interval = refresh_interval
        self.refresh_buffer = refresh_buffer
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the async token refresh service"""
        if self.is_running:
            logger.warning("Async token refresh service is already running")
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._run_refresh_loop())
        logger.info("Async token refresh service started")
    
    async def stop(self):
        """Stop the async token refresh service"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Async token refresh service stopped")
    
    async def _run_refresh_loop(self):
        """Main async refresh loop"""
        while self.is_running:
            try:
                await self._refresh_tokens_async()
            except Exception as e:
                logger.error(f"Error in async token refresh loop: {e}")
            
            # Sleep for the refresh interval
            await asyncio.sleep(self.refresh_interval)
    
    async def _refresh_tokens_async(self):
        """Check and refresh tokens asynchronously"""
        try:
            # Run the synchronous refresh in a thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._refresh_tokens_sync)
        except Exception as e:
            logger.error(f"Error in async token refresh: {e}")
    
    def _refresh_tokens_sync(self):
        """Synchronous token refresh logic"""
        service = TokenRefreshService(
            self.redis_manager,
            self.auth_manager,
            self.refresh_interval,
            self.refresh_buffer
        )
        service._refresh_tokens()


# Global service instance
_refresh_service: Optional[TokenRefreshService] = None


def get_token_refresh_service() -> TokenRefreshService:
    """Get or create the global token refresh service"""
    global _refresh_service
    if _refresh_service is None:
        _refresh_service = TokenRefreshService()
    return _refresh_service


def start_token_refresh_service():
    """Start the global token refresh service"""
    service = get_token_refresh_service()
    service.start()


def stop_token_refresh_service():
    """Stop the global token refresh service"""
    service = get_token_refresh_service()
    service.stop() 