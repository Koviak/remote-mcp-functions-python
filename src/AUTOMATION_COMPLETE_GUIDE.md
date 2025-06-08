# Complete Automation Guide: Annika-Planner Integration

## 🚀 Yes, It's Fully Automated!

Once you complete the setup steps below, the MCP server will:

1. **Run automatically and indefinitely** - The sync service starts when the MCP server starts
2. **Auto-restart on failures** - Built-in monitoring restarts the sync if it crashes
3. **Sync all tasks bi-directionally** - You'll see all Annika tasks in Planner and vice versa
4. **Require minimal maintenance** - Just set it up once and forget about it

## 📋 One-Time Setup Requirements

### 1. **Configure User ID Mappings** (5 minutes)
Edit `src/annika_task_adapter.py` and add your Microsoft user ID:

```python
USER_ID_MAP = {
    "YOUR-MICROSOFT-USER-ID": "Your Name",
    # Example: "5ac3e02f-825f-49f1-a2e2-8fe619020b60": "Joshua Koviak",
}
```

To find your user ID:
1. Go to https://graph.microsoft.com/v1.0/me
2. Copy the "id" field

### 2. **Set Default Plan ID** (2 minutes)
Add to your `local.settings.json` or `.env`:

```json
{
  "Values": {
    "DEFAULT_PLANNER_PLAN_ID": "YOUR-PLAN-ID"
  }
}
```

To find your plan ID:
1. Go to https://graph.microsoft.com/v1.0/me/planner/plans
2. Choose the plan you want to use
3. Copy its "id" field

### 3. **Update function_app.py** (1 minute)
Replace the current `function_app.py` with `function_app_updated.py`:

```bash
# Backup original
cp src/function_app.py src/function_app_original.py

# Use updated version
cp src/function_app_updated.py src/function_app.py
```

## 🎯 What Happens When You Start the MCP Server

1. **Token refresh service starts** - Keeps authentication tokens fresh
2. **Local services start** - ngrok, webhooks, monitoring
3. **Configuration check** - Verifies plan ID is set
4. **Sync service starts** - Begins bi-directional synchronization
5. **Health monitoring starts** - Auto-restarts on failures

### Sync Behavior:
- **Annika → Planner**: Instant (event-driven)
- **Planner → Annika**: Every 30 seconds (polling)
- **Initial sync**: All existing tasks sync on startup

## 🔍 What You'll See in MS Planner

All Annika tasks will appear with:
- ✅ Task titles and descriptions
- ✅ Completion status
- ✅ Assigned users (mapped from Annika names)
- ✅ Due dates
- ✅ Priority levels

Task organization:
- Tasks from different Annika lists may appear in the same Planner plan
- Use buckets in Planner to organize as needed
- Task IDs are preserved via internal mappings

## 📊 Monitoring the Integration

### Check sync health:
```bash
curl http://localhost:7071/api/health/sync
```

Response:
```json
{
  "running": true,
  "restart_count": 0,
  "redis_connected": true,
  "last_sync": "2024-01-20T10:30:00Z"
}
```

### View logs:
Look for these key messages:
- "✅ Annika-Planner Sync Service started with monitoring"
- "Syncing Annika changes to Planner..."
- "✅ Created Planner task: {id}"
- "✅ Created Annika task: {id}"

### Check Redis mappings:
```bash
# See all ID mappings
redis-cli KEYS "annika:planner:id_map:*"

# Check specific mapping
redis-cli GET "annika:planner:id_map:Task-CV123-1"
```

## 🛡️ Built-in Resilience

The system handles:
- **Network failures** - Retries with exponential backoff
- **Redis disconnections** - Automatic reconnection
- **MS Graph API limits** - Respects rate limits
- **Service crashes** - Auto-restart up to 10 times
- **Token expiration** - Automatic refresh

## 🚨 Troubleshooting

### Tasks not appearing in Planner?
1. Check logs for "No default plan ID configured"
2. Verify user ID mapping exists
3. Look for "Failed to create Planner task" errors

### Tasks not syncing from Planner?
1. Check if TaskListManager is processing queue
2. Look for "annika:task_ops:requests" backlog
3. Verify Redis connection is stable

### Service keeps restarting?
1. Check configuration is complete
2. Verify Redis is accessible
3. Check authentication tokens are valid

## 🎁 Advanced Features (Optional)

### Custom task routing:
Edit `determine_task_list()` in adapter to route tasks to specific Annika lists based on:
- Planner bucket name
- Task title keywords
- Assigned user

### Faster sync from Planner:
Change `DOWNLOAD_INTERVAL` in `planner_sync_service_v2.py`:
```python
DOWNLOAD_INTERVAL = 10  # Check every 10 seconds instead of 30
```

### Webhook support (instant both ways):
The infrastructure is ready - just needs MS Graph webhook subscriptions for Planner changes.

## ✅ Success Checklist

You know it's working when:
- [ ] Logs show "Sync Service started with monitoring"
- [ ] Creating task in Annika → appears in Planner within seconds
- [ ] Creating task in Planner → appears in Annika within 30 seconds
- [ ] Health endpoint returns `"running": true`
- [ ] No repeated error messages in logs

## 🏁 Summary

**Yes, once configured, it runs completely autonomously!**

The integration will:
- Start automatically with the MCP server
- Run indefinitely with auto-recovery
- Sync all tasks bi-directionally
- Require no manual intervention

Just complete the one-time setup (10 minutes) and you're done. Come back in a week, a month, or a year - it will still be running and keeping everything in sync.

The only maintenance needed:
- Update user mappings if new team members join
- Check logs occasionally for any persistent errors
- Update plan ID if you change Planner plans

That's it! Set it and forget it. 🚀 