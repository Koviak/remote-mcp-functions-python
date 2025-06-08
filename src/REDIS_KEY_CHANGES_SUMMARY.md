# Redis Key Changes for MCP-Annika Integration

## Executive Summary

To integrate the MCP server with Annika's existing task management system, we need to adapt the MCP server to work with Annika's Redis structure rather than changing Annika's structure. This document outlines the key changes required.

## Key Structure Differences

### Current MCP Server Keys
```
annika:tasks:{id}                    # Individual task storage
annika:task:mapping:{redis_id}       # ID mappings
annika:task:mapping:{planner_id}     # Reverse mappings
annika:tasks:updates                 # Pub/sub channel
annika:tasks:sync                    # Sync notifications
```

### Annika AGI Keys (What MCP Must Adapt To)
```
annika:conscious_state               # RedisJSON - Global task lists
annika:consciousness:{conv_id}:components:tasks  # Conversation tasks
annika:task_ops:requests             # Task operation queue
annika:task_ops:results:{op_id}      # Operation results
```

## Task Format Conversions Required

### Field Name Mappings
| MS Planner Field | Annika Field | Notes |
|------------------|--------------|-------|
| percentComplete | percent_complete | Planner: 0-100, Annika: 0-1 |
| assignedTo | assigned_to | Planner: array of IDs, Annika: string name |
| dueDateTime | due_date | Planner: ISO datetime, Annika: date only |
| createdDateTime | created_at | Same format |
| completedDateTime | completed_at | Same format |
| notes | description | Different field names |

### Data Structure Changes
- **MCP**: Flat structure with individual Redis keys per task
- **Annika**: Nested structure within `task_lists` object:
  ```json
  {
    "task_lists": {
      "user_tasks": { "tasks": [...] },
      "research_tasks": { "tasks": [...] },
      "system_two_tasks": { "tasks": [...] }
    }
  }
  ```

## Implementation Changes

### 1. New Adapter Module (`annika_task_adapter.py`)
- Converts between Annika and Planner formats
- Maps user IDs to names and vice versa
- Handles priority and status conversions
- Extracts tasks from nested Annika structure

### 2. Updated Sync Service (`planner_sync_service_v2.py`)
- Monitors `annika:conscious_state` changes via keyspace notifications
- Uses `annika:task_ops:requests` queue for creating/updating tasks
- Maintains ID mappings with new prefix: `annika:planner:id_map:`
- Polls Planner for human changes every 30 seconds

### 3. Key Monitoring Changes
The sync service now monitors:
```python
# Keyspace notifications for conscious_state changes
"__keyspace@0__:annika:conscious_state"

# Task operation results  
"__keyspace@0__:annika:task_ops:results:*"

# Legacy compatibility
"annika:tasks:updates"
```

### 4. Task Operations
Instead of directly modifying Redis, the MCP server now:
1. Creates operation requests in the format expected by TaskListManager
2. Pushes to `annika:task_ops:requests` queue
3. Waits for results at `annika:task_ops:results:{op_id}`

Example operation:
```json
{
  "operation_id": "uuid",
  "operation_type": "create_task",
  "payload": {
    "list_type": "user_tasks",
    "title": "Task Title",
    "assigned_to": "Joshua Koviak",
    "percent_complete": 0.5
  }
}
```

## Migration Steps

1. **Deploy new adapter and sync service**
   - Keep existing planner_sync_service.py for now
   - Deploy planner_sync_service_v2.py alongside

2. **Configure default plan ID**
   ```bash
   # Set in Redis
   SET annika:config:default_plan_id "your-plan-id"
   
   # Or environment variable
   export DEFAULT_PLANNER_PLAN_ID="your-plan-id"
   ```

3. **Update user mappings in adapter**
   - Add MS Graph user IDs to `USER_ID_MAP` in adapter

4. **Test with small subset**
   - Monitor logs for successful conversions
   - Verify tasks appear correctly in both systems

5. **Full deployment**
   - Stop old sync service
   - Run only v2 service

## Benefits of This Approach

1. **No changes to Annika core** - MCP adapts to existing structure
2. **Uses existing TaskListManager** - Maintains data integrity
3. **Agents continue unchanged** - They already monitor conscious_state
4. **Backwards compatible** - Can run both sync services temporarily
5. **Performance** - Agents work at Redis speed, sync happens in background

## Monitoring and Debugging

Check these keys for troubleshooting:
```bash
# View conscious_state structure
redis-cli JSON.GET annika:conscious_state $

# Check ID mappings
redis-cli KEYS "annika:planner:id_map:*"

# Monitor operation queue
redis-cli LLEN annika:task_ops:requests

# Watch for changes
redis-cli --csv PSUBSCRIBE "__keyspace@0__:annika:conscious_state"
```

## Next Steps

1. Review and test the adapter conversions
2. Add more user ID mappings as needed
3. Consider adding bucket-to-list-type mapping logic
4. Implement deletion synchronization
5. Add comprehensive error handling and retries 