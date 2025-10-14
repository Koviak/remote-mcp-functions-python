# RedisJSON Quick Reference for MS-MCP Task Management

**Quick access guide for developers working on the RedisJSON conversion**

---

## 🎯 Core Principle

**ALL task storage MUST use RedisJSON**. No exceptions.

```python
# ❌ FORBIDDEN - Plain string storage
await redis.set(f"annika:tasks:{id}", json.dumps(task))
raw = await redis.get(f"annika:tasks:{id}")

# ✅ REQUIRED - RedisJSON storage  
await redis.execute_command("JSON.SET", f"annika:tasks:{id}", "$", json.dumps(task))
task_json = await redis.execute_command("JSON.GET", f"annika:tasks:{id}", "$")
```

---

## 📋 Quick Conversion Patterns

### Pattern 1: Full Document Write

**Before:**
```python
await redis.set(key, json.dumps(data))
```

**After:**
```python
await redis.execute_command("JSON.SET", key, "$", json.dumps(data))
```

---

### Pattern 2: Full Document Read

**Before:**
```python
raw = await redis.get(key)
if raw:
    data = json.loads(raw)
```

**After:**
```python
data_json = await redis.execute_command("JSON.GET", key, "$")
if data_json:
    data_list = json.loads(data_json)  # JSONPath returns array
    data = data_list[0] if data_list else None
```

---

### Pattern 3: With TTL (SETEX)

**Before:**
```python
await redis.setex(key, 3600, json.dumps(data))
```

**After:**
```python
await redis.execute_command("JSON.SET", key, "$", json.dumps(data))
await redis.expire(key, 3600)
```

---

### Pattern 4: Partial Field Update (NEW!)

**Update single field:**
```python
await redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{id}",
    "$.status",
    '"completed"'  # Must be valid JSON string
)
```

**Update timestamp:**
```python
await redis.execute_command(
    "JSON.SET",
    f"annika:tasks:{id}",
    "$.updated_at",
    f'"{datetime.utcnow().isoformat()}Z"'
)
```

---

### Pattern 5: Numeric Operations

**Increment percent complete:**
```python
await redis.execute_command(
    "JSON.NUMINCRBY",
    f"annika:tasks:{id}",
    "$.percent_complete",
    10  # Add 10%
)
```

---

### Pattern 6: Array Operations

**Append to array:**
```python
await redis.execute_command(
    "JSON.ARRAPPEND",
    f"annika:tasks:{id}",
    "$.labels",
    '"urgent"'  # Must be valid JSON
)
```

**Insert at position:**
```python
await redis.execute_command(
    "JSON.ARRINSERT",
    f"annika:tasks:{id}",
    "$.checklist_items",
    0,  # Index
    json.dumps({"item": "New task", "complete": False})
)
```

---

## 🔍 JSONPath Query Patterns

### Get Specific Field

```python
# Get only the status field
status_json = await redis.execute_command(
    "JSON.GET",
    f"annika:tasks:{id}",
    "$.status"
)
status = json.loads(status_json)[0] if status_json else None
```

### Filter by Condition

```python
# Get task if status is completed
result_json = await redis.execute_command(
    "JSON.GET",
    f"annika:tasks:{id}",
    "$[?(@.status=='completed')]"
)
result = json.loads(result_json) if result_json else []
```

### Multiple Fields

```python
# Get multiple fields
fields_json = await redis.execute_command(
    "JSON.GET",
    f"annika:tasks:{id}",
    "$.title",
    "$.status",
    "$.due_date"
)
```

---

## 🗂️ Key Files to Update

| File | Changes | Priority |
|------|---------|----------|
| `src/annika_task_adapter.py` | Lines 292-295, 229-310 | **CRITICAL** |
| `src/http_endpoints.py` | Task CRUD operations | **CRITICAL** |
| `src/planner_sync_service_v5.py` | All task reads/writes | **CRITICAL** |
| `src/endpoints/planner.py` | Task operations | HIGH |
| `src/endpoints/tasks_buckets.py` | Task operations | HIGH |
| `src/endpoints/agent_tools.py` | Agent task creation | HIGH |

---

## ⚠️ Common Pitfalls

### 1. JSONPath Returns Arrays

**Problem:**
```python
data = await redis.execute_command("JSON.GET", key, "$")
print(data['id'])  # ❌ ERROR! data is string, not dict
```

**Solution:**
```python
data_json = await redis.execute_command("JSON.GET", key, "$")
data_list = json.loads(data_json)
data = data_list[0]  # ✅ Extract first element
print(data['id'])
```

---

### 2. JSON Value Formatting

**Problem:**
```python
await redis.execute_command("JSON.SET", key, "$.status", "completed")
# ❌ ERROR! Must be valid JSON string
```

**Solution:**
```python
await redis.execute_command("JSON.SET", key, "$.status", '"completed"')
# ✅ Properly quoted JSON string
```

---

### 3. Checking Existence

**Problem:**
```python
if await redis.get(key):  # ❌ Won't work with RedisJSON
```

**Solution:**
```python
# Option 1: Try to get type
key_type = await redis.execute_command("JSON.TYPE", key, "$")
if key_type:
    # Key exists

# Option 2: Try to get and check result
result = await redis.execute_command("JSON.GET", key, "$")
if result:
    # Key exists and has data
```

---

### 4. TTL with RedisJSON

**Problem:**
```python
await redis.execute_command("JSON.SET", key, "$", data, "EX", 3600)
# ❌ JSON.SET doesn't support EX parameter
```

**Solution:**
```python
await redis.execute_command("JSON.SET", key, "$", data)
await redis.expire(key, 3600)  # ✅ Separate expire command
```

---

## 🧪 Testing Commands

### Manual Testing in Redis CLI

```bash
# Enter Redis container
docker exec -it annika_20-redis-1 redis-cli -a password

# Create task
JSON.SET annika:tasks:test-001 $ '{"id":"test-001","title":"Test","status":"not_started"}'

# Read task
JSON.GET annika:tasks:test-001 $

# Update field
JSON.SET annika:tasks:test-001 $.status '"completed"'

# Read specific field
JSON.GET annika:tasks:test-001 $.status

# Check type
JSON.TYPE annika:tasks:test-001 $

# Delete
DEL annika:tasks:test-001
```

---

## 🔄 Migration Checklist

**Before making changes:**
- [ ] Read full conversion plan: `REDISJSON_CONVERSION_PLAN.md`
- [ ] Review [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc)
- [ ] Backup Redis data
- [ ] Create test cases

**During implementation:**
- [ ] Replace ALL `redis.set()` with `JSON.SET`
- [ ] Replace ALL `redis.get()` with `JSON.GET`
- [ ] Handle JSONPath array returns correctly
- [ ] Update error handling
- [ ] Add tests for new patterns

**After implementation:**
- [ ] Run test suite
- [ ] Verify no string operations remain
- [ ] Check performance metrics
- [ ] Update documentation

---

## 📞 Need Help?

**Common Questions:**

**Q: Why is my JSON.GET returning None?**
A: Check if key exists using `JSON.TYPE`. The key might not exist or might be plain string storage.

**Q: How do I update nested fields?**
A: Use JSONPath: `$.parent.child` for nested objects.

**Q: Can I use transactions with RedisJSON?**
A: Yes! Use MULTI/EXEC as normal. RedisJSON commands work within transactions.

**Q: What about performance?**
A: RedisJSON is generally faster for partial updates. Benchmark specific use cases.

---

## 📚 Full Documentation

- **Complete Plan**: [REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md)
- **Redis Master Manager**: [@redis-master-manager.mdc](mdc:.cursor/rules/redis-master-manager.mdc)
- **RedisJSON Operations**: [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc)
- **Key Patterns**: [@redis-component-keys-map.mdc](mdc:.cursor/rules/redis-component-keys-map.mdc)
- **Official RedisJSON Docs**: https://redis.io/docs/stack/json/

---

**Last Updated:** October 14, 2025  
**Status:** Ready for implementation

