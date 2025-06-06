# Automated Local Development Startup Guide

## Overview

The Function App now automatically starts all required services for local development when you run `func start`. No manual intervention needed!

## What Happens Automatically

When you run `func start`, the following services start automatically:

1. **ngrok** - Creates a public tunnel to your local Function App
2. **Webhook Subscriptions** - Sets up MS Graph webhooks for:
   - Email messages
   - Calendar events  
   - Group updates (up to 10 groups)
   - Teams updates (up to 5 teams)
3. **Planner Sync Service** - Handles bidirectional sync:
   - Event-driven uploads (immediate)
   - Polling downloads (every 30 seconds)
4. **Subscription Monitoring** - Renews webhooks before they expire
5. **Token Refresh Service** - Keeps authentication tokens fresh

## Prerequisites

Ensure your `local.settings.json` contains:

```json
{
  "Values": {
    "AZURE_TENANT_ID": "your-tenant-id",
    "AZURE_CLIENT_ID": "your-client-id", 
    "AZURE_CLIENT_SECRET": "your-client-secret",
    "AGENT_USER_NAME": "annika@yourdomain.com",
    "AGENT_PASSWORD": "agent-password",
    "NGROK_DOMAIN": "your-custom-domain.ngrok.app" // Optional
  }
}
```

## Starting the Function App

Simply run:

```powershell
func start
```

You'll see logs indicating each service starting:

```
🚀 Starting local development services...
This includes: ngrok, webhooks, planner sync, monitoring
✅ ngrok started: https://your-domain.ngrok.app
✅ App-only authentication verified
✅ Agent authentication verified
📋 Setting up webhook subscriptions...
✅ Created user message subscription
✅ Created calendar event subscription
👥 Setting up group subscriptions...
✅ Webhook setup complete (2+ subscriptions)
✅ All services started successfully!
📡 Webhook URL: https://your-domain.ngrok.app/api/graph_webhook
🔔 Ready to receive notifications
✅ Planner Sync Service started
```

## What If Something Fails?

If any service fails to start, you'll see error messages. Common issues:

### ngrok Not Found
```
Error starting ngrok: [Errno 2] No such file or directory: 'ngrok'
```
**Solution**: Install ngrok: https://ngrok.com/download

### Missing Credentials
```
❌ Missing settings: AZURE_TENANT_ID, AZURE_CLIENT_ID
```
**Solution**: Update your `local.settings.json` with required values

### Authentication Failed
```
❌ Agent authentication not available
```
**Solution**: Check AGENT_USER_NAME and AGENT_PASSWORD are correct

## Manual Fallback

If automated startup fails, you can still run services manually:

1. Start ngrok:
   ```powershell
   ngrok http 7071
   ```

2. Set up webhooks:
   ```powershell
   python src/setup_local_webhooks.py
   ```

## Monitoring

The system automatically:
- Monitors webhook subscriptions every hour
- Renews subscriptions before they expire (48-hour lifespan)
- Logs all webhook notifications received
- Syncs Planner tasks every 30 seconds

## Stopping Services

When you stop the Function App (Ctrl+C), all services stop automatically.

## Architecture

```
func start
    ├── Token Refresh Service (background thread)
    ├── Local Services Manager (background thread)
    │   ├── ngrok process
    │   ├── Webhook setup
    │   └── Subscription monitor
    └── Planner Sync Service (background thread)
        ├── Upload loop (Redis → Planner)
        └── Download loop (Planner → Redis)
```

## Testing

To test webhooks are working:

1. Send an email to the agent user
2. Create a calendar event
3. Update a group the agent is member of

Watch the Function App logs for incoming notifications! 