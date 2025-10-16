Bug Fix Log

Date: 2025-09-16

Issue
- Planner-Annika task sync completely broken - no tasks being created or synced

Root Causes
- ID mappings were incorrectly stored (50% had Planner IDs as keys instead of Annika IDs)
- _store_id_mapping was creating bidirectional mappings in wrong namespace
- Tasks were not being written to annika:tasks:{id} due to error suppression
- Agent notifications were not being sent due to error suppression

Fix
- Fixed ID mapping storage in _store_id_mapping to only store:
  - annika:planner:id_map:{annika_id} → {planner_id}
  - annika:task:mapping:planner:{planner_id} → {annika_id}
- Fixed _get_annika_id to look in correct reverse mapping location
- Fixed _remove_mapping to delete correct keys
- Removed error suppression in _create_annika_task_from_planner
- Removed error suppression in _update_annika_task_from_planner
- Ran recovery script to fix 95 reversed ID mappings in Redis

Files Modified
- src/planner_sync_service_v5.py: Fixed ID mapping functions and task creation/update
- Created fix_mappings.py recovery script to correct reversed mappings
- Created test_sync.py to verify sync functionality

Verification
- ID mappings now correctly stored (verified with test_sync.py)
- Task creation/notification logic fixed (awaiting service restart for full test)
- Recovery script successfully fixed 95 reversed mappings

Impact
- Bi-directional sync will work correctly after service restart
- Agents will receive notifications for Planner tasks
- Task Manager will have visibility of all synced tasks

---

Date: 2025-09-16

Change
- Decoupled authoritative task writes/notifications from `annika:conscious_state` existence in V5 sync service.

Details
- `_create_annika_task_from_planner`: Always `SET annika:tasks:{id}` and `PUBLISH annika:tasks:updates` even if `annika:conscious_state` is missing; mirror to `conscious_state` only if present (best effort).
- `_update_annika_task_from_planner`: Always upsert per-task key and publish; mirror to `conscious_state` if present (best effort).
- Rationale: Agents and Task Manager rely on the per-task key and updates channel; gating on `conscious_state` prevented all Planner imports.

Files Modified
- `src/planner_sync_service_v5.py`: Create/update paths refactored as above.

Verification Plan
- Restart the MS-MCP sync service.
- Run `python test_sync.py` and confirm >0 `annika:tasks:*` keys and live messages on `annika:tasks:updates`.
- Create a new Planner task; verify it appears under `annika:tasks:*`. If `annika:conscious_state` exists, confirm it mirrors under `task_lists`.

Next Steps
- Restart MS-MCP sync service to apply code changes
- Create test tasks in Planner to verify sync
- Monitor annika:tasks:updates channel for notifications

Date: 2025-09-14

Change
- Implemented non-breaking changes for full two-way Planner ↔ Annika sync in MCP server (V5):
  - Timestamp alignment: use last_modified_at or updated_at everywhere (fallback to modified_at).
  - Planner→Annika create/update now writes canonical per-task key `annika:tasks:{id}` and publishes to `annika:tasks:updates`.
  - ID mapping compatibility: tolerate JSON-or-string reads; always write string; also write reverse `annika:task:mapping:planner:{planner_id}`.
  - Adapter mapping: include `notes` and append `output` into Planner `notes` with delimiter.
  - Optional fallback: if lists are empty, adapter scans `annika:tasks:*` for per-task objects.

Files
- `src/planner_sync_service_v5.py`: updated `_task_needs_upload`, `ConflictResolver.resolve_conflict`, `_initial_sync` filter, `_get_planner_id`, `_get_annika_id`, `_store_id_mapping`, `_create_annika_task_from_planner`, `_update_annika_task_from_planner`, `_task_needs_sync_from_planner`.
- `src/annika_task_adapter.py`: enhanced `annika_to_planner` for notes/output; added per-task fallback in `get_all_annika_tasks`.

Impact
- Annika-created tasks upload reliably; Planner-created tasks are visible to agents immediately and trigger processing.
- ID map reads/writes are consistent with Task Manager; reverse mapping is present for lookups.
- Notes and agent outputs appear in Planner task notes.

Verification Plan
- Run existing tests `test_v5_sync.py`, `test_phase2_*` and manual E2E: create in Planner, observe `annika:tasks:updates`, agent update, verify PATCH to Planner and `annika:sync:last_upload:{id}`.

Notes / Follow-ups
- Many linter style warnings exist project-wide; will address separately. Removed only obviously unsafe items in future passes.

Date: 2025-09-09

Issue
- Services could not acquire a delegated authentication token; startup loop showed "Waiting for token..." and then aborted sync. Additionally, env variables were not being loaded reliably.

Root Cause
- `.env` was stored under `src/.env` but `load_env.py` did not search that location and `start_all_services.py` didn’t import it. As a result, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AGENT_USER_NAME`, `AGENT_PASSWORD` were missing in the process and ROPC could not run.
- Also needed to confirm app settings and delegated scopes; once env loaded, token acquisition proceeded.

Fix
- Updated `src/load_env.py` to include `src/.env` in `possible_paths` and to use UTF‑8 when reading.
- Imported `load_env` at the top of `src/start_all_services.py` so environment variables are loaded before token acquisition and other imports.
- Verified that on startup we now see "Found .env file ... Loaded AZURE_CLIENT_ID ..." and token verification succeeds.

Verification
- Logs show delegated token stored: `Token stored successfully for scope: delegated:https://graph.microsoft.com/.default`.
- Planner sync V5 fully started; webhooks created; initial sync completed.

Notes / Follow-ups
- Linter now flags stylistic items; defer unless we standardize formatting across the repo.
- If delegated token acquisition ever fails again, capture the AAD error via direct POST to `/oauth2/v2.0/token` to check for CA/security defaults/federation.


---

Change
- Align HTTP endpoints with correct token types and Graph paths; add SharePoint compound site support.

Files
- `src/http_endpoints.py`

Details
- Teams Chats:
  - `GET /api/me/chats` now prefers delegated token; falls back to app-only via `/users/{id}/chats` when `AGENT_USER_ID` is set. Returns a friendly 503 JSON if neither is available.
  - `POST /api/me/chats` messaging now requires delegated token explicitly; surfaces clear error if missing (app-only cannot post chat messages).
- Mail:
  - `GET /api/me/messages` (inbox list) and `GET /api/me/mailFolders` now use delegated tokens; fall back to `/users/{id}/...` with app-only if configured.
  - `POST /api/me/sendMail` now prefers delegated; falls back to `/users/{id}/sendMail` for app-only.
- Calendar:
  - `GET /api/me/calendar/calendarView` now prefers delegated; falls back to `/users/{id}/calendar/calendarView` with app-only. Uses `requests` query `params` to pass `startDateTime`/`endDateTime` as-is and returns clearer JSON on auth unavailability.
- SharePoint:
  - Added `GET /api/sites/{site_id}/drives` supporting compound `site_id` (e.g., `{hostname},{siteId},{webId}`) and lookup via `hostname` + `path` when needed.

Impact
- Resolves 401/403/400s caused by token-type/endpoint mismatches without adding new scopes. Delegated is used for all `/me/*` routes; app-only fallbacks target `/users/{id}/...` where supported by Graph.

Operational Notes
- Ensure `AGENT_USER_ID` is set for app-only fallbacks. Delegated tokens are acquired via `agent_auth_manager.get_agent_token()` (ROPC or other configured methods).

Date: 2025-09-13

Issue
- `start_all_services.py` failed to start `ngrok` and Azure Functions host with WinError 2 (executable not found).

Root Cause
- The script assumed `ngrok` and `func` would be discoverable on PATH and hard‑coded a user‑specific `func.cmd` path. In some sessions, PATH wasn’t inherited by the Python process, causing lookups to fail.

Fix
- `src/start_all_services.py`:
  - Implemented robust executable discovery using `shutil.which` plus environment hints (`NGROK_EXE`, `NGROK_PATH`, `NGROK_DIR`, `FUNC_PATH`, `FUNCTIONS_CORE_TOOLS_PATH`, `AZURE_FUNCTIONS_CORE_TOOLS_PATH`) and a repo‑local `tools/` directory fallback.
  - When an executable is found, prepend its directory to `PATH` for child processes to ensure consistent discovery.
  - Removed hard‑coded `func.cmd` path and switched to resolved path.
  - Cleaned up logs (removed emojis) and improved error messages.

Verification
- Quick checks:
  - `Get-Command ngrok` and `Get-Command func` return valid paths in PowerShell.
  - Running `python start_all_services.py` no longer raises WinError 2; ngrok and Function App start as expected.

Notes / Follow-ups
- If `ngrok`/`func` still aren’t found, set `NGROK_EXE` or `FUNC_PATH` (or their directory variants) in `.env`/`local.settings.json`. The startup script will pick them up automatically.

Date: 2025-09-13

Change
- Bind local Azure Functions host to all interfaces (0.0.0.0) so the MCP SSE endpoint is reachable from other machines on the network.

Files
- `src/start_all_services.py`

Details
- When starting the Functions host, set `ASPNETCORE_URLS=http://0.0.0.0:7071` in the child process environment and pass `--port 7071`. This ensures Kestrel listens on all interfaces.
- Startup log now prints `http://0.0.0.0:7071` to make the external URL obvious.

Operational Notes
- To run manually without the script:
  - PowerShell (session-only): `$env:ASPNETCORE_URLS = "http://0.0.0.0:7071"; cd src; func start`
  - Optional Windows Firewall rule (require admin): `New-NetFirewallRule -DisplayName "Azure Functions 7071" -Direction Inbound -Protocol TCP -LocalPort 7071 -Action Allow`
- If exposing publicly, prefer using the existing ngrok tunnel and function-level auth for the SSE endpoint.

Verification
- From another machine on the LAN, curl: `http://<host-ip>:7071/api/health/ready` returns 200 and the SSE endpoint streams at `http://<host-ip>:7071/runtime/webhooks/mcp/sse`.

Date: 2025-09-10

Change
- Hardened health checks to eliminate intermittent "Host unavailable after check" errors during startup and restarts.

Files
- `src/function_app.py`: Added ultra-light readiness endpoint `GET /api/health/ready` returning `{ status: "ready" }` for external probes.
- `src/start_all_services.py`: Updated readiness wait to probe `/api/health/ready` first, with exponential backoff and jitter, falling back to `/api/hello`.
- `src/host.json`: Tuned `healthMonitor` for local dev to reduce false negatives (10s interval, 2m window, threshold 6).

Impact
- External supervisors stop flagging transient host unavailability; startup becomes more robust; fewer noisy log lines and restarts.

Verification
- Start services and observe logs: readiness uses `/api/health/ready`; no new "Host unavailable after check" entries during startup. Health metrics continue to report normally.

---

Date: 2025-09-12

Issue
- Delegated token acquisition via ROPC fails with `AADSTS65001: consent_required`, causing `/me/*` endpoints to return 400 and the live endpoints test to fail one or more routes intermittently.

Troubleshooting checklist (current status)
- [x] Required delegated scopes identified and configured per policy: `openid`, `profile`, `offline_access`, `User.Read`, `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`, `Calendars.Read|Calendars.ReadWrite`, `Files.ReadWrite.All` (prefer ALL variants), `Chat.Read`, `Chat.ReadWrite`, `Tasks.ReadWrite`.
- [x] MFA/CA blocking ROPC ruled out (MFA disabled for agent user).
- [x] Allow public client flows enabled (ROPC) under App registrations → Authentication.
- [ ] Admin consent verified across all delegated scopes actually requested by code (especially `Files.Read.All` vs `Files.ReadWrite.All`).
- [ ] Enterprise applications → Agency-Swarm → Properties → “User assignment required?” set to `No` (or the agent user explicitly assigned).
- [ ] Agent credentials valid (no force password change / expired password).
- [ ] Token endpoint used is tenant‑scoped v2.0: `https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token`.
- [ ] After consent, delegated token warms successfully; `/me` probe returns 200.

Remediation implemented in code
- Switched token requests to prefer “ALL” variants to align with tenant policy.
  - Default delegated scope set to include `Files.ReadWrite.All` (see `src/agent_auth_manager.py`).
- Adjusted several `/me/*` endpoints to request minimal, delegated scopes; remaining endpoints will be aligned to use `*.ReadWrite.All` where required by tenant policy.

Next actions (requires tenant admin)
1. Grant tenant admin consent for delegated scopes actually requested at runtime (verify that `Files.Read.All` delegated is either granted or replaced by `Files.ReadWrite.All`).
2. In Enterprise applications → Agency-Swarm → Properties, set “User assignment required?” to `No` (or assign the agent user if you keep it `Yes`).
3. Re‑run delegated token warmup and validate `/me` calls.

Manifest review (Agency‑Swarm)
- [x] signInAudience: `AzureADMultipleOrgs` (multi‑tenant). OK for tenant‑scoped token requests.
- [x] isFallbackPublicClient: `true` (Allow public client flows enabled for ROPC).
- [x] requiredResourceAccess includes extensive Microsoft Graph delegated scopes (Scopes) and application roles (Roles). Delegated consent still must be granted in Enterprise app → Permissions.
- [x] Implicit grant disabled for Web (not relevant to ROPC).
- [x] Public client redirect URIs empty (OK for ROPC).
- [ ] Enterprise app setting "User assignment required" not visible in this export. Verify in Enterprise applications → Agency‑Swarm → Properties and set to `No` or assign the agent user.
- [!] servicePrincipalLockConfiguration: `isEnabled=true`, `allProperties=true`. If the Enterprise app UI prevents toggling Properties or granting consent, unlock the service principal or have a Global Admin adjust this lock before changing settings.



---

Date: 2025-09-10

Issue
- Ctrl+C did not always perform a graceful shutdown; child processes could linger and ports (7071 for Azure Functions, 4040 for ngrok API) sometimes remained bound, causing subsequent starts to fail.

Fix
- `src/start_all_services.py`:
  - Implemented `async stop_all()` to orderly stop: sync service → background tasks → ngrok → Function App.
  - On Windows, send `CTRL_BREAK_EVENT` to processes started with `CREATE_NEW_PROCESS_GROUP` for clean teardown; Unix uses `terminate()` with fallback to `kill()`.
  - Added `_get_pid_on_port()` and `_ensure_port_closed()` to verify ports are freed; only force-stops the process if its PID matches the expected child PID (avoids killing unrelated processes).
  - Ensured background renewal loop and other tasks are cancelled and awaited.

Verification
- Manual test: start services, press Ctrl+C; observed orderly shutdown logs, no lingering `func`/`ngrok` processes, and ports 7071/4040 are released. Subsequent start succeeds without "address in use" errors.

Notes
- Some linter warnings remain (formatting/logging style) but do not affect shutdown reliability. Will address in a separate formatting pass.

---

Date: 2025-09-18

Issue #34 - MS-MCP Infinite Recursion Loop
- Service showing massive repetition of "📤 Processing upload batch" messages
- Eventually failing with "maximum recursion depth exceeded while calling a Python object"
- Complete Planner sync service failure, unable to process tasks

Root Cause
- Direct recursion in _queue_upload() function when batch size reached
- When rate limited, _create_planner_task and _update_planner_task call _queue_upload()
- _queue_upload() immediately called await _process_upload_batch() when queue full
- _process_upload_batch() could trigger more rate limiting, calling _queue_upload() again
- Created infinite recursion loop without proper async scheduling

Fix Applied
1. Changed _queue_upload() to use asyncio.create_task() instead of await for batch processing
2. Added _trigger_batch_processing() helper with 0.1s delay to prevent tight loops
3. Added batch_processing flag to prevent concurrent batch processing
4. Added duplicate detection in _queue_upload() to prevent same task being queued multiple times
5. Wrapped _process_upload_batch() with try/finally to ensure flag is always reset
6. Initialized batch_processing flag in __init__ method

Files Modified
- src/planner_sync_service_v5.py: Fixed recursion in batch processing and added guards

Verification Needed
- Restart MS-MCP service to test fix
- Monitor logs for proper batch processing without infinite loops
- Verify tasks are syncing correctly between Planner and Annika

Impact
- MS-MCP service will be stable and functional
- Task sync will resume working correctly
- No more stack overflow errors

---

Date: 2025-09-19

Issue
- UnboundLocalError in RateLimitHandler: "cannot access local variable 'backoff' where it is not associated with a value"

Root Cause
- In the handle_rate_limit method, the 'backoff' variable was only defined in the else block
- When retry_after_seconds parameter was provided, backoff was never defined but still used in the logger.warning message

Fix Applied
- Modified handle_rate_limit() to define backoff in both branches of the if statement
- When retry_after_seconds is provided, set backoff = retry_after_seconds
- When calculating exponential backoff, backoff is calculated as before

Files Modified
- src/planner_sync_service_v5.py: Fixed UnboundLocalError in RateLimitHandler.handle_rate_limit()

Verification
- Confirmed fix worked - service ran without UnboundLocalError after restart
- New HTTP 403 permission errors detected (tracked as issue #35 in current_debug_tasks.mdc)

Impact
- Rate limiting handler now works correctly when explicit retry_after is provided
- No more UnboundLocalError crashes in rate limit scenarios

---

Date: 2025-09-23

Change
- Align sync health TTL to spec (5 minutes) and implement pending operations queue worker

Details
- `src/planner_sync_service_v5.py`:
  - `_health_monitor`: Changed Redis `annika:sync:health` TTL from 3600 to 300 seconds.
  - Added `_pending_queue_worker` coroutine: consumes `annika:sync:pending` via BRPOP with 5s timeout, retries with exponential backoff + jitter, deduplicates across restarts using `annika:sync:processed:{yyyy-mm-dd}` (TTL 2 days), and writes structured failures to `annika:sync:failed` with bounded list size and TTL enforcement.
  - Wired worker into `asyncio.gather` in `start()` so it runs alongside existing loops.
  - Enhanced delete path: on HTTP 412, fetch fresh ETag and retry once with `If-Match` (fallback `*`).

Verification Plan
- Restart MS-MCP services; observe `annika:sync:health` key TTL ~300s and refresh every minute.
- Push test operations into `annika:sync:pending` and verify consumption, retries, and dedup set population.
- Confirm failed entries appear in `annika:sync:failed` with TTL and list bounded to last 1000.

Impact
- Monitoring reflects current state within 5 minutes per spec.
- Pending operations are processed reliably with backoff and no duplicate reprocessing across restarts.
- Delete operations are more resilient to ETag drift (reduces 412 failures).

---

Date: 2025-09-23

Change
- Planner Sync V5 stability and performance improvements (memoization, plan choice cache, inaccessible plans set, quick-poll control, housekeeping)

Details
- `src/planner_sync_service_v5.py`:
  - Plan discovery memoized per cycle (5m) and `$select` added to Graph reads.
  - Per-plan bucket cache (5m) with Redis mirror `annika:graph:buckets:{planId}` EX 300.
  - Fallback create caches plan choice per Annika task `annika:planner:plan_choice:{id}` EX 300.
  - Mark inaccessible plans on 403: `SADD annika:planner:inaccessible_plans` with TTL 600; skip during selection.
  - Quick polls add jitter and enforce a minimum interval via `MIN_QUICK_POLL_INTERVAL_SECONDS` (default 300s).
  - Housekeeping loop (config-gated): normalizes ID maps, deletes orphan ETags, enforces TTLs, trims logs, sets health TTL; dry-run by default logging to `annika:cleanup:log` and `annika:cleanup:stats`.
  - Polling interval configurable via `PLANNER_POLL_INTERVAL_SECONDS` (default 3600s).

Verification Plan
- Restart services and validate:
  - Reduced discovery calls; Redis shows `annika:graph:plans:index` and `annika:graph:buckets:*` keys with TTL ~300s.
  - On 403 fallback, `annika:planner:inaccessible_plans` contains plan and expires ~600s.
  - `annika:cleanup:stats` present when housekeeping runs; no destructive changes in DRY-RUN.

Impact
- Less churn on Graph APIs; safer, faster creates/updates.
- Fewer 403 loops; quicker fallback to accessible plans.
- Operational hygiene improves; stale keys/ETags auto-corrected with safe defaults.

---

Date: 2025-09-23

Change
- Teams chat subscriptions, planner webhook schema consistency, and token reuse verification

Details
- `src/chat_subscription_manager.py`:
  - Ensure per-chat subscription entries include `mode: per_chat` for clarity; global remains `mode: global`.
  - Global → per-chat fallback path preserved; renewal window (15m) and cleanup maintained.
- `src/webhook_handler.py`:
  - Publish minimized, consistent payload to `annika:planner:webhook` (fields: `changeType`, `resource`, `resourceData`, `clientState`, `subscriptionId`).
  - Keeps lifecycle logging and other resource routing identical.
- `src/agent_auth_manager.py`:
  - Reinforced token reuse: prefer in-memory cache → Redis cache, and as last resort reuse master delegated superset token if available (no re-mint) to avoid unnecessary token churn.

Verification Plan
- Create a per-chat subscription and confirm Redis hash contains `mode=per_chat`; validate renewal logs update `expires_at`.
- Send a sample webhook payload and confirm consumer sees the minimized schema on `annika:planner:webhook`.
- Observe `get_agent_token` calls under load: no repeated ROPC requests; tokens reused until TTL buffer (~5 min) and master token used as fallback when appropriate.

Impact
- Cleaner, predictable webhook bus schema; fewer downstream parsing errors.
- Teams subscriptions metadata clearer and easier to audit; renewal flow remains robust.
- Reduced token acquisition frequency; less auth load and fewer throttling risks.

Date: 2025-09-24

Change
- Reset Redis task data to resolve 403 Planner create loops and stale sync artifacts.

Details
- Added `src/Clear_All_Local_Task_Data.py` utility:
  - Canonical wipe of `annika:tasks:*`, `annika:conscious_state`, `annika:consciousness:*:components:tasks`, `annika:agent_outputs:*`.
  - Clears Planner crosswalk/cache keys (`annika:planner:id_map:*`, `annika:task:mapping:planner:*`, `annika:planner:tasks:*`, `annika:planner:etag:*`).
  - Removes pending/failed sync queues (`annika:sync:pending`, `annika:sync:failed`, `annika:sync:last_upload:*`, `annika:sync:log`, `annika:sync:health`, `annika:sync:webhook_status`).
  - Drops task pub/sub backlog (`annika:tasks:updates`, `annika:tasks:assignments`, `annika:tasks:completions`, `annika:tasks:queue`).
  - Includes dry-run flag and verifies critical patterns are empty post-cleanup.
- Executed script against Redis (deleted 2,445 keys); verification confirmed zero residual keys for `annika:tasks:*`, `annika:planner:id_map:*`, `annika:task:mapping:planner:*`.

Impact
- Local Redis no longer contains stale Annika/Planner task records that caused repeated 403 create attempts and dirty sync state.
- Next MS-MCP start will repopulate from live Planner data only; prevents agents from acting on orphaned tasks.



---

## 2025-10-15 | Planner Task Overflow & Subtask Fix

### Problem
- **603 pending tasks** attempting to sync to a full Microsoft Planner plan
- Error: \MaximumActiveTasksInProject\ (HTTP 403) - plan at 200+ task capacity
- **Subtasks creating individual Planner tasks** instead of using checklist items
- Batch processing continuing during rate-limit backoff periods
- No plan capacity validation at Task Manager level

### Implementation
1. **Redis Reset**: Cleared 5,846 keys (1250 tasks, 1116 ID maps, 538 mirrors, 561 cached, 2381 sync state)
2. **Subtask Filtering**: Added \_is_subtask_entry()\ helper to detect Task-CV-xxx-###-### pattern and skip queuing
3. **Backoff Check**: Modified \_process_upload_batch()\ to respect backoff_until flag
4. **403 Handling**: Enhanced error handling to detect MaximumActiveTasksInProject and mark tasks as failed (no retry)
5. **Capacity Validation**: Added \check_plan_task_count()\ to Task Manager, blocks creation when plan ≥200 tasks

### Files Modified
- \planner_sync_service_v5.py\: Subtask filter, backoff check, 403 handling (lines 2042-2133, 3088-3133)
- \config.py\: Added MAX_TASKS_PER_PLANNER_PLAN = 200
- \edis_manager.py\: Added check_plan_task_count() method (lines 305-343)
- \__init__.py\: Integrated plan capacity check into task_create (lines 141-152)

### Status
✅ Implemented - Ready for testing

