# MS-MCP Server RedisJSON Conversion Plan

**Document Version:** 1.0  
**Created:** October 14, 2025  
**Purpose:** Comprehensive plan to convert ms-mcp_server to use RedisJSON exclusively for all task management operations

---

## 🎯 Executive Summary

Convert the MS-MCP server from mixed Redis storage patterns (plain strings + RedisJSON) to **RedisJSON-only** for all task management operations. This aligns with Annika 2.0's architectural principle: "RedisJSON for everything we can" and ensures seamless compatibility with OpenAI structured outputs.

### Benefits
1. **Direct OpenAI Integration**: Structured outputs → RedisJSON without conversion
2. **Atomic Field Updates**: Update specific task fields without full rewrites
3. **JSONPath Queries**: Powerful filtering and searching capabilities
4. **Type Safety**: Redis enforces JSON structure validation
5. **Performance**: Faster partial updates and queries
6. **Consistency**: Single storage pattern across all task operations

---

## 📋 Current State Analysis

### Current Storage Patterns (Mixed)

#### ✅ Already Using RedisJSON
- `annika:conscious_state` - Global consciousness state
- `annika:consciousness:{conv_id}:components:tasks` - Conversation-specific tasks
- Some metadata caches via `JSON.GET`/`JSON.SET`

#### ❌ Using Plain String Storage
- `annika:tasks:{task_id}` - **Primary task storage** (uses `redis.set()` and `redis.get()`)
- `annika:planner:tasks:{task_id}` - Temporary Planner cache (uses `setex()`)
- Task lists in some HTTP endpoints

### Files Requiring Changes

| File | Current Pattern | Lines to Change | Priority |
|------|----------------|-----------------|----------|
| `src/annika_task_adapter.py` | String GET/SET | 292-295, 229-310 | **HIGH** |
| `src/http_endpoints.py` | String GET/SET | Multiple endpoints | **HIGH** |
| `src/planner_sync_service_v5.py` | Mixed | Task reads/writes throughout | **HIGH** |
| `src/planner_sync_service_v4.py` | Mixed | Legacy reference | MEDIUM |
| `src/planner_sync_service_v3.py` | Mixed | Legacy reference | LOW |
| `src/endpoints/planner.py` | String operations | Task CRUD operations | HIGH |
| `src/endpoints/tasks_buckets.py` | String operations | Task operations | HIGH |
| `src/endpoints/agent_tools.py` | String operations | Agent task creation | HIGH |

---

## 🔧 Conversion Specifications

### 1. Primary Task Storage (`annika:tasks:{task_id}`)

**Current Implementation:**
```python
# Writing
await self.redis.set(f"annika:tasks:{task_id}", json.dumps(task))

# Reading
raw = await self.redis.get(f"annika:tasks:{task_id}")
if raw:
    task = json.loads(raw)
```

**Target Implementation:**
```python
# Writing (full document)
await self.redis.execute_command(
    "JSON.SET", 
    f"annika:tasks:{task_id}", 
    "$", 
    json.dumps(task)
)

# Reading (full document)
task_json = await self.redis.execute_command(
    "JSON.GET", 
    f"annika:tasks:{task_id}", 
    "$"
)
if task_json:
    task = json.loads(task_json)[0]  # JSONPath returns array

# Partial update (specific field)
await self.redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{task_id}",
    "$.status",
    '"completed"'  # Must be valid JSON
)

# Increment numeric field
await self.redis.execute_command(
    "JSON.NUMINCRBY",
    f"annika:tasks:{task_id}",
    "$.percentComplete",
    10
)
```

### 2. Temporary Planner Cache (`annika:planner:tasks:{task_id}`)

**Current Implementation:**
```python
# String storage with TTL
await self.redis.setex(
    f"annika:planner:tasks:{task_id}",
    3600,  # 1 hour TTL
    json.dumps(task)
)
```

**Target Implementation:**
```python
# RedisJSON with separate TTL
await self.redis.execute_command(
    "JSON.SET",
    f"annika:planner:tasks:{task_id}",
    "$",
    json.dumps(task)
)
await self.redis.expire(f"annika:planner:tasks:{task_id}", 3600)
```

### 3. Graph Metadata Cache (`annika:graph:tasks:{task_id}`)

**Current Implementation:**
```python
# Already uses RedisJSON in some places
await self.redis.execute_command(
    "JSON.SET",
    f"annika:graph:tasks:{task_id}",
    "$",
    json.dumps(graph_task)
)
```

**Target Implementation:**
✅ **No change needed** - already using RedisJSON correctly

---

## 📝 Detailed File Changes

### File 1: `src/annika_task_adapter.py`

#### Change 1: `get_all_annika_tasks()` Method (Lines 286-308)

**Current Code:**
```python
cursor, keys = await self.redis.scan(
    cursor, match=pattern, count=200
)
for task_key in keys:
    try:
        raw = await self.redis.get(task_key)  # ❌ Plain GET
        if not raw:
            continue
        task = json.loads(raw)
```

**Updated Code:**
```python
cursor, keys = await self.redis.scan(
    cursor, match=pattern, count=200
)
for task_key in keys:
    try:
        # Use RedisJSON GET
        task_json = await self.redis.execute_command(
            "JSON.GET", 
            task_key, 
            "$"
        )
        if not task_json:
            continue
        # JSONPath returns array, take first element
        task_data = json.loads(task_json)
        if not isinstance(task_data, list) or not task_data:
            continue
        task = task_data[0]
```

**Rationale:** Converts from plain string GET to RedisJSON GET for authoritative task keys.

---

### File 2: `src/http_endpoints.py`

#### Change 2.1: `create_agent_task_http()` Function

**Current Code Location:** Line ~1800-1900 (based on grep results)

**Current Pattern:**
```python
redis_client.set(f"annika:tasks:{task['id']}", json.dumps(task))
```

**Updated Pattern:**
```python
# Create with RedisJSON
await redis_client.execute_command(
    "JSON.SET",
    f"annika:tasks:{task['id']}",
    "$",
    json.dumps(task)
)
```

#### Change 2.2: Task Retrieval in HTTP Endpoints

**Search Pattern:** Look for all instances of:
- `redis_client.get(f"annika:tasks:` 
- `redis.get("annika:planner:tasks:`

**Replace With:** RedisJSON GET operations as shown in specifications above

#### Change 2.3: Temporary Planner Cache

**Current Code Pattern:**
```python
redis_client.setex(
    f"annika:planner:tasks:{task_id}",
    3600,
    json.dumps(task_data)
)
```

**Updated Pattern:**
```python
# Store with RedisJSON, then set TTL
await redis_client.execute_command(
    "JSON.SET",
    f"annika:planner:tasks:{task_id}",
    "$",
    json.dumps(task_data)
)
await redis_client.expire(f"annika:planner:tasks:{task_id}", 3600)
```

---

### File 3: `src/planner_sync_service_v5.py`

#### Change 3.1: Task Read Operations

**Function:** `_sync_from_planner_to_annika()` and similar

**Current Pattern:**
```python
# Check if task exists in Annika
annika_task_key = f"annika:tasks:{annika_id}"
existing_raw = await self.redis.get(annika_task_key)
if existing_raw:
    existing_task = json.loads(existing_raw)
```

**Updated Pattern:**
```python
# Check if task exists in Annika (RedisJSON)
annika_task_key = f"annika:tasks:{annika_id}"
existing_json = await self.redis.execute_command(
    "JSON.GET", 
    annika_task_key, 
    "$"
)
if existing_json:
    existing_data = json.loads(existing_json)
    existing_task = existing_data[0] if existing_data else None
```

#### Change 3.2: Task Write Operations

**Function:** `_create_in_planner()`, `_update_task()`, etc.

**Current Pattern:**
```python
await self.redis.set(
    f"annika:tasks:{annika_id}",
    json.dumps(annika_task)
)
```

**Updated Pattern:**
```python
await self.redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{annika_id}",
    "$",
    json.dumps(annika_task)
)
```

#### Change 3.3: Partial Task Updates

**New Capability:** Use JSONPath for efficient field updates

**Example - Update Status Only:**
```python
# Instead of reading full task, modifying, and rewriting:
# OLD WAY (3 operations):
task_json = await redis.get(f"annika:tasks:{task_id}")
task = json.loads(task_json)
task['status'] = 'completed'
await redis.set(f"annika:tasks:{task_id}", json.dumps(task))

# NEW WAY (1 operation):
await redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{task_id}",
    "$.status",
    '"completed"'
)
```

**Example - Update Timestamp:**
```python
await redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{task_id}",
    "$.updated_at",
    f'"{datetime.utcnow().isoformat()}Z"'
)
```

---

### File 4: `src/endpoints/planner.py`

**Changes Required:**
1. Convert all task retrieval to `JSON.GET`
2. Convert all task storage to `JSON.SET`
3. Update error handling for RedisJSON responses
4. Add JSONPath query examples for filtering

---

### File 5: `src/endpoints/tasks_buckets.py`

**Changes Required:**
1. Task CRUD operations → RedisJSON
2. Bucket association updates → JSONPath
3. Task list retrieval → JSON.GET with filters

---

### File 6: `src/endpoints/agent_tools.py`

**Changes Required:**
1. Agent task creation → JSON.SET
2. Task status updates → Partial updates with JSONPath
3. Task assignment → Field-level updates

---

## 🔍 Search and Filter Capabilities

### New JSONPath Query Patterns

**Filter by Status:**
```python
# Get all completed tasks
completed_tasks = await redis.execute_command(
    "JSON.GET",
    "annika:tasks:*",  # Note: Need to iterate keys
    "$[?(@.status=='completed')]"
)
```

**Filter by Date Range:**
```python
# Tasks due in next 7 days (requires scanning keys)
import datetime
threshold = (datetime.datetime.now() + datetime.timedelta(days=7)).isoformat()

# For each task key:
task_json = await redis.execute_command(
    "JSON.GET",
    task_key,
    f"$[?(@.due_date<='{threshold}')]"
)
```

**Filter by Assignment:**
```python
# Get tasks assigned to specific user
tasks = await redis.execute_command(
    "JSON.GET",
    f"annika:tasks:{task_id}",
    "$[?(@.assigned_to=='Joshua Koviak')]"
)
```

### RediSearch Integration (Future Enhancement)

**Note:** For advanced searching across all tasks, consider adding RediSearch index:

```python
# Create search index (one-time setup)
await redis.execute_command(
    "FT.CREATE", "idx:tasks",
    "ON", "JSON",
    "PREFIX", "1", "annika:tasks:",
    "SCHEMA",
    "$.title", "AS", "title", "TEXT",
    "$.status", "AS", "status", "TAG",
    "$.priority", "AS", "priority", "TAG",
    "$.assigned_to", "AS", "assigned_to", "TEXT",
    "$.due_date", "AS", "due_date", "NUMERIC", "SORTABLE",
    "$.percent_complete", "AS", "percent_complete", "NUMERIC"
)

# Search example
results = await redis.execute_command(
    "FT.SEARCH", "idx:tasks",
    "@status:{in_progress} @priority:{high|urgent}",
    "SORTBY", "due_date", "ASC",
    "LIMIT", "0", "10"
)
```

---

## 🧪 Testing Strategy

### 1. Unit Tests

**Create:** `src/Tests/test_redisjson_conversion.py`

**Test Coverage:**
```python
import pytest
import json
from datetime import datetime

class TestRedisJSONConversion:
    """Test RedisJSON task storage and retrieval"""
    
    async def test_create_task_with_redisjson(self, redis_client):
        """Test creating task with JSON.SET"""
        task = {
            "id": "test-task-001",
            "title": "Test Task",
            "status": "not_started",
            "percent_complete": 0.0,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Create with RedisJSON
        await redis_client.execute_command(
            "JSON.SET",
            f"annika:tasks:{task['id']}",
            "$",
            json.dumps(task)
        )
        
        # Verify storage
        result = await redis_client.execute_command(
            "JSON.GET",
            f"annika:tasks:{task['id']}",
            "$"
        )
        
        assert result is not None
        retrieved = json.loads(result)[0]
        assert retrieved['id'] == task['id']
        assert retrieved['title'] == task['title']
    
    async def test_partial_update_task(self, redis_client):
        """Test partial field update"""
        task_id = "test-task-002"
        
        # Create initial task
        await redis_client.execute_command(
            "JSON.SET",
            f"annika:tasks:{task_id}",
            "$",
            json.dumps({
                "id": task_id,
                "title": "Initial",
                "status": "not_started"
            })
        )
        
        # Update only status
        await redis_client.execute_command(
            "JSON.SET",
            f"annika:tasks:{task_id}",
            "$.status",
            '"in_progress"'
        )
        
        # Verify
        result_json = await redis_client.execute_command(
            "JSON.GET",
            f"annika:tasks:{task_id}",
            "$"
        )
        result = json.loads(result_json)[0]
        assert result['status'] == 'in_progress'
        assert result['title'] == 'Initial'  # Unchanged
    
    async def test_numeric_increment(self, redis_client):
        """Test incrementing percent_complete"""
        task_id = "test-task-003"
        
        # Create with 0% complete
        await redis_client.execute_command(
            "JSON.SET",
            f"annika:tasks:{task_id}",
            "$",
            json.dumps({
                "id": task_id,
                "percent_complete": 0
            })
        )
        
        # Increment by 25%
        await redis_client.execute_command(
            "JSON.NUMINCRBY",
            f"annika:tasks:{task_id}",
            "$.percent_complete",
            25
        )
        
        # Verify
        result_json = await redis_client.execute_command(
            "JSON.GET",
            f"annika:tasks:{task_id}",
            "$.percent_complete"
        )
        result = json.loads(result_json)
        assert result[0] == 25
    
    async def test_array_operations(self, redis_client):
        """Test appending to arrays (labels, checklist_items)"""
        task_id = "test-task-004"
        
        # Create with empty labels
        await redis_client.execute_command(
            "JSON.SET",
            f"annika:tasks:{task_id}",
            "$",
            json.dumps({
                "id": task_id,
                "labels": []
            })
        )
        
        # Append label
        await redis_client.execute_command(
            "JSON.ARRAPPEND",
            f"annika:tasks:{task_id}",
            "$.labels",
            '"urgent"'
        )
        
        # Verify
        result_json = await redis_client.execute_command(
            "JSON.GET",
            f"annika:tasks:{task_id}",
            "$.labels"
        )
        result = json.loads(result_json)
        assert "urgent" in result[0]
    
    async def test_jsonpath_filtering(self, redis_client):
        """Test JSONPath filtering"""
        # Create multiple tasks
        tasks = [
            {"id": "task-1", "status": "completed"},
            {"id": "task-2", "status": "in_progress"},
            {"id": "task-3", "status": "completed"}
        ]
        
        for task in tasks:
            await redis_client.execute_command(
                "JSON.SET",
                f"annika:tasks:{task['id']}",
                "$",
                json.dumps(task)
            )
        
        # Query completed status
        for task in tasks:
            result_json = await redis_client.execute_command(
                "JSON.GET",
                f"annika:tasks:{task['id']}",
                "$[?(@.status=='completed')]"
            )
            result = json.loads(result_json) if result_json else []
            
            if task['status'] == 'completed':
                assert len(result) > 0
            else:
                assert len(result) == 0
```

### 2. Integration Tests

**Update:** `src/Tests/test_planner_sync_deletion.py`

Add tests for:
- RedisJSON operations in sync workflow
- Partial updates during sync
- Error handling for malformed JSON
- TTL behavior with RedisJSON

### 3. End-to-End Tests

**Update:** `src/test_phase2_comprehensive.py`

Add tests for:
- Full task lifecycle with RedisJSON
- Planner → Annika → Planner round-trip
- Webhook notifications with RedisJSON storage
- Performance benchmarks (string vs RedisJSON)

---

## 📊 Migration Strategy

### Phase 1: Preparation (Week 1)
- [ ] Create test suite for RedisJSON operations
- [ ] Document all current Redis key patterns
- [ ] Create backup scripts for existing data
- [ ] Set up monitoring for Redis operations
- [ ] Review all files for string storage patterns

### Phase 2: Core Adapter Changes (Week 2)
- [ ] Update `annika_task_adapter.py`
- [ ] Update `get_all_annika_tasks()` method
- [ ] Add RedisJSON helper methods
- [ ] Run unit tests
- [ ] Performance benchmark

### Phase 3: HTTP Endpoints (Week 3)
- [ ] Update `http_endpoints.py`
- [ ] Update `endpoints/planner.py`
- [ ] Update `endpoints/tasks_buckets.py`
- [ ] Update `endpoints/agent_tools.py`
- [ ] Integration tests

### Phase 4: Sync Service (Week 4)
- [ ] Update `planner_sync_service_v5.py`
- [ ] Convert all task read operations
- [ ] Convert all task write operations
- [ ] Add partial update optimizations
- [ ] End-to-end sync tests

### Phase 5: Data Migration (Week 5)
- [ ] Create migration script
- [ ] Test migration on dev environment
- [ ] Backup production data
- [ ] Execute migration
- [ ] Verify data integrity

### Phase 6: Optimization (Week 6)
- [ ] Add JSONPath query patterns
- [ ] Implement RediSearch indexes
- [ ] Performance tuning
- [ ] Documentation updates
- [ ] Training materials

---

## 🔄 Data Migration Script

**Create:** `src/scripts/migrate_to_redisjson.py`

```python
"""
Migrate existing task data from string storage to RedisJSON
Run this script ONCE during deployment
"""

import asyncio
import json
import logging
import redis.asyncio as redis
from datetime import datetime

logger = logging.getLogger(__name__)

async def migrate_tasks_to_redisjson():
    """Migrate all tasks to RedisJSON format"""
    
    # Connect to Redis
    client = await redis.Redis(
        host="localhost",
        port=6379,
        password="password",
        decode_responses=True
    )
    
    try:
        # Find all task keys
        cursor = 0
        pattern = "annika:tasks:*"
        migrated_count = 0
        error_count = 0
        
        logger.info("Starting task migration to RedisJSON...")
        
        while True:
            cursor, keys = await client.scan(
                cursor, 
                match=pattern, 
                count=100
            )
            
            for key in keys:
                try:
                    # Check if already RedisJSON
                    key_type = await client.execute_command("JSON.TYPE", key, "$")
                    if key_type:
                        logger.debug(f"Key {key} already RedisJSON, skipping")
                        continue
                    
                    # Get current value (string)
                    raw_value = await client.get(key)
                    if not raw_value:
                        logger.warning(f"Key {key} has no value, skipping")
                        continue
                    
                    # Parse JSON
                    task_data = json.loads(raw_value)
                    
                    # Validate task structure
                    if not isinstance(task_data, dict):
                        logger.error(f"Key {key} is not a dict: {type(task_data)}")
                        error_count += 1
                        continue
                    
                    if 'id' not in task_data:
                        logger.error(f"Key {key} missing 'id' field")
                        error_count += 1
                        continue
                    
                    # Get TTL if exists
                    ttl = await client.ttl(key)
                    
                    # Backup to temporary key
                    backup_key = f"{key}:backup:{datetime.utcnow().timestamp()}"
                    await client.set(backup_key, raw_value)
                    await client.expire(backup_key, 86400)  # 24 hour backup
                    
                    # Delete old key
                    await client.delete(key)
                    
                    # Create as RedisJSON
                    await client.execute_command(
                        "JSON.SET",
                        key,
                        "$",
                        json.dumps(task_data)
                    )
                    
                    # Restore TTL if existed
                    if ttl > 0:
                        await client.expire(key, ttl)
                    
                    migrated_count += 1
                    
                    if migrated_count % 100 == 0:
                        logger.info(f"Migrated {migrated_count} tasks...")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in key {key}: {e}")
                    error_count += 1
                except Exception as e:
                    logger.error(f"Error migrating key {key}: {e}")
                    error_count += 1
            
            if cursor == 0:
                break
        
        logger.info(
            f"Migration complete! "
            f"Migrated: {migrated_count}, "
            f"Errors: {error_count}"
        )
        
        return {
            "migrated": migrated_count,
            "errors": error_count
        }
        
    finally:
        await client.close()


async def verify_migration():
    """Verify all tasks are now RedisJSON"""
    client = await redis.Redis(
        host="localhost",
        port=6379,
        password="password",
        decode_responses=True
    )
    
    try:
        cursor = 0
        pattern = "annika:tasks:*"
        json_count = 0
        string_count = 0
        
        while True:
            cursor, keys = await client.scan(
                cursor, 
                match=pattern, 
                count=100
            )
            
            for key in keys:
                # Skip backup keys
                if ":backup:" in key:
                    continue
                
                # Check type
                try:
                    key_type = await client.execute_command("JSON.TYPE", key, "$")
                    if key_type:
                        json_count += 1
                    else:
                        string_count += 1
                        logger.warning(f"Key {key} is still string storage")
                except Exception:
                    string_count += 1
                    logger.warning(f"Key {key} is not RedisJSON")
            
            if cursor == 0:
                break
        
        logger.info(
            f"Verification complete! "
            f"RedisJSON: {json_count}, "
            f"String: {string_count}"
        )
        
        return {
            "redisjson": json_count,
            "string": string_count
        }
        
    finally:
        await client.close()


async def rollback_migration():
    """Rollback migration using backup keys"""
    client = await redis.Redis(
        host="localhost",
        port=6379,
        password="password",
        decode_responses=True
    )
    
    try:
        cursor = 0
        pattern = "annika:tasks:*:backup:*"
        restored_count = 0
        
        logger.info("Rolling back migration...")
        
        while True:
            cursor, keys = await client.scan(
                cursor, 
                match=pattern, 
                count=100
            )
            
            for backup_key in keys:
                try:
                    # Extract original key
                    original_key = backup_key.split(":backup:")[0]
                    
                    # Get backup value
                    backup_value = await client.get(backup_key)
                    if not backup_value:
                        continue
                    
                    # Restore original
                    await client.delete(original_key)
                    await client.set(original_key, backup_value)
                    
                    restored_count += 1
                    
                except Exception as e:
                    logger.error(f"Error restoring {backup_key}: {e}")
            
            if cursor == 0:
                break
        
        logger.info(f"Rollback complete! Restored {restored_count} keys")
        
    finally:
        await client.close()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate_to_redisjson.py migrate")
        print("  python migrate_to_redisjson.py verify")
        print("  python migrate_to_redisjson.py rollback")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "migrate":
        result = asyncio.run(migrate_tasks_to_redisjson())
        print(f"\nMigration Results: {result}")
    
    elif command == "verify":
        result = asyncio.run(verify_migration())
        print(f"\nVerification Results: {result}")
    
    elif command == "rollback":
        confirm = input(
            "This will rollback all migrations. Are you sure? (yes/no): "
        )
        if confirm.lower() == "yes":
            asyncio.run(rollback_migration())
        else:
            print("Rollback cancelled")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
```

**Usage:**
```powershell
# Step 1: Migrate
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe migrate_to_redisjson.py migrate

# Step 2: Verify
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe migrate_to_redisjson.py verify

# If problems: Rollback
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe migrate_to_redisjson.py rollback
```

---

## ⚠️ Risk Assessment

### High Risk Areas
1. **Data Loss**: Improper migration could lose task data
   - **Mitigation**: Backup all keys before migration, 24-hour rollback window
   
2. **Performance Impact**: RedisJSON operations may have different performance characteristics
   - **Mitigation**: Benchmark before/after, use partial updates where possible
   
3. **Compatibility**: Existing code expecting string format will break
   - **Mitigation**: Comprehensive testing, gradual rollout

4. **Concurrent Operations**: Race conditions during migration
   - **Mitigation**: Migrate during low-traffic window, use Redis transactions

### Medium Risk Areas
1. **TTL Preservation**: Task TTLs must be maintained
   - **Mitigation**: Migration script explicitly handles TTL
   
2. **Schema Validation**: RedisJSON enforces structure
   - **Mitigation**: Validate all task data before migration
   
3. **Memory Usage**: RedisJSON may use more memory
   - **Mitigation**: Monitor Redis memory, adjust maxmemory if needed

---

## 📈 Success Metrics

### Functional Metrics
- [ ] 100% of tasks stored as RedisJSON
- [ ] Zero data loss during migration
- [ ] All tests passing
- [ ] No string GET/SET operations remaining

### Performance Metrics
- [ ] Task read latency < 5ms (p95)
- [ ] Task write latency < 10ms (p95)
- [ ] Partial update operations < 3ms (p95)
- [ ] Memory usage increase < 10%

### Code Quality Metrics
- [ ] No mixed storage patterns
- [ ] Test coverage > 90%
- [ ] All linter warnings resolved
- [ ] Documentation updated

---

## 🔗 Related Resources

### Documentation
- [RedisJSON Documentation](https://redis.io/docs/stack/json/)
- [JSONPath Syntax](https://goessner.net/articles/JsonPath/)
- [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc) - Annika RedisJSON patterns
- [@redis-component-keys-map.mdc](mdc:.cursor/rules/redis-component-keys-map.mdc) - Key patterns
- [@redis-master-manager.mdc](mdc:.cursor/rules/redis-master-manager.mdc) - Connection patterns

### Code References
- `remote-mcp-functions-python/src/annika_task_adapter.py` - Task adapter
- `remote-mcp-functions-python/src/planner_sync_service_v5.py` - Sync service
- `Annika_2.0/Redis_Master_Manager_Client.py` - Redis client (reference)

---

## ✅ Implementation Checklist

### Pre-Implementation
- [ ] Read this document completely
- [ ] Review all referenced .mdc rules
- [ ] Set up test environment
- [ ] Create backup of production Redis
- [ ] Schedule maintenance window

### Implementation
- [ ] Phase 1: Preparation (Tests, backup, monitoring)
- [ ] Phase 2: Core adapter changes
- [ ] Phase 3: HTTP endpoints
- [ ] Phase 4: Sync service
- [ ] Phase 5: Data migration
- [ ] Phase 6: Optimization

### Post-Implementation
- [ ] Run migration script
- [ ] Verify all tasks migrated
- [ ] Monitor performance metrics
- [ ] Update documentation
- [ ] Clean up backup keys (after 24 hours)
- [ ] Archive migration scripts

---

## 📞 Support & Questions

### Key Decision Points Requiring User Input

1. **Migration Timing**: When should production migration occur?
   - Recommendation: Off-peak hours, weekend preferred
   
2. **Rollback Policy**: How long to keep backup keys?
   - Recommendation: 24-48 hours minimum
   
3. **RediSearch**: Should we add search indexes immediately or later?
   - Recommendation: Later (Phase 6), after core migration stable
   
4. **Performance Threshold**: What latency is acceptable?
   - Current: Need baseline measurements
   - Target: <10ms for all operations

---

**Document Status:** ✅ Complete and ready for review  
**Next Steps:** Review with team → Approve migration plan → Begin Phase 1

