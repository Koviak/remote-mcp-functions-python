# Cache Population Test Instructions

## Overview
The `test_cache_population.py` script triggers API calls to populate the Redis cache and verifies that caching is working correctly.

## Prerequisites

Before running the test, ensure all services are running:

### 1. Redis Container
```bash
docker ps | grep redis
# Should show: annika_20-redis-1 running on port 6379
```

### 2. ngrok Tunnel
```bash
ngrok http --domain=agency-swarm.ngrok.app 7071
# Should be running in a separate terminal
```

### 3. Function App (MCP Server)
```bash
cd src
func start
# Wait for "Worker process started and initialized"
```

## Running the Test

Once all services are running:

```bash
cd src
python test_cache_population.py
```

## What the Test Does

1. **Service Checks**
   - Verifies Redis is accessible
   - Verifies Function App is responding

2. **User Cache Test**
   - Clears cache for test user
   - Makes API call to `/api/users/{id}`
   - Verifies data is cached with 24-hour TTL

3. **Group Cache Test**
   - Gets list of groups
   - Verifies groups are cached from list calls
   - Checks 24-hour TTL

4. **Plan Cache Test**
   - Gets list of plans
   - Makes specific plan API call
   - Verifies plan is cached with 24-hour TTL

5. **Task Cache Test**
   - Creates a new task via `/api/agent/tasks`
   - Verifies task is stored with NO EXPIRY
   - Checks both storage locations

6. **Metadata Endpoint Test**
   - Tests the `/api/metadata` endpoint
   - Verifies cache retrieval works

## Expected Output

```
🧪 Cache Population Test Suite
============================================================
✅ Redis is running
✅ Function App is running (tested /groups)

1️⃣ Testing User Cache
✅ USER CACHED!
  - Name: Annika Hansen
  - TTL: 24.0 hours

2️⃣ Testing Group Cache
✅ GROUP CACHED!
  - Name: Engineering Team
  - TTL: 24.0 hours

3️⃣ Testing Plan Cache
✅ PLAN CACHED!
  - Title: Product Development
  - TTL: 24.0 hours

4️⃣ Testing Task Cache
✅ TASK STORED (Primary)!
  - TTL: No expiry
  - ✅ No expiry (persists forever)

5️⃣ Testing Metadata Endpoint
✅ User metadata retrieved: Annika Hansen

📊 Cache Statistics
  - Users: 1 items cached
  - Groups: 5 items cached
  - Plans: 2 items cached
  - Tasks (Primary): 382 items cached

🏁 Test Summary
Total: 5/5 tests passed

🎉 All tests passed! Cache population is working correctly!
```

## Troubleshooting

### Function App Not Running
- Kill any stuck func processes: `Get-Process func | Stop-Process -Force`
- Restart from src directory: `cd src; func start`
- Wait 15-20 seconds for full initialization

### 503 Errors
- Function App is still starting up
- Wait 15-20 seconds after starting func
- Check Function App logs for errors

### Cache Not Populating
- Check GraphMetadataManager is integrated in http_endpoints.py
- Verify Redis connection in Function App logs
- Check for authentication errors in API calls

## How Caching Works

1. **Initial Population**: First API call triggers cache storage
2. **TTL Settings**:
   - Users/Groups/Plans: 24 hours
   - Tasks: Never expire
3. **Webhook Updates**: MS Graph webhooks update cache automatically
4. **Cache Keys**:
   - Users: `annika:graph:users:{id}`
   - Groups: `annika:graph:groups:{id}`
   - Plans: `annika:graph:plans:{id}`
   - Tasks: `annika:tasks:{id}` (primary) or `annika:graph:tasks:{id}` (metadata) 