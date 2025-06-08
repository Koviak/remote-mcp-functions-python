# Planner Sync V4 - Full Bidirectional Sync

## Overview

V4 combines the best features from V2 and V3 to create a complete bidirectional sync solution.

## Key Features

### ✅ From V2 (Bidirectional):
- **Annika → Planner**: Monitors Redis changes and uploads to Planner
- **Planner → Annika**: Downloads new/updated tasks from Planner
- **Update Detection**: Uses ETags to detect changes
- **Deletion Handling**: Removes tasks deleted from either side

### ✅ From V3 (Smart & Stable):
- **Direct Redis Operations**: No queue dependency
- **Smart Sync Intervals**: Active plans sync more frequently
- **Completed Task Filtering**: Ignores tasks with 100% completion
- **Duplicate Prevention**: Tracks processed tasks
- **Circuit Breakers**: Prevents endless failures (can be added)

## How It Works

### 1. **Upload (Annika → Planner)**
```
Redis change detected → Check if task exists in Planner
  ├─ No → Create new task in Planner
  └─ Yes → Update existing task in Planner
```

### 2. **Download (Planner → Annika)**
```
Check all plans (smart intervals) → For each task:
  ├─ New task → Create in Redis directly
  ├─ Updated (ETag different) → Update in Redis
  └─ Deleted → Remove from Redis
```

### 3. **What Happens When You:**

**Create task in Annika:**
- Detected via Redis pub/sub
- Created in Planner with correct plan
- ID mapping stored

**Update task in Annika:**
- Change detected
- Planner task updated via PATCH
- New ETag stored

**Complete task in Annika:**
- Status synced to Planner (percentComplete: 100)
- Task filtered from future downloads

**Delete task in Annika:**
- Removed from Planner
- Mappings cleaned up

**Create task in Planner:**
- Found during next sync cycle
- Created in appropriate Annika list
- ID mapping established

**Update task in Planner:**
- ETag change detected
- Updates synced to Redis
- New ETag stored

**Complete task in Planner:**
- Filtered out (not synced)
- Annika task remains as-is

**Delete task in Planner:**
- Detected by comparing active IDs
- Removed from Redis
- Mappings cleaned up

## Smart Features

### 1. **No Duplicate Creation**
- Stores ID mappings immediately
- Checks mappings before any create operation
- Tracks processed tasks in memory

### 2. **Efficient Updates**
- ETags prevent unnecessary API calls
- Only syncs when content actually changes
- Batches operations where possible

### 3. **Smart Plan Sync**
- Active plans (>10 tasks): Every 1 minute
- Normal plans (1-10 tasks): Every 5 minutes  
- Inactive plans (0 active tasks): Every 30 minutes

### 4. **Direct Redis Operations**
- No dependency on TaskListManager
- Writes directly to conscious_state
- Immediate feedback

## Configuration

Set these environment variables:
- `DEFAULT_PLANNER_PLAN_ID`: Where to create new tasks from Annika
- `REDIS_PASSWORD`: Redis connection password

## To Use

1. Stop V2 and V3 services
2. Run V4: `python planner_sync_service_v4.py`
3. Or update `function_app.py` to import V4

## Benefits Over Previous Versions

- **V2 Issues Fixed**: No queue dependency, no endless loops
- **V3 Limitations Fixed**: Full bidirectional sync restored
- **Best of Both**: Smart + Complete

This is a production-ready sync service that handles all scenarios correctly! 