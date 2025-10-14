# RedisJSON Conversion - Implementation Checklist

**Use this checklist to track your progress during the conversion**

---

## 📋 Pre-Implementation Checklist

### Documentation Review
- [ ] Read IMPLEMENTATION_SUMMARY.md (15 min)
- [ ] Read REDISJSON_QUICK_REFERENCE.md (30 min)
- [ ] Skim REDISJSON_CONVERSION_PLAN.md (sections relevant to your work)
- [ ] Review [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc)
- [ ] Review [@redis-component-keys-map.mdc](mdc:.cursor/rules/redis-component-keys-map.mdc)

### Environment Setup
- [ ] Backup Redis data: `docker exec annika_20-redis-1 redis-cli -a password SAVE`
- [ ] Backup copied to safe location with timestamp
- [ ] Test environment verified working
- [ ] Redis CLI access confirmed
- [ ] Conda environment activated: `conda activate Annika_2.1`

### Baseline Measurements
- [ ] Run existing test suite and record results
- [ ] Benchmark current task read latency
- [ ] Benchmark current task write latency
- [ ] Document current memory usage
- [ ] Record baseline error rate

---

## 🔧 Phase 1: Preparation (Week 1)

### Test Suite Creation
- [ ] Create `src/Tests/test_redisjson_conversion.py`
- [ ] Test: Create task with JSON.SET
- [ ] Test: Read task with JSON.GET
- [ ] Test: Partial field update
- [ ] Test: Numeric increment (NUMINCRBY)
- [ ] Test: Array operations (ARRAPPEND)
- [ ] Test: JSONPath filtering
- [ ] Test: TTL preservation
- [ ] Test: Error handling for malformed JSON
- [ ] All new tests passing

### Documentation
- [ ] Document all current Redis key patterns
- [ ] List all files using string storage
- [ ] Create file-by-file conversion plan
- [ ] Document rollback procedures

### Monitoring Setup
- [ ] Redis monitoring dashboard configured
- [ ] Performance tracking enabled
- [ ] Error alerting configured
- [ ] Log rotation verified

---

## 🔄 Phase 2: Core Adapter Changes (Week 2)

### File: `src/annika_task_adapter.py`

**Lines 286-308: `get_all_annika_tasks()` method**
- [ ] Replace `redis.get()` with `JSON.GET`
- [ ] Handle JSONPath array returns correctly
- [ ] Update error handling
- [ ] Add logging for migration tracking
- [ ] Test with existing tasks
- [ ] Test with empty database
- [ ] Test with malformed data
- [ ] Performance benchmark

**Add Helper Methods**
- [ ] Create `_redis_json_get()` helper
- [ ] Create `_redis_json_set()` helper
- [ ] Create `_redis_json_update()` helper for partial updates
- [ ] Document all helper methods
- [ ] Unit tests for helpers

**Testing**
- [ ] All existing tests still pass
- [ ] New RedisJSON tests pass
- [ ] Integration tests pass
- [ ] No performance regression (< 10% slower)

---

## 🌐 Phase 3: HTTP Endpoints (Week 3)

### File: `src/http_endpoints.py`

**Task Creation Endpoint (`create_agent_task_http`)**
- [ ] Find all `redis.set(f"annika:tasks:` calls
- [ ] Replace with `JSON.SET` operations
- [ ] Update response handling
- [ ] Add JSON validation
- [ ] Test creation with valid data
- [ ] Test creation with invalid data
- [ ] Test error responses

**Task Retrieval Endpoints**
- [ ] Find all `redis.get(f"annika:tasks:` calls
- [ ] Replace with `JSON.GET` operations
- [ ] Handle JSONPath array returns
- [ ] Update response serialization
- [ ] Test retrieval of existing tasks
- [ ] Test retrieval of non-existent tasks

**Temporary Planner Cache**
- [ ] Find all `redis.setex(f"annika:planner:tasks:` calls
- [ ] Replace with `JSON.SET` + `expire()`
- [ ] Verify TTL preservation
- [ ] Test cache expiration

### File: `src/endpoints/planner.py`
- [ ] Convert all task reads to JSON.GET
- [ ] Convert all task writes to JSON.SET
- [ ] Update error handling
- [ ] Test all planner endpoints
- [ ] Performance benchmark

### File: `src/endpoints/tasks_buckets.py`
- [ ] Convert bucket association updates
- [ ] Convert task list retrievals
- [ ] Update JSONPath queries
- [ ] Test bucket operations

### File: `src/endpoints/agent_tools.py`
- [ ] Convert agent task creation
- [ ] Convert task status updates to partial updates
- [ ] Convert task assignment updates
- [ ] Test all agent tool operations

**Phase 3 Verification**
- [ ] All HTTP endpoint tests passing
- [ ] Integration tests passing
- [ ] No regression in response times
- [ ] Error handling working correctly

---

## 🔁 Phase 4: Sync Service (Week 4)

### File: `src/planner_sync_service_v5.py`

**Task Read Operations**
- [ ] Find all `redis.get(f"annika:tasks:` in sync service
- [ ] Replace with `JSON.GET` operations
- [ ] Update `_sync_from_planner_to_annika()`
- [ ] Update `_monitor_annika_changes()`
- [ ] Update `_pending_queue_worker()`
- [ ] Handle JSONPath array returns
- [ ] Test reads during sync

**Task Write Operations**
- [ ] Find all `redis.set(f"annika:tasks:` in sync service
- [ ] Replace with `JSON.SET` operations
- [ ] Update `_create_in_planner()`
- [ ] Update `_update_task()`
- [ ] Update `_queue_upload()`
- [ ] Test writes during sync

**Optimization: Partial Updates**
- [ ] Identify operations that only update single fields
- [ ] Replace full document writes with JSONPath updates
- [ ] Add status update optimization
- [ ] Add timestamp update optimization
- [ ] Add percent_complete update optimization
- [ ] Benchmark improvement

**Sync Testing**
- [ ] Test Annika → Planner sync
- [ ] Test Planner → Annika sync
- [ ] Test bidirectional sync
- [ ] Test conflict resolution
- [ ] Test webhook-driven sync
- [ ] Test rate limiting with RedisJSON
- [ ] Test error recovery

**Phase 4 Verification**
- [ ] All sync tests passing
- [ ] No data loss during sync
- [ ] Performance improvement documented
- [ ] End-to-end tests passing

---

## 📦 Phase 5: Data Migration (Week 5)

### Migration Script Setup
- [ ] Create `src/scripts/migrate_to_redisjson.py`
- [ ] Implement `migrate_tasks_to_redisjson()`
- [ ] Implement `verify_migration()`
- [ ] Implement `rollback_migration()`
- [ ] Test script on dev environment
- [ ] Document script usage

### Pre-Migration
- [ ] **CRITICAL**: Full Redis backup taken
- [ ] Backup verified readable
- [ ] Backup stored in safe location
- [ ] Maintenance window scheduled
- [ ] Team notified of migration
- [ ] Rollback procedure tested

### Migration Execution
- [ ] Stop all services that write tasks
- [ ] Run migration script: `python migrate_to_redisjson.py migrate`
- [ ] Monitor migration progress
- [ ] Record migration statistics
- [ ] Run verification: `python migrate_to_redisjson.py verify`
- [ ] Verify 100% RedisJSON conversion
- [ ] Spot check random tasks for data integrity
- [ ] Check TTLs preserved correctly

### Post-Migration Verification
- [ ] Restart all services
- [ ] Run full test suite
- [ ] Test task creation
- [ ] Test task updates
- [ ] Test task deletion
- [ ] Test Planner sync
- [ ] Monitor for errors (30 minutes)
- [ ] Monitor performance metrics
- [ ] Verify no data loss

### Rollback (If Needed)
- [ ] Stop all services
- [ ] Run rollback script: `python migrate_to_redisjson.py rollback`
- [ ] Verify rollback successful
- [ ] Restart services with old code
- [ ] Document rollback reason
- [ ] Plan remediation

---

## 🚀 Phase 6: Optimization (Week 6)

### JSONPath Query Patterns
- [ ] Document common query patterns
- [ ] Add status filtering examples
- [ ] Add date range filtering examples
- [ ] Add assignment filtering examples
- [ ] Create query helper functions
- [ ] Test all query patterns

### RediSearch Integration (Optional)
- [ ] Create search index for tasks
- [ ] Test search by title
- [ ] Test search by status
- [ ] Test search by priority
- [ ] Test search by assignment
- [ ] Test search by date
- [ ] Benchmark search performance

### Performance Tuning
- [ ] Identify bottlenecks
- [ ] Optimize hot paths
- [ ] Add caching where appropriate
- [ ] Tune Redis memory settings if needed
- [ ] Document optimizations
- [ ] Measure improvement

### Documentation Updates
- [ ] Update all .mdc rules
- [ ] Update agents.md
- [ ] Create migration runbook
- [ ] Document new patterns
- [ ] Create training materials

---

## ✅ Final Verification

### Functional Verification
- [ ] 100% of tasks stored as RedisJSON
- [ ] Zero data loss confirmed
- [ ] All tests passing (100%)
- [ ] No string GET/SET operations remaining
- [ ] All features working correctly

### Performance Verification
- [ ] Task read latency < 5ms (p95)
- [ ] Task write latency < 10ms (p95)
- [ ] Partial updates < 3ms (p95)
- [ ] Memory usage increase < 10%
- [ ] No performance regressions

### Code Quality Verification
- [ ] No mixed storage patterns
- [ ] Test coverage > 90%
- [ ] All linter warnings resolved
- [ ] Documentation complete and accurate
- [ ] Code review passed

### Cleanup
- [ ] Remove backup keys (after 24-48 hours)
- [ ] Archive migration scripts
- [ ] Remove diagnostic files
- [ ] Update monitoring dashboards
- [ ] Close migration tickets

---

## 🎯 Success Metrics

**Record final metrics:**

```
Migration Statistics:
├─ Tasks migrated: ___ / ___
├─ Migration time: ___ minutes
├─ Errors encountered: ___
├─ Rollbacks needed: ___
└─ Data loss: 0 (required)

Performance Metrics:
├─ Read latency (p95): ___ ms (target: < 5ms)
├─ Write latency (p95): ___ ms (target: < 10ms)
├─ Partial update latency (p95): ___ ms (target: < 3ms)
├─ Memory increase: ___% (target: < 10%)
└─ Test suite time: ___ seconds (vs baseline: ___ seconds)

Code Quality Metrics:
├─ Files changed: ___
├─ Lines changed: ___
├─ Tests added: ___
├─ Test coverage: ___%
└─ Linter warnings: 0 (required)
```

---

## 📞 Emergency Contacts

**If you encounter critical issues:**

1. **Data Loss**: STOP immediately and execute rollback
2. **Performance Issues**: Document and escalate to team lead
3. **Test Failures**: Do not proceed to next phase
4. **Migration Failures**: Review logs, attempt rollback if needed

**Resources:**
- Migration Plan: [REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md)
- Quick Reference: [REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md)
- Redis Rules: [@redis-json.mdc](mdc:.cursor/rules/redis-json.mdc)

---

## 📝 Notes Section

**Use this space to track issues, decisions, and learnings:**

### Issues Encountered
```
Date: ___________
Issue: ___________________________________________
Resolution: _______________________________________
```

### Decisions Made
```
Date: ___________
Decision: _________________________________________
Rationale: ________________________________________
```

### Performance Notes
```
Date: ___________
Observation: ______________________________________
Action Taken: _____________________________________
```

### Lessons Learned
```
What went well: ___________________________________
What could improve: _______________________________
Recommendations: __________________________________
```

---

**Checklist Version:** 1.0  
**Last Updated:** October 14, 2025  
**Next Review:** End of Phase 6

---

## 🎉 Completion Certificate

**When all items are checked:**

```
✅ RedisJSON Conversion Complete

Project: MS-MCP Server RedisJSON Conversion
Completed By: _________________________
Date: _________________________________
Total Time: ___________________________
Final Status: ☐ Success ☐ Success with notes ☐ Partial

Key Achievements:
- ___________________________________
- ___________________________________
- ___________________________________

Signature: ____________________________
```

---

**Print this checklist and keep it handy during implementation!**

