"""Redis Configuration and Connection Manager."""

# mypy: ignore-errors

# This module interacts heavily with the Redis client, which provides a mix of
# synchronous and asynchronous return types. To keep type checking lightweight
# while still allowing async usage, we ignore detailed type validation here.

import json
import logging
import os
from datetime import datetime
from typing import Any

import redis
from redis.connection import ConnectionPool

# Configure logging
logger = logging.getLogger(__name__)


class RedisConfig:
    """Redis configuration from environment variables"""
    
    def __init__(self):
        # Basic connection settings
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.db = int(os.getenv("REDIS_DB", 0))
        self.password = os.getenv("REDIS_PASSWORD", "password")
        
        # Pool settings
        self.pool_size = int(os.getenv("REDIS_POOL_SIZE", 10))
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", 10))
        
        # Timeout settings
        self.socket_timeout = float(
            os.getenv("REDIS_SOCKET_TIMEOUT", 30.0))
        self.connect_timeout = float(
            os.getenv("REDIS_CONNECT_TIMEOUT", 30.0))
        self.socket_keepalive = (
            os.getenv("REDIS_SOCKET_KEEPALIVE", "true").lower() == "true")
        
        # Retry settings
        self.retry_on_timeout = (
            os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true")
        self.max_retries = int(os.getenv("REDIS_MAX_RETRIES", 3))
        self.retry_delay = float(os.getenv("REDIS_RETRY_DELAY", 0.2))
        
        # Health check settings
        self.health_check_interval = int(
            os.getenv("REDIS_HEALTH_CHECK_INTERVAL", 15))
        self.validation_interval = int(
            os.getenv("REDIS_VALIDATION_INTERVAL", 10))
        self.save_interval = int(os.getenv("REDIS_SAVE_INTERVAL", 10))
        
        # Namespace and other settings
        self.namespace = os.getenv("REDIS_NAMESPACE", "annika:")
        self.decode_responses = (
            os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true")
        
        # Memory settings (for server configuration)
        self.max_memory = os.getenv("REDIS_MAX_MEMORY", "2gb")
        self.max_memory_policy = os.getenv(
            "REDIS_MAX_MEMORY_POLICY", "allkeys-lru")
    
    def get_connection_kwargs(self) -> dict[str, Any]:
        """Get kwargs for Redis connection"""
        # Only include parameters that ConnectionPool accepts
        return {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "password": self.password,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.connect_timeout,
            "socket_keepalive": self.socket_keepalive,
            "socket_keepalive_options": {},
            "encoding": "utf-8",
            "encoding_errors": "strict",
            "decode_responses": self.decode_responses,
            "retry_on_timeout": self.retry_on_timeout,
            "health_check_interval": self.health_check_interval,
            "max_connections": self.max_connections
        }


class RedisTokenManager:
    """Manages token storage and retrieval in Redis"""
    
    def __init__(self, config: RedisConfig | None = None):
        self.config = config or RedisConfig()
        self._pool: ConnectionPool | None = None
        self._client: redis.Redis
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize Redis connection pool and client"""
        try:
            # Create connection pool
            # Remove max_connections from kwargs since it's already included
            kwargs = self.config.get_connection_kwargs()
            kwargs.pop('max_connections', None)
            
            self._pool = ConnectionPool(
                **kwargs,
                max_connections=self.config.pool_size
            )
            
            # Create Redis client
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            self._client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    def _get_key(self, scope: str, user_id: str | None = None) -> str:
        """Generate Redis key for token storage"""
        if user_id:
            return f"{self.config.namespace}tokens:user:{user_id}:{scope}"
        return f"{self.config.namespace}tokens:agent:{scope}"
    
    def store_token(
        self,
        token: str,
        expires_on: int,
        scope: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Store token in Redis with metadata
        
        Args:
            token: The access token
            expires_on: Unix timestamp when token expires
            scope: The scope/resource the token is for
            user_id: Optional user ID for user-specific tokens
            metadata: Optional additional metadata
            
        Returns:
            bool: True if successful
        """
        try:
            key = self._get_key(scope, user_id)
            
            # Calculate TTL (with 5 minute buffer)
            ttl = max(0, expires_on - int(datetime.now().timestamp()) - 300)
            
            # Prepare data
            data = {
                "token": token,
                "expires_on": expires_on,
                "scope": scope,
                "stored_at": int(datetime.now().timestamp()),
                "refresh_count": 0
            }
            
            if user_id:
                data["user_id"] = user_id
            
            if metadata:
                data["metadata"] = metadata
            
            # Store in Redis with TTL
            self._client.setex(
                key,
                ttl,
                json.dumps(data)
            )
            
            # Also store in a set for tracking all tokens
            self._client.sadd(f"{self.config.namespace}tokens:active", key)
            
            logger.info(f"Token stored successfully for scope: {scope}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing token: {e}")
            return False
    
    def get_token(
        self,
        scope: str,
        user_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieve token from Redis
        
        Args:
            scope: The scope/resource
            user_id: Optional user ID
            
        Returns:
            Dict containing token data or None
        """
        try:
            key = self._get_key(scope, user_id)
            data = self._client.get(key)
            
            if not data:
                return None
            
            token_data = json.loads(data)
            
            # Check if token is still valid
            if token_data["expires_on"] > (datetime.now().timestamp() + 300):
                return token_data
            else:
                # Token expired, remove it
                self.remove_token(scope, user_id)
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return None
    
    def remove_token(self, scope: str, user_id: str | None = None) -> bool:
        """Remove token from Redis"""
        try:
            key = self._get_key(scope, user_id)
            self._client.delete(key)
            self._client.srem(f"{self.config.namespace}tokens:active", key)
            return True
        except Exception as e:
            logger.error(f"Error removing token: {e}")
            return False
    
    def update_refresh_count(self, scope: str, user_id: str | None = None) -> bool:
        """Update the refresh count for a token"""
        try:
            key = self._get_key(scope, user_id)
            data = self._client.get(key)
            
            if data:
                token_data = json.loads(data)
                token_data["refresh_count"] = token_data.get("refresh_count", 0) + 1
                token_data["last_refreshed"] = int(datetime.now().timestamp())
                
                # Calculate remaining TTL
                ttl = self._client.ttl(key)
                if ttl > 0:
                    self._client.setex(key, ttl, json.dumps(token_data))
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating refresh count: {e}")
            
        return False
    
    def get_all_active_tokens(self) -> list[dict[str, Any]]:
        """Get all active tokens (for monitoring/management)"""
        try:
            active_keys = self._client.smembers(f"{self.config.namespace}tokens:active")
            tokens = []
            
            for key in active_keys:
                data = self._client.get(key)
                if data:
                    token_data = json.loads(data)
                    # Don't include the actual token in the list
                    token_data.pop("token", None)
                    token_data["key"] = key
                    tokens.append(token_data)
                else:
                    # Clean up stale reference
                    self._client.srem(f"{self.config.namespace}tokens:active", key)
            
            return tokens
            
        except Exception as e:
            logger.error(f"Error getting active tokens: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def close(self):
        """Close Redis connection"""
        try:
            if self._client:
                self._client.close()
            if self._pool:
                self._pool.disconnect()
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Global instance
_redis_token_manager: RedisTokenManager | None = None


def get_redis_token_manager() -> RedisTokenManager:
    """Get or create the global Redis token manager"""
    global _redis_token_manager
    if _redis_token_manager is None:
        _redis_token_manager = RedisTokenManager()
    return _redis_token_manager 