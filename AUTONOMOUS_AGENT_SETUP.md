# Autonomous Agent Authentication Setup Guide

This guide explains how to enable autonomous agents to use delegated access with the MCP server, working around the limitation that MCP triggers cannot access HTTP request headers.

## Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐
│  Autonomous Agent   │     │   Azure AD / Entra  │
│                     │────▶│                     │
│  - Username/Pass    │     │  - ROPC Flow        │
│  - Certificate      │     │  - User Context     │
│  - Managed Identity │     │  - Delegated Perms  │
└─────────────────────┘     └─────────────────────┘
           │                           │
           │                           │
           ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Agent Auth Manager │     │    Access Token     │
│                     │────▶│                     │
│  - Token Caching    │     │  - User Context     │
│  - Token Storage    │     │  - Delegated Scope  │
│  - Auto-refresh     │     │  - Expires in 1hr   │
└─────────────────────┘     └─────────────────────┘
           │
           │
           ▼
┌─────────────────────┐
│    MCP Tools        │
│                     │
│  - Get token from   │
│    Auth Manager     │
│  - Use delegated    │
│    permissions      │
└─────────────────────┘
```

## Setup Steps

### 1. Configure Azure AD Application

First, ensure your Azure AD application is configured for the authentication method you'll use:

#### For Username/Password (ROPC) Authentication:
1. In Azure AD, go to your app registration
2. Navigate to **Authentication** → **Advanced settings**
3. Enable **"Allow public client flows"** (required for ROPC)
4. Add delegated permissions:
   - `User.Read`
   - `Mail.Send`
   - `Files.ReadWrite.All`
   - `Teams.ReadWrite.All`
   - `Tasks.ReadWrite`
   - Any other delegated permissions your agent needs

#### For Certificate Authentication:
1. Generate a certificate:
   ```bash
   openssl req -x509 -newkey rsa:4096 -keyout agent-key.pem -out agent-cert.pem -days 365 -nodes
   ```
2. Upload the certificate to your app registration
3. Note the certificate thumbprint

#### For Managed Identity (Azure-hosted agents):
1. Enable managed identity on your Azure resource
2. Grant the managed identity access to required resources

### 2. Set Environment Variables

Add these to your `local.settings.json` or Azure configuration:

```json
{
  "Values": {
    // Existing settings...
    "AZURE_CLIENT_ID": "your-app-client-id",
    "AZURE_CLIENT_SECRET": "your-app-client-secret",
    "AZURE_TENANT_ID": "your-tenant-id",
    
    // Agent-specific settings (choose one method):
    
    // Method 1: Username/Password (ROPC)
    "AGENT_USERNAME": "agent@yourdomain.com",
    "AGENT_PASSWORD": "agent-password",
    
    // Method 2: Certificate
    "AGENT_CERTIFICATE_PATH": "/path/to/agent-cert.pem",
    
    // Optional: Redis for token storage
    "REDIS_URL": "redis://localhost:6379"
  }
}
```

### 3. Important Security Considerations

⚠️ **ROPC Security Warning**: The Resource Owner Password Credentials flow is less secure because:
- It requires storing the agent's password
- It doesn't support MFA
- It's being deprecated for some scenarios

**Recommended**: Use certificate authentication or managed identity when possible.

### 4. Test the Setup

Create a test script to verify agent authentication:

```python
# test_agent_auth.py
import os
from agent_auth_manager import get_agent_token

# Test getting a token
token = get_agent_token()
if token:
    print("✅ Successfully obtained agent token")
    print(f"Token preview: {token[:20]}...")
else:
    print("❌ Failed to obtain agent token")
    print("Check your configuration")
```

### 5. Available Delegated MCP Tools

Once configured, the following MCP tools will use delegated permissions:

- **get_my_profile** - Get the agent's user profile
- **list_my_files** - List files in the agent's OneDrive
- **send_email_as_agent** - Send email as the agent user
- **list_my_calendar** - List agent's calendar events
- **create_todo_task** - Create tasks in agent's To Do
- **list_my_teams** - List teams the agent is a member of
- **post_teams_message_as_agent** - Post messages as the agent

### 6. Token Storage Options

The auth manager supports multiple token storage backends:

#### Memory Only (Default)
- Tokens cached in memory
- Lost on function restart
- Good for testing

#### Redis (Recommended)
- Tokens persist across restarts
- Shared across function instances
- TTL automatically managed

#### Azure Key Vault (Future)
- Most secure option
- Requires additional configuration

### 7. Monitoring and Troubleshooting

Enable logging to monitor authentication:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Common issues:
1. **"Allow public client flows" not enabled** - Required for ROPC
2. **Incorrect permissions** - Ensure delegated permissions are granted
3. **Consent not granted** - Admin consent may be required
4. **Token expiration** - Tokens expire in 1 hour, auth manager handles refresh

### 8. Production Deployment

For production:
1. Use certificate authentication or managed identity
2. Enable Redis for token persistence
3. Monitor token acquisition failures
4. Implement retry logic for token acquisition
5. Consider using Azure Key Vault for secrets

### 9. Hybrid Approach

You can use both authentication methods:
- **App-only permissions** for administrative tasks
- **Delegated permissions** for user-specific operations

This provides maximum flexibility while working within MCP limitations.

## Example Usage

```python
# In your agent code
from src.agent_auth_manager import get_agent_token

# Get token for specific scope
token = get_agent_token("Files.ReadWrite.All Teams.ReadWrite.All")

# Use with Microsoft Graph
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
```

## Summary

This solution enables autonomous agents to:
1. ✅ Authenticate with their own identity
2. ✅ Use delegated permissions in MCP tools
3. ✅ Cache tokens for performance
4. ✅ Work around MCP trigger limitations
5. ✅ Support multiple authentication methods

The agent auth manager handles the complexity of token acquisition and management, allowing MCP tools to simply request tokens when needed. 