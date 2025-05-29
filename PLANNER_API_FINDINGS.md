# Microsoft Planner API - Key Findings

## Issue Summary
The `office_planner_get_task` tool is failing with a 404 error when trying to access task ID `AAGaxfPn4Uej46oplY26sjYAKsFq`.

## Root Cause
**Microsoft Planner APIs only support DELEGATED permissions, not APPLICATION permissions.**

### Key Facts:
1. **Delegated-Only API**: The Planner API requires a signed-in user context
2. **No Application Permissions**: Unlike many other Graph APIs, Planner doesn't support app-only access
3. **Current Setup Issue**: Your Azure Functions app is using application permissions (client credentials flow), which won't work for Planner

## Why the 404 Error?
When using application permissions with Planner APIs, you typically get:
- **404 Not Found**: The most common response, even if the resource exists
- **403 Forbidden**: Sometimes returned instead of 404
- The API essentially acts as if the resource doesn't exist when accessed without proper delegated context

## Solutions

### Option 1: Implement Delegated Authentication (Recommended for Planner)
You need to implement a delegated authentication flow:
- **Authorization Code Flow**: For web apps with user interaction
- **On-Behalf-Of Flow**: For APIs that receive user tokens
- **Device Code Flow**: For devices without browsers

### Option 2: Use Alternative APIs
If you need app-only access, consider:
- **Microsoft To Do API**: Supports application permissions for task management
- **SharePoint Lists**: Can be used for task tracking with app permissions
- **Custom solution**: Store task data in a database you control

### Option 3: Hybrid Approach
- Use delegated permissions for Planner operations
- Cache/sync data to a system that supports app-only access
- Implement a service account with delegated permissions (less secure)

## Required Permissions for Planner
When implementing delegated auth, you'll need:
- `Tasks.Read` - Read tasks (minimum)
- `Tasks.ReadWrite` - Full task access
- `Group.Read.All` - Read groups with plans
- `Group.ReadWrite.All` - Full group access

## Implementation Notes
1. The task ID format (`AAGaxfPn4Uej46oplY26sjYAKsFq`) looks valid
2. The HTTP endpoints are correctly implemented
3. The issue is purely authentication-related
4. All Planner operations will have this same limitation

## Recommendation
For your MCP tools to work with Planner, you'll need to:
1. Implement a delegated authentication mechanism
2. Store and manage user tokens
3. Handle token refresh
4. Consider the user experience implications

Alternatively, if you need fully automated access without user interaction, consider migrating to a different task management solution that supports application permissions. 