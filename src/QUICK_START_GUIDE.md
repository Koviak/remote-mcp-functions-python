# Quick Start Guide: MCP-Annika Integration

## Prerequisites

1. Redis server running with RedisJSON module
2. MS Graph API credentials configured
3. Python environment with required packages

## Implementation Steps

### Step 1: Deploy New Files

Copy these new files to your src directory:
- `annika_task_adapter.py` - Format conversion adapter
- `planner_sync_service_v2.py` - Updated sync service
- `test_task_conversion.py` - Testing utility

### Step 2: Configure User Mappings

Edit `annika_task_adapter.py` and update the USER_ID_MAP:

```python
USER_ID_MAP = {
    "5ac3e02f-825f-49f1-a2e2-8fe619020b60": "Joshua Koviak",
    # Add more user ID mappings here
    # "another-graph-user-id": "Another User Name",
}
```

To find user IDs, use the Graph Explorer or this endpoint:
```
GET https://graph.microsoft.com/v1.0/users
```

### Step 3: Set Default Plan ID

Choose one of these methods:

**Option A: Set in Redis**
```bash
redis-cli SET annika:config:default_plan_id "YOUR-PLAN-ID"
```

**Option B: Set environment variable**
```bash
export DEFAULT_PLANNER_PLAN_ID="YOUR-PLAN-ID"
```

To find your plan ID:
```
GET https://graph.microsoft.com/v1.0/me/planner/plans
```

### Step 4: Test the Conversion

Run the test script to verify conversions work:

```bash
python src/test_task_conversion.py
```

You should see:
- Task format conversions
- Successful extraction from conscious_state
- Task counts by list type

### Step 5: Start the Sync Service

Run the new sync service:

```bash
python src/planner_sync_service_v2.py
```

Monitor the logs for:
- "Starting Annika-Planner Sync Service V2..."
- "Monitoring Annika conscious_state changes..."
- "Starting Planner download loop..."

### Step 6: Verify Integration

1. **Create a task in Annika:**
   - Use your task manager interface
   - Watch sync service logs for "Creating Planner task"
   - Check MS Planner to see the task appear

2. **Create a task in Planner:**
   - Add a task via MS Planner web/app
   - Wait 30 seconds for sync
   - Check Redis for the new task

### Step 7: Monitor Operations

Check sync status:
```bash
# View conscious_state
redis-cli JSON.GET annika:conscious_state $ | python -m json.tool

# Check ID mappings
redis-cli KEYS "annika:planner:id_map:*"

# Monitor task operations
redis-cli LLEN annika:task_ops:requests
```

## Troubleshooting

### Tasks not syncing to Planner
1. Check agent token is valid
2. Verify plan ID is set correctly
3. Look for errors in sync service logs

### Tasks not appearing in Annika
1. Check task operation queue is being processed
2. Verify TaskListManager is running
3. Look for results in annika:task_ops:results:*

### Format conversion issues
1. Run test_task_conversion.py to debug
2. Check field mappings in adapter
3. Verify user ID mappings are correct

## Migration from Old Service

If you have the old planner_sync_service.py running:

1. Stop the old service
2. Clear old individual task keys (optional):
   ```bash
   redis-cli --scan --pattern "annika:tasks:*" | \
   grep -v mapping | xargs redis-cli DEL
   ```
3. Start the new service
4. Let it sync existing tasks

## Next Steps

1. Add more user ID mappings as needed
2. Customize task list determination logic
3. Implement bucket-to-list mapping
4. Add webhook support for instant sync
5. Configure error notifications 