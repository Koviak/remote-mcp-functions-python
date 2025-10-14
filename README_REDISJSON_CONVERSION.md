# RedisJSON Conversion Project

**Convert MS-MCP Server to RedisJSON-Only Task Management**

---

## 🎯 Quick Start

**New to this project?** Start here:

1. **Read the overview** (15 minutes)  
   → [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

2. **Learn the patterns** (30 minutes)  
   → [REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md)

3. **Check the full plan** (when needed)  
   → [REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md)

4. **Track your work**  
   → [REDISJSON_IMPLEMENTATION_CHECKLIST.md](./REDISJSON_IMPLEMENTATION_CHECKLIST.md)

**Complete navigation:** [REDISJSON_INDEX.md](./REDISJSON_INDEX.md)

---

## 📋 What Is This?

A comprehensive plan to convert the MS-MCP server from mixed Redis storage patterns (plain strings + RedisJSON) to **RedisJSON-only** for all task management operations.

### Current Problem

```python
# ❌ Current: Mixed patterns
await redis.set(f"annika:tasks:{id}", json.dumps(task))  # Plain string
await redis.execute_command("JSON.SET", key, "$", data)  # RedisJSON
```

### Target Solution

```python
# ✅ Target: RedisJSON only
await redis.execute_command("JSON.SET", f"annika:tasks:{id}", "$", json.dumps(task))
task_json = await redis.execute_command("JSON.GET", f"annika:tasks:{id}", "$")
```

---

## 🎯 Why?

1. **OpenAI Compatibility**: Structured outputs work directly with RedisJSON
2. **Atomic Updates**: Change single fields without full rewrites
3. **Query Support**: JSONPath filtering and RediSearch integration
4. **Type Safety**: JSON structure validation at storage time
5. **Performance**: Faster partial updates

---

## 📊 Project Scope

| Metric | Value |
|--------|-------|
| **Timeline** | 6 weeks |
| **Files** | 6 core files |
| **Lines Changed** | ~500-800 lines |
| **Risk Level** | Medium (with mitigation) |
| **Data Loss Tolerance** | Zero |

---

## 🗓️ Timeline

```
Week 1: Preparation
├─ Create test suite
├─ Set up monitoring
├─ Document patterns

Week 2: Core Adapter
├─ Update annika_task_adapter.py
├─ Add helper methods
├─ Unit tests
└─ Performance benchmark

Week 3: HTTP Endpoints
├─ Update http_endpoints.py
├─ Update endpoint modules
├─ Integration tests
└─ Verify no regressions

Week 4: Sync Service
├─ Update planner_sync_service_v5.py
├─ Optimize with partial updates
├─ End-to-end tests
└─ Performance tuning

Week 5: Migration
├─ Run migration script
├─ Verify data integrity
├─ Monitor production
└─ Keep 24hr rollback ready

Week 6: Optimization
├─ Add query patterns
├─ RediSearch integration
├─ Documentation updates
└─ Final verification
```

---

## 📚 Documentation

### 1. [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)
**For:** Executives, Project Managers, All stakeholders  
**Time:** 15 minutes  
**Contains:** Overview, timeline, risks, success metrics

### 2. [REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md)
**For:** Developers (active coding)  
**Time:** 30 minutes  
**Contains:** Code patterns, examples, troubleshooting

### 3. [REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md)
**For:** Architects, Technical Leads  
**Time:** 2 hours  
**Contains:** Complete technical specification

### 4. [REDISJSON_IMPLEMENTATION_CHECKLIST.md](./REDISJSON_IMPLEMENTATION_CHECKLIST.md)
**For:** Developers, QA  
**Time:** Reference  
**Contains:** Task tracking and verification

### 5. [REDISJSON_INDEX.md](./REDISJSON_INDEX.md)
**For:** Everyone  
**Time:** 5 minutes  
**Contains:** Navigation and learning paths

---

## 🔧 Key Changes

### Files Being Updated

**CRITICAL Priority:**
1. `src/annika_task_adapter.py` - Lines 292-295, 229-310
2. `src/http_endpoints.py` - Task CRUD operations  
3. `src/planner_sync_service_v5.py` - All task reads/writes

**HIGH Priority:**
4. `src/endpoints/planner.py` - Task operations
5. `src/endpoints/tasks_buckets.py` - Bucket operations
6. `src/endpoints/agent_tools.py` - Agent task creation

### Redis Keys Affected

- `annika:tasks:{task_id}` - Primary task storage
- `annika:planner:tasks:{task_id}` - Temporary Planner cache
- All related task read/write operations

---

## ✅ Success Criteria

### Functional
- [ ] 100% of tasks stored as RedisJSON
- [ ] Zero data loss
- [ ] All tests passing
- [ ] No string operations remaining

### Performance
- [ ] Task read < 5ms (p95)
- [ ] Task write < 10ms (p95)
- [ ] Partial updates < 3ms (p95)
- [ ] Memory increase < 10%

### Code Quality
- [ ] No mixed patterns
- [ ] Test coverage > 90%
- [ ] Linter clean
- [ ] Documentation complete

---

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Data loss | Full backup + 24hr rollback window |
| Performance issues | Benchmark + optimization phase |
| Breaking changes | Comprehensive testing + gradual rollout |
| Memory increase | Monitor + adjust Redis settings |

---

## 🚀 Getting Started

### For Developers

**Step 1: Read Documentation**
```bash
# Start with overview
cat IMPLEMENTATION_SUMMARY.md

# Learn patterns
cat REDISJSON_QUICK_REFERENCE.md

# Get checklist
cat REDISJSON_IMPLEMENTATION_CHECKLIST.md
```

**Step 2: Set Up Environment**
```powershell
# Activate environment
conda activate Annika_2.1

# Backup Redis
docker exec annika_20-redis-1 redis-cli -a password SAVE

# Run tests
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/ -v
```

**Step 3: Start Converting**
- Pick a file from priority list
- Follow patterns in QUICK_REFERENCE
- Write tests first (TDD)
- Update checklist

### For Managers

**Step 1: Review Timeline**
- Read IMPLEMENTATION_SUMMARY.md
- Understand 6-week timeline
- Schedule Week 5 maintenance window

**Step 2: Allocate Resources**
- 2-3 developers full-time
- 1 DevOps engineer (migration support)
- QA resources for testing

**Step 3: Monitor Progress**
- Weekly status updates
- Track success criteria
- Review risk assessment

---

## 📞 Support

**Questions?**
1. Check [REDISJSON_INDEX.md](./REDISJSON_INDEX.md) for navigation
2. Review [REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md) for patterns
3. Consult [REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md) for details

**Issues?**
1. Check Common Pitfalls in QUICK_REFERENCE
2. Review Related .mdc Rules
3. Ask team lead

---

## 🔗 Related Resources

### Internal Rules (Annika 2.0)
- [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc) - RedisJSON operations
- [@redis-master-manager.mdc](mdc:.cursor/rules/redis-master-manager.mdc) - Connection patterns
- [@redis-component-keys-map.mdc](mdc:.cursor/rules/redis-component-keys-map.mdc) - Key patterns

### External Resources
- [RedisJSON Documentation](https://redis.io/docs/stack/json/)
- [JSONPath Syntax](https://goessner.net/articles/JsonPath/)
- [Redis CLI Reference](https://redis.io/docs/ui/cli/)

### Project Files
- [agents.md](./agents.md) - Repository guide
- [bug_fix_MS-MCP.md](./bug_fix_MS-MCP.md) - Change log
- [src/agents.md](./src/agents.md) - Source directory guide

---

## 📈 Progress Tracking

**Current Phase:** Planning Complete

**Next Steps:**
1. [ ] Review and approve documentation
2. [ ] Schedule kickoff meeting
3. [ ] Begin Phase 1: Preparation
4. [ ] Set up monitoring and backups

**Weekly Updates:** Track in [REDISJSON_IMPLEMENTATION_CHECKLIST.md](./REDISJSON_IMPLEMENTATION_CHECKLIST.md)

---

## 🎉 Quick Wins

**After conversion you'll get:**

✅ **Immediate:**
- Consistent storage pattern
- OpenAI compatibility
- Better error messages

✅ **Short-term (Weeks 1-4):**
- Faster partial updates
- Clearer code
- Easier debugging

✅ **Long-term (Months):**
- Query capabilities
- Search integration
- Better scalability

---

**Project Status:** ✅ Documentation Complete  
**Created:** October 14, 2025  
**Updated:** October 14, 2025  
**Version:** 1.0  

**Ready to start?** → [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

