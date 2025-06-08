# Planner Sync Download Fix Summary

## The Problem

The Annika-Planner sync service was successfully **uploading** tasks from Redis to MS Planner, but was **not downloading** tasks from Planner back to Redis.

### Root Cause

The sync service was only checking personal plans via `/me/planner/plans`, which returned only:
- **Annika_AGI** plan with **0 tasks**

However, tasks were actually being uploaded to **group plans** such as:
- **The Bridge/Annika** - 10 tasks
- **Firefly/Annika AGI Tasks** - 75 tasks
- Various other group plans with hundreds of tasks

## The Fix

Modified `planner_sync_service_v2.py` in the `_download_planner_changes()` method to:

1. **Check personal plans** via `/me/planner/plans` (as before)
2. **Additionally check all group plans** by:
   - Getting all groups via `/me/memberOf`
   - For each group, getting its plans via `/groups/{group_id}/planner/plans`
   - Combining all plans into a single list to check

## Code Changes

```python
# Before: Only checked personal plans
response = requests.get(f"{GRAPH_API_ENDPOINT}/me/planner/plans", ...)
plans = response.json().get("value", [])

# After: Checks both personal AND group plans
all_plans = []

# Get personal plans
response = requests.get(f"{GRAPH_API_ENDPOINT}/me/planner/plans", ...)
if response.status_code == 200:
    personal_plans = response.json().get("value", [])
    all_plans.extend(personal_plans)

# Get group plans
response = requests.get(f"{GRAPH_API_ENDPOINT}/me/memberOf", ...)
if response.status_code == 200:
    groups = response.json().get("value", [])
    for item in groups:
        if item.get("@odata.type") == "#microsoft.graph.group":
            group_id = item.get("id")
            plans_resp = requests.get(f"{GRAPH_API_ENDPOINT}/groups/{group_id}/planner/plans", ...)
            if plans_resp.status_code == 200:
                group_plans = plans_resp.json().get("value", [])
                all_plans.extend(group_plans)

# Now check ALL plans for tasks
for plan in all_plans:
    await self._check_plan_tasks(plan["id"], headers)
```

## Impact

With this fix, the sync service will now:
- Find and download tasks from **all accessible plans** (not just personal ones)
- Properly sync tasks created by humans in group plans like "The Bridge/Annika"
- Create corresponding tasks in Redis for agent consumption
- Complete the bidirectional sync loop

## Next Steps

1. Restart the sync service with the updated code
2. The service will now check ~20+ plans instead of just 1
3. Any new tasks created by humans in Planner will be downloaded to Redis
4. Agents will see these tasks in their conscious_state structure

## Verification

When the sync service runs, you should see logs like:
```
📋 Found 1 personal plans
📋 Found 19 group plans
📋 Checking 20 total plans for updates...
🔍 Checking plan: Annika_AGI (fcoksV9z...)
🔍 Checking plan: Annika AGI Tasks (_XVogjqO...)
   Found 75 tasks in this plan
   🆕 New task from Planner: Clarify technical specifications
   🆕 New task from Planner: Analyze o1_reasoning.pdf Document
...
``` 