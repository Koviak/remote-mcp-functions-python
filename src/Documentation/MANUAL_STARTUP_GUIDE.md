# Manual Startup Guide

When the automated startup script has issues finding the `func` command, follow these steps to manually start all services:

## Step 1: Start the Function App

Open a PowerShell terminal in the `src` directory and run:

```powershell
# Option 1: If func is in your PATH
func start

# Option 2: Using npx
npx azure-functions-core-tools@latest start

# Option 3: If you know the full path to func
& "C:\Program Files\Microsoft\Azure Functions Core Tools\func.exe" start
```

Wait until you see all the endpoints listed and the message:
```
Host lock lease acquired by instance ID...
```

## Step 2: Verify Function App is Running

In a new PowerShell terminal, test the Function App:

```powershell
Invoke-WebRequest -Uri http://localhost:7071/api/hello -UseBasicParsing
```

You should get a 200 status response.

## Step 3: Set Up Webhooks (Optional)

If you need MS Graph webhooks, trigger the setup:

```powershell
# This will configure webhook subscriptions
Invoke-WebRequest -Method POST -Uri "http://localhost:7071/api/graph_webhook?validationToken=setup" -UseBasicParsing
```

## Step 4: Start the Planner Sync Service

In another PowerShell terminal, from the `src` directory:

```powershell
python planner_sync_service.py
```

This will start the background sync service that:
- Monitors Redis for task changes
- Syncs tasks to Microsoft Planner
- Downloads updates from Planner every 30 seconds

## Verification

You should now have:
1. **Function App** running on http://localhost:7071
2. **Planner Sync Service** monitoring Redis and syncing with MS Graph
3. **Webhooks** (optional) receiving notifications from MS Graph

## Quick Test

Create a test task via the agent endpoint:

```powershell
$body = @{
    title = "Test Task from Manual Start"
    planId = "YOUR_PLAN_ID"
    bucketId = "YOUR_BUCKET_ID"
} | ConvertTo-Json

Invoke-WebRequest -Method POST -Uri "http://localhost:7071/api/agent/tasks" -Body $body -ContentType "application/json" -UseBasicParsing
```

The task should:
1. Be created in Redis immediately
2. Sync to Microsoft Planner within seconds
3. Be visible in the Planner web interface

## Troubleshooting

If `func` command is not found:
1. Install Azure Functions Core Tools: https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local
2. Or use npm: `npm install -g azure-functions-core-tools@4`
3. Or download directly from: https://github.com/Azure/azure-functions-core-tools/releases

If authentication fails:
1. Check `local.settings.json` has all required values
2. Verify AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID are correct
3. Ensure AGENT_USER_NAME and AGENT_PASSWORD are set 