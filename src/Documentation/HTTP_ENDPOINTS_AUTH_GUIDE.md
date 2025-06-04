# HTTP Endpoints Authentication Guide

## Quick Answer: YES! 

You can add new HTTP tools that support BOTH delegated and app-only access. Here's how:

## Current Status

### Existing HTTP Endpoints (34 total)
- Currently use **app-only authentication** exclusively
- Work perfectly with application permissions
- Located in `http_endpoints.py`

### MCP Tools
- **App-only tools** (9): Always use app authentication
- **Delegated tools** (7): Always use agent/user authentication

## Adding New HTTP Endpoints

### Option 1: App-Only (Simple)
```python
def my_new_endpoint_http(req: func.HttpRequest) -> func.HttpResponse:
    token = get_access_token()  # App-only token
    # ... use token with Microsoft Graph
```

### Option 2: Delegated-Only
```python
def my_delegated_endpoint_http(req: func.HttpRequest) -> func.HttpResponse:
    # Get user token from built-in auth
    user_token = req.headers.get('X-MS-TOKEN-AAD-ACCESS-TOKEN')
    
    # Or use agent token
    from agent_auth_manager import get_agent_token
    token = get_agent_token()
    
    # ... use token with Microsoft Graph
```

### Option 3: Dual Authentication (Best!)
```python
from http_auth_helper import get_http_access_token

def my_smart_endpoint_http(req: func.HttpRequest) -> func.HttpResponse:
    # Automatically uses best available auth method:
    # 1. User delegated (if available)
    # 2. Agent delegated (if configured)
    # 3. App-only (fallback)
    token = get_http_access_token(req, prefer_delegated=True)
    
    # ... use token with Microsoft Graph
```

## Authentication Priority

When using `get_http_access_token()`:

1. **User Delegated** (Highest Priority)
   - Requires built-in auth enabled in Azure
   - User authenticates through Azure AD
   - Token in `X-MS-TOKEN-AAD-ACCESS-TOKEN` header

2. **Agent Delegated** (Medium Priority)  
   - Uses Annika's credentials
   - Works for autonomous scenarios
   - No user interaction needed

3. **App-Only** (Fallback)
   - Always available
   - Uses application permissions
   - Works for all scenarios

## Examples

### Adaptive Email Endpoint
```python
def send_email_adaptive(req: func.HttpRequest) -> func.HttpResponse:
    token = get_http_access_token(req)
    
    # With delegated: sends as authenticated user
    # With app-only: needs 'from' parameter
    
    if is_delegated_token(token):
        endpoint = "/me/sendMail"
    else:
        from_user = req.get_json().get('from')
        endpoint = f"/users/{from_user}/sendMail"
```

### User Info Endpoint
```python
def get_user_adaptive(req: func.HttpRequest) -> func.HttpResponse:
    token = get_http_access_token(req)
    user_id = req.params.get('userId', 'me')
    
    # /me only works with delegated auth
    # /users/{id} works with both
```

## Benefits of Dual Auth

1. **Flexibility**: Same endpoint works for users AND autonomous agents
2. **Graceful Degradation**: Falls back to app-only if needed
3. **Context Awareness**: Can detect auth type and adapt behavior
4. **Single Codebase**: No need for separate endpoints

## Quick Start

1. Use the helper function:
   ```python
   from http_auth_helper import get_http_access_token
   ```

2. Get token with fallback:
   ```python
   token = get_http_access_token(req)
   ```

3. Handle both scenarios in your logic

## Summary

- ✅ **Yes**, you can add HTTP endpoints that work with both auth types
- ✅ Use `http_auth_helper.py` for automatic auth selection
- ✅ Endpoints can adapt based on available authentication
- ✅ Single endpoint can serve users, agents, and app-only scenarios

The implementation in `example_dual_auth_endpoint.py` shows complete examples! 