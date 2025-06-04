# Multi-Factor Authentication (MFA) Issue with Agent Authentication

## Problem
The agent account `annika@reddypros.com` has Multi-Factor Authentication (MFA) enabled, which prevents the Resource Owner Password Credentials (ROPC) flow from working.

**Error**: `AADSTS50076: Due to a configuration change made by your administrator, or because you moved to a new location, you must use multi-factor authentication`

## Why This Happens
- ROPC flow does not support MFA
- It's a direct username/password authentication that can't handle MFA challenges
- This is by design for security reasons

## Solutions

### Option 1: Create a Dedicated Service Account (Recommended)
1. Create a new Azure AD user specifically for the agent (e.g., `annika-agent@reddypros.com`)
2. Ensure this account:
   - Has MFA disabled
   - Is excluded from Conditional Access policies requiring MFA
   - Has only the necessary permissions
3. Update your `.env` file with the new credentials

### Option 2: Conditional Access Policy Exception
If you must use the existing account:
1. In Azure AD, create a Conditional Access policy
2. Exclude the agent account from MFA requirements
3. Consider adding IP restrictions for added security

### Option 3: Use Application-Only Authentication
Instead of delegated permissions, use app-only permissions:
- The existing `additional_tools.py` already uses this approach
- Works without any user context
- No MFA issues

### Option 4: Certificate-Based Authentication (Most Secure)
1. Generate a certificate for the agent
2. Upload to Azure AD app registration
3. Use certificate instead of username/password
4. Supports service principal authentication

## Current Working Authentication
Your app-only authentication is already working:
- Uses `ClientSecretCredential`
- No MFA requirements
- All non-delegated MCP tools will work

## For Delegated Access
To use the delegated access tools (`additional_tools_delegated.py`), you must resolve the MFA issue using one of the options above.

## Testing App-Only Tools
While we resolve the MFA issue, you can test the app-only tools:

```bash
# Start the function app
func start

# The following MCP tools will work:
- list_teams
- list_channels
- post_channel_message
- list_drives
- download_file
- sites_search
- usage_summary
- get_alerts
- list_managed_devices
```

These use application permissions and don't require user authentication. 