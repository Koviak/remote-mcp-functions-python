# Token API Documentation

This document describes how external applications can retrieve delegated access tokens stored in Redis by the MCP Functions server.

## Overview

The MCP Functions server automatically:
1. Acquires delegated access tokens using agent credentials
2. Stores tokens in Redis with appropriate TTL
3. Automatically refreshes tokens before they expire
4. Provides HTTP endpoints for external applications to retrieve tokens

## Prerequisites

1. **Redis Connection**: Ensure you have access to the same Redis instance used by the MCP server
2. **Environment Variables**: The following Redis configuration should be set:
   ```
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_PASSWORD=password
   REDIS_NAMESPACE=annika:
   ```

## API Endpoints

### 1. Get Token for Specific Scope

Retrieve a valid token for a specific scope/resource.

**Endpoint**: `GET /api/tokens/{scope}`

**Parameters**:
- `scope` (path parameter): The scope/resource to get token for (e.g., `https://graph.microsoft.com/.default`)
- `user_id` (query parameter, optional): User ID for user-specific tokens

**Example Request**:
```bash
# Get token for Microsoft Graph
curl http://localhost:7071/api/tokens/https%3A%2F%2Fgraph.microsoft.com%2F.default

# Get token for a specific user
curl http://localhost:7071/api/tokens/https%3A%2F%2Fgraph.microsoft.com%2F.default?user_id=user123
```

**Success Response** (200 OK):
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6...",
  "expires_on": 1704067200,
  "scope": "https://graph.microsoft.com/.default",
  "refresh_count": 2
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "Token not found",
  "scope": "https://graph.microsoft.com/.default",
  "message": "No valid token found for the specified scope"
}
```

### 2. List All Active Tokens

Get metadata about all active tokens (without the actual token values).

**Endpoint**: `GET /api/tokens`

**Example Request**:
```bash
curl http://localhost:7071/api/tokens
```

**Success Response** (200 OK):
```json
{
  "count": 3,
  "tokens": [
    {
      "scope": "https://graph.microsoft.com/.default",
      "expires_on": 1704067200,
      "stored_at": 1704063600,
      "refresh_count": 1,
      "key": "annika:tokens:agent:https://graph.microsoft.com/.default"
    },
    {
      "scope": "User.Read Mail.Send",
      "expires_on": 1704070800,
      "stored_at": 1704067200,
      "refresh_count": 0,
      "user_id": "user123",
      "key": "annika:tokens:user:user123:User.Read Mail.Send"
    }
  ]
}
```

### 3. Health Check

Check the health of the token service and Redis connection.

**Endpoint**: `GET /api/tokens/health`

**Example Request**:
```bash
curl http://localhost:7071/api/tokens/health
```

**Success Response** (200 OK):
```json
{
  "status": "healthy",
  "redis_connected": true,
  "active_token_count": 3,
  "timestamp": 1704063600
}
```

**Error Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "redis_connected": false,
  "active_token_count": 0,
  "timestamp": 1704063600
}
```

### 4. Manually Refresh Token

Force a token refresh for a specific scope.

**Endpoint**: `POST /api/tokens/refresh/{scope}`

**Parameters**:
- `scope` (path parameter): The scope/resource to refresh token for

**Example Request**:
```bash
curl -X POST http://localhost:7071/api/tokens/refresh/https%3A%2F%2Fgraph.microsoft.com%2F.default
```

**Success Response** (200 OK):
```json
{
  "status": "success",
  "message": "Token refreshed for scope: https://graph.microsoft.com/.default",
  "scope": "https://graph.microsoft.com/.default"
}
```

## Direct Redis Access

If you prefer to access tokens directly from Redis, they are stored with the following key patterns:

### Key Format
```
{REDIS_NAMESPACE}tokens:agent:{scope}     # For agent tokens
{REDIS_NAMESPACE}tokens:user:{user_id}:{scope}  # For user-specific tokens
```

### Example Redis Commands
```bash
# Connect to Redis
redis-cli -h localhost -p 6379 -a password

# Get token for Microsoft Graph
GET "annika:tokens:agent:https://graph.microsoft.com/.default"

# List all active token keys
SMEMBERS "annika:tokens:active"

# Get TTL for a token
TTL "annika:tokens:agent:https://graph.microsoft.com/.default"
```

### Token Data Structure
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6...",
  "expires_on": 1704067200,
  "scope": "https://graph.microsoft.com/.default",
  "stored_at": 1704063600,
  "refresh_count": 2,
  "metadata": {
    "acquired_by": "agent_auth_manager",
    "client_id": "your-client-id"
  }
}
```

## Integration Examples

### Python Example
```python
import requests
import redis
import json

# Option 1: Use HTTP API
def get_token_via_api(scope):
    response = requests.get(
        f"http://localhost:7071/api/tokens/{scope}"
    )
    if response.status_code == 200:
        return response.json()["token"]
    return None

# Option 2: Direct Redis access
def get_token_via_redis(scope):
    r = redis.Redis(
        host='localhost',
        port=6379,
        password='password',
        decode_responses=True
    )
    key = f"annika:tokens:agent:{scope}"
    data = r.get(key)
    if data:
        return json.loads(data)["token"]
    return None

# Use the token
token = get_token_via_api("https://graph.microsoft.com/.default")
if token:
    headers = {"Authorization": f"Bearer {token}"}
    # Make API calls with the token
```

### Node.js Example
```javascript
const axios = require('axios');
const redis = require('redis');

// Option 1: Use HTTP API
async function getTokenViaApi(scope) {
    try {
        const response = await axios.get(
            `http://localhost:7071/api/tokens/${encodeURIComponent(scope)}`
        );
        return response.data.token;
    } catch (error) {
        console.error('Failed to get token:', error);
        return null;
    }
}

// Option 2: Direct Redis access
async function getTokenViaRedis(scope) {
    const client = redis.createClient({
        url: 'redis://:password@localhost:6379'
    });
    
    await client.connect();
    
    const key = `annika:tokens:agent:${scope}`;
    const data = await client.get(key);
    
    await client.disconnect();
    
    if (data) {
        return JSON.parse(data).token;
    }
    return null;
}
```

## Best Practices

1. **Token Caching**: Cache tokens locally and only fetch when expired
2. **Error Handling**: Implement retry logic for token retrieval
3. **Monitoring**: Use the health endpoint to monitor service availability
4. **Security**: 
   - Always use HTTPS in production
   - Consider implementing authentication for the token API endpoints
   - Tokens are sensitive - handle them securely

## Troubleshooting

### Common Issues

1. **Token Not Found**
   - Ensure the agent has successfully authenticated
   - Check if the scope is correctly formatted
   - Verify the token refresh service is running

2. **Redis Connection Failed**
   - Verify Redis credentials and connection settings
   - Check network connectivity to Redis server
   - Ensure Redis is running

3. **Token Expired**
   - The refresh service should prevent this
   - Manually trigger refresh using the refresh endpoint
   - Check refresh service logs for errors

### Logging

The MCP server logs token operations. Check logs for:
- Token acquisition success/failure
- Token refresh operations
- Redis connection issues

## Environment Configuration

Ensure these environment variables are set for the MCP server:

```bash
# Azure AD Configuration
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Agent Credentials
AGENT_USER_NAME=agent@yourdomain.com
AGENT_PASSWORD=agent-password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=password
REDIS_NAMESPACE=annika:
```

## Security Considerations

1. **Access Control**: Consider implementing authentication for token API endpoints
2. **Network Security**: Use TLS/SSL for Redis connections in production
3. **Token Scope**: Request only the minimum required scopes
4. **Audit Logging**: Log all token access for security auditing

## Support

For issues or questions:
1. Check the MCP server logs
2. Verify Redis connectivity
3. Ensure all environment variables are correctly set
4. Review the token refresh service status 