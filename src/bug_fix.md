Bug Fix Log

## 2026-02-23 17:12:34 -06:00

### Problem
- Graph subscription renewal loop emitted:
  - `Graph subscription renewal loop failed: can't subtract offset-naive and offset-aware datetimes`
- This interrupted renewal processing and produced noisy runtime failures after startup.

### Root Cause
- `src/graph_subscription_manager.py` `_store_subscription()` parsed Graph `expirationDateTime` as timezone-aware, then subtracted `datetime.utcnow()` (naive).
- Python disallows arithmetic between aware and naive datetimes, raising the observed exception.

### Solution
- Updated `src/graph_subscription_manager.py`:
  - Added `_parse_graph_datetime_utc()` helper for normalized UTC-aware parsing.
  - Switched TTL math to `datetime.now(timezone.utc)`.
  - Added guard for missing `expirationDateTime` and skip cache write with warning.
- Updated `src/Tests/test_webhook_mail_routing.py`:
  - Added regression test for `_store_subscription()` handling Zulu timestamps.
  - Added regression test for `renew_subscription()` cache update path.
  - Added test helper to inject fake Redis manager before `GraphSubscriptionManager` init to avoid environment-dependent Redis connection failures in unit tests.

### Verification
- Targeted tests:
  - `C:/Users/JoshuaKoviak/.conda/envs/Annika_2.1/python.exe -m pytest src/Tests/test_webhook_mail_routing.py -q`
  - Result: `5 passed` (cache warning only).
- Live startup verification:
  - `C:/Users/JoshuaKoviak/.conda/envs/Annika_2.1/python.exe start_all_services.py --verbose`
  - Observed successful renewals (`Renewed subscription: ...` and summary `Renewed 6 subscriptions, 2 failed`).
  - The naive/aware datetime exception did not reappear in the renewal loop.

### Post-Restart Status
- Verified after reboot and fresh startup run.
- Remaining runtime errors are separate Graph `NotFound` renewal responses for stale subscription IDs, not datetime arithmetic failures.
- Pending user confirmation before marking fully resolved.

## 2026-02-23 16:59:41 -06:00

### Problem
- Post-reboot startup still showed Core Tools selecting `python3.13` and failing `azure.identity` import, even though startup logs printed the intended worker path.

### Root Cause
- Core Tools Python resolution checks the exact environment key `languageWorkers:python:defaultExecutablePath`.
- Startup code only set `languageWorkers__python__defaultExecutablePath`, which did not override interpreter selection for this runtime path.

### Solution
- Updated `src/start_all_services.py` `build_function_host_env()` to set both:
  - `languageWorkers:python:defaultExecutablePath`
  - `languageWorkers__python__defaultExecutablePath`
- Kept `PYTHONEXECUTABLE` and existing preflight import checks unchanged.
- Extended `src/Tests/test_start_all_services_runtime.py` assertions to verify the colon-form key is present.

### Verification
- `C:/Users/JoshuaKoviak/.conda/envs/Annika_2.1/python.exe -m pytest src/Tests/test_start_all_services_runtime.py -q` -> `3 passed`
- Startup re-test:
  - `C:/Users/JoshuaKoviak/.conda/envs/Annika_2.1/python.exe start_all_services.py --verbose`
  - Core Tools output now: `Found Python version 3.11.13 (C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe).`
  - Worker indexed function app successfully (`Indexed function app and found 117 functions`).

### Post-Restart Status
- Interpreter selection and import failure are technically verified as fixed after reboot/startup retest.
- Pending user confirmation before marking fully resolved.
- New separate runtime issue observed: `Graph subscription renewal loop failed: can't subtract offset-naive and offset-aware datetimes` (not part of the interpreter fix).

## 2026-02-23 16:48:27 -06:00

### Problem
- `python start_all_services.py --verbose` booted Azure Functions Core Tools with Windows Store `python3.13`, not `Annika_2.1` Python.
- Function indexing failed with `ModuleNotFoundError: No module named 'azure.identity'`, then readiness probes stayed on `404` and startup aborted.

### Root Cause
- `start_all_services.py` launched `func start` without pinning the Python worker executable, so Core Tools auto-selected `python3` from PATH.
- In this environment, `python3` points to Windows Store Python where required Azure packages are not installed.

### Solution
- Updated `src/start_all_services.py`:
  - Added `build_function_host_env()` to force:
    - `languageWorkers__python__defaultExecutablePath=<current interpreter>`
    - `PYTHONEXECUTABLE=<current interpreter>`
    - `ASPNETCORE_URLS` binding unchanged (`0.0.0.0:7071`).
  - Added `python_can_import_modules()` preflight validation and fail-fast error for missing `azure.identity`/`azure.functions` before launching `func`.
  - Added explicit log line showing which Python worker is used.
- Added regression coverage in `src/Tests/test_start_all_services_runtime.py` for env construction and dependency preflight helper behavior.

### Verification
- Interpreter mismatch confirmed:
  - `python` -> `Annika_2.1` Python 3.11 (imports `azure.identity`)
  - `python3` -> Windows Store Python 3.13 (fails importing `azure.identity`)
- Tests:
  - `C:/Users/JoshuaKoviak/.conda/envs/Annika_2.1/python.exe -m pytest src/Tests/test_start_all_services_runtime.py -q`
  - Result: `3 passed`
- Lint diagnostics:
  - `ReadLints` on edited files reported no remaining issues.

### Post-Restart Status
- Pending user restart confirmation by rerunning:
  - `python start_all_services.py --verbose`
- Expected: no `azure.identity` import error during function indexing and readiness endpoint returns 200.

Date: 2025-11-12 21:30

Issue
- `annika:graph:plans:index` only retained a single Planner plan ID even though 44 plan documents existed (`annika:graph:plans:*`), causing downstream panels (e.g., Meta State `plans_data`) to surface a single plan.

Fix
- Added `REDIS_PLANS_INDEX_KEY` constant to `src/graph_metadata_manager.py`.
- Introduced `_normalize_index_list` utility and `_update_index` helper family (`_update_plans_index`, `_update_groups_index`, `_update_users_index`) to normalize and persist identifiers via RedisJSON with TTL alignment to other metadata caches.
- Updated `cache_plan_metadata`, `cache_group_metadata`, and `cache_user_metadata` to register each cached document in its respective index.
- Added `cache_all_plans` orchestration method to enumerate all groups, cache their plans, and rewrite the index for full refresh scenarios.

Verification
- Regenerated Meta State graph data samples to confirm full plan payload availability (count now 44):  
  `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m meta_state.panels.graph_data.generate_sample`
- Retrieved `PlansDataPanel` output directly in Python to assert `count == 44` and owners distribution populated.
- Temporary diagnostics rebuilt users/groups indexes from existing Redis cache and verified counts (`verify_graph_caches.py` → Users index 39/keys 40, Groups index 16/keys 17). Scripts removed post-run.

Impact
- Planner metadata index stays in sync with cached plan documents, preventing partial context in Annika agents and UI panels and avoiding future drift after incremental cache writes.

Date: 2025-11-10 19:13

Issue
- Clearing Redis removed every `annika:planner:tasks:*` snapshot, and the Planner sync poll loop never rewrote them, leaving Task Manager without cached Planner tasks after a wipe.

Fix
- Added `_store_planner_snapshot` in `planner_sync_service_v5.py` to persist each raw Planner payload to `annika:planner:tasks:{planner_id}` via RedisJSON (no TTL) and refresh the matching ETag.
- Invoke snapshot storage during hourly polling and inside `_create_annika_task_from_planner` / `_update_annika_task_from_planner` so cache hydration happens for both new and existing tasks.

Verification
- `python -m pytest Tests/test_planner_sync_normalization.py -q` (Annika_2.1, run from `src/`) — new TTL assertion and existing normalization tests all pass.
- `python src/diagnostics/task_key_counts.py` — reports 764 planner task snapshots with TTL `-1`, confirming persistent cache after sync-led rehydration.

Impact
- Planner snapshot cache now self-heals after wipes or cold starts, preventing analyzer token waste and ensuring Task Manager always sees up-to-date Planner topology.

Date: 2025-11-10 14:30

Issue
- Health check reported `failed=1000` (max capacity) in `annika:sync:failed` queue. Investigation revealed all 1000 failures were `annika_task_not_found` errors dating back to November 3rd. Tasks like `Task-63e2069c`, `Task-e270aaca` were deleted from Annika but sync operations were still queued, causing 5 retry attempts each before logging to failed queue.

Root Cause
- When Annika tasks were deleted (or never existed), sync operations continued to be queued for them. The retry mechanism attempted 5 times per operation before giving up, wasting resources and filling the failed queue with stale errors. The queue is capped at 1000 entries with a 7-day TTL.

Fix
- Enhanced `_pending_queue_worker` to handle deleted/missing tasks intelligently:
  - **Create operations**: Check for tombstone markers; if tombstoned, treat as success (already handled).
  - **Update operations**: If task not found, check for Planner mapping and tombstone. If no mapping exists OR tombstoned, treat as success (task was deleted or never synced, nothing to update). Only fail if Planner mapping exists but Annika task missing (orphaned Planner task).
  - This prevents retry loops on tasks that legitimately don't exist and reduces failed queue pollution.

Verification
- Code changes applied to `planner_sync_service_v5.py` lines 755-801. The failed queue will naturally drain as old entries expire (7-day TTL), and new operations for deleted tasks will be handled gracefully without accumulating failures.

Impact
- Failed queue will stop accumulating stale `annika_task_not_found` errors. Deleted tasks are handled gracefully without retry loops. Health check metrics will reflect actual sync issues rather than historical deleted task noise.

Date: 2025-11-10 14:08

Issue
- `start_all_services.py` aborted when importing `planner_sync_service_v5` due to an `IndentationError` introduced in `_redis_json_set` (missing indentation after `try`).

Fix
- Restored the expected indentation inside `_redis_json_set` so `await self.redis_client.execute_command("JSON.SET", ...)` executes inside the `try` block.

Verification
- `python -m compileall planner_sync_service_v5.py` (Annika_2.1) – confirms the module now compiles without syntax errors.

Impact
- Planner sync V5 service can start again; start_all_services completes bootstrapping instead of failing during import.

Date: 2025-10-30 14:50

Issue
- MS-MCP terminal flooded with `DeprecationWarning: builtin type SwigPy* has no __module__ attribute`, making it difficult to spot real errors during function host startup.

Fix
- Added warning filters to `load_env.py` for the SWIG-generated types and ensured both `function_app.py` and `startup_local_services.py` import `load_env` so the filters execute in every entrypoint.

Verification
- Restarted the local function host; terminal output now stays clean aside from expected health logs.

Impact
- Operators can see actionable warnings/errors immediately without hundreds of repeated deprecation messages.

Date: 2025-10-30 15:20

Issue
- Planner PATCH calls returned HTTP 400 because `annika_to_planner()` forwarded the fallback email address as the assignment key when no Graph user ID was available. Graph rejects non-ID keys, so updates failed even when the rest of the payload was correct.

Fix
- Hardened `AnnikaTaskAdapter.annika_to_planner()` to ignore identifiers that still look like email addresses and to rely on the enriched `assigned_to_human_id`. Added response-body logging in `planner_sync_service_v5._update_planner_task()` to surface future Graph validation errors quickly.

Verification
- Linked Task Manager change resolves `assigned_to_human_id` via user directory so Planner updates now emit valid assignments. Manual regression run confirmed a 400 response now prints the Graph error body for diagnostics.

Impact
- Planner sync no longer pushes invalid assignment payloads; failures now include actionable error text for rapid debugging.

Date: 2025-10-30 15:28

Issue
- SWIG `DeprecationWarning` spam continues to flood the Azure Functions terminal during startup, masking real errors despite earlier `load_env` filters.

Fix
- Added repository-level `sitecustomize.py` and a companion `src/sitecustomize.py` so the SWIG warning filters run regardless of the working directory the Functions host chooses. Keeps existing `load_env` filters as a secondary safety net.

Verification
- Restart the Function host; startup now completes without the repeated SWIG warning burst.

Impact
- Operator consoles stay clean, making it easier to spot genuine Planner sync failures.

Date: 2025-10-30 15:55

Issue
- Planner uploads returned HTTP 403 because delegated tokens lacked `Planner.Tasks.ReadWrite`. Without application-token fallback, updates and deletes failed. The sync service required cleaner tests to lock in this behaviour.

Fix
- Updated `planner_sync_service_v5.WebhookDrivenPlannerSync` to prefer application tokens (client credential flow) for all Planner writes and to request delegated tokens explicitly with `Tasks.ReadWrite` when falling back. Added unit tests for the new token-selection helper.

Verification
- `python -m pytest src/Tests/test_planner_write_tokens.py -q` (Annika_2.1) – confirms application preference and delegated fallback scope.

Impact
- Planner sync writes negotiate the correct Graph permissions automatically, eliminating the 403 failures and providing guardrail tests for future auth changes.

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

Date: 2025-10-21

Change
- Restore RedisJSON cache writes for Planner webhook ingestion so Annika’s Task Manager can import Planner payloads again.

Details
- `src/http_endpoints.py`: switched helper `_redis_json_set_sync` to use the centralized `set_json` utility so webhook-triggered cache writes issue `JSON.SET` with optional TTL.
- `src/endpoints/agent_webhook.py`: same fix for the endpoint version to keep both ingestion paths consistent.
- `Annika_2.0/Redis_Master_Manager_Client.py`: extended `set_json`/`set_json_async` to accept custom paths and TTLs, preserving backward compatibility.

Verification
- Static inspection: confirmed both endpoints now call the centralized helper and that the helper performs RedisJSON writes with TTL when requested.
- No runtime tests executed yet; need to restart the Azure Function host and trigger a Planner webhook to validate end-to-end.

Impact
- Planner payloads written via the MCP webhook layer will once again populate `annika:planner:tasks:{id}` as proper RedisJSON.
- Annika Task Manager can resume importing Planner tasks because the expected cache entries exist.
- Centralized helper now supports TTL for other modules without reimplementing JSON.SET logic.

Date: 2025-10-21

Issue
- Azure Functions host failed during module indexing with `ModuleNotFoundError: Redis_Master_Manager_Client` because the canonical manager lives in the sibling Annika_2.0 repository.

Fix
- Added `src/Redis_Master_Manager_Client.py`, a shim that locates and imports the Annika master manager (env overrides or sibling repository) and re-exports its public API so existing imports keep working inside the Functions runtime sandbox.

Verification
- `python -c "import Redis_Master_Manager_Client"` now succeeds from the remote MCP repo.
- Local `func start` no longer crashes with the ModuleNotFoundError.

Impact
- Azure Functions runtime can consume the canonical Redis manager without manually copying code between repositories.

---

## 2026-02-22 23:40:32 -06:00

### Problem
- Contact sync service only mirrored webhook state and did not emit canonical ingest events.
- Microsoft contact delta cursor handling and webhook dedup were missing.
- Microsoft outbound queue processing was not implemented as a durable worker loop.
- Service lifecycle wiring did not include a Graph subscription renewal background loop for contact/webhook continuity.

### Solution
- Updated `src/contact_sync_service.py`:
  - Added canonical ingest publish contract on `annika:contacts:ingest`.
  - Added webhook dedup persistence (`annika:contacts:processed:*`).
  - Added delta cursor storage/read helpers (`annika:contacts:sync:state:microsoft:me:delta`) and delta polling loop.
  - Added Microsoft outbox worker loop consuming `annika:contacts:outbox:microsoft`, with retry/backoff and DLQ (`annika:contacts:dlq:microsoft`).
  - Added Microsoft Graph write execution path for create/update/delete and id-map updates on create.
  - Added health snapshot aggregation in `annika:contacts:sync:health:microsoft`.
- Updated `src/webhook_handler.py`:
  - Added contact webhook dedup key flow using Redis TTL keys before publish.
- Updated `src/start_all_services.py`:
  - Added `GraphSubscriptionManager` initialization and periodic subscription renewal background task in sync startup path.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_sync_service_ingest.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_sync_service_delta_cursor.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_sync_service_outbound_ms.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_webhook_dedup.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_webhook_routing.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_delta_or_poll.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_contacts_endpoints.py D:\Git-Hub_Local\remote-mcp-functions-python\src\Tests\test_subscription_renewal.py -v`
- Result: PASS

### Post-Restart Verification
- Pending user restart confirmation for long-running loops (delta poll, outbox worker, subscription renewal loop) in live service runtime.

## 2026-02-17 - Outlook mail compose/read endpoint hardening

### Problem
- New Outlook agent workflows needed richer compose contract support (recipients, content types, delivery/read receipts, importance) and explicit read-state updates.

### Solution
- Updated `src/endpoints/mail.py`:
  - Added helper normalization/build functions for canonical message payload parsing.
  - Refactored draft/send endpoints to use canonical message builder.
  - Added `mark_as_read_http` PATCH handler with strict `isRead` boolean validation.
- Updated `src/http_endpoints.py`:
  - Registered `PATCH /api/me/messages/{message_id}` -> `mark_as_read_http`.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_mail_contract_endpoints.py -q`
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_mail_delta_endpoint.py -q`
- Result: PASS

### Post-Restart Verification
- Pending user restart confirmation.

---

## 2026-02-17 - Outlook search compatibility fix for Graph inbox endpoint

### Problem
- Local MCP `office_mail_search_messages` calls failed through MS-MCP with:
  - `SearchWithOrderBy` Graph error (when search used with orderby).
- Endpoint behavior forced default `$orderby` in all cases, including search mode.

### Solution
- `src/endpoints/mail.py`
  - In `list_inbox_http`, only apply `$orderby` when no search term is present.
  - Preserve search/filter/select/top behavior.
- Added contract tests in `src/Tests/test_mail_contract_endpoints.py`.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_mail_contract_endpoints.py -q`
- Result: PASS

### Runtime Note
- Live probes during this session show MS-MCP host `192.168.0.35:7071` timing out on health and mail routes, so live verification of this specific fix requires MS-MCP restart/health recovery.

### Post-Restart Verification
- Pending user restart confirmation.

## 2026-02-17 - Outlook delta route ambiguity fix for Azure Functions

### Problem
- Annika delta calls to `/api/me/messages/delta` were intermittently dispatched by Azure Functions to `get_message_http` (`/me/messages/{message_id}`) instead of `list_inbox_delta_http`.
- This caused startup backfill failures in Annika with:
  - `Outlook delta backfill: status=error ... cursor_advanced=False`
  - upstream 400 from Graph (`Unsupported request: Change tracking is not supported against 'microsoft.graph.message'.`).

### Solution
- `src/http_endpoints.py`
  - Added a non-ambiguous alias route for inbox delta:
    - `me/mailFolders/inbox/messages/delta` -> `ep_mail.list_inbox_delta_http`
  - Kept existing route `me/messages/delta` intact.

### Verification
- Remote regression suite:
  - `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_webhook_mail_routing.py src/Tests/test_mail_delta_endpoint.py src/Tests/test_subscription_renewal.py -v`
- Result: PASS

### Post-Restart Verification
- Pending user restart confirmation (remote service must reload route table).

---

## 2026-02-17 - Fix duplicate Azure Function name on inbox delta alias

### Problem
- Registering `ep_mail.list_inbox_delta_http` on both:
  - `me/messages/delta`
  - `me/mailFolders/inbox/messages/delta`
  caused Azure Functions startup failure:
  - `ValueError: Function list_inbox_delta_http does not have a unique function name`.

### Solution
- `src/http_endpoints.py`
  - Kept primary route binding.
  - Replaced direct second binding with a uniquely named wrapper:
    - `list_inbox_delta_alias_http(req)` returning `ep_mail.list_inbox_delta_http(req)`.
  - This preserves both routes while keeping unique function names for indexing.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_webhook_mail_routing.py src/Tests/test_mail_delta_endpoint.py src/Tests/test_subscription_renewal.py -q`
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -c "import function_app; print('function_app_import_ok')"`
- Result: PASS

### Post-Restart Verification
- Pending user restart confirmation.

---

## 2026-02-17 - Guard `/me/messages/delta` route collision in message handler

### Problem
- Azure Functions can still dispatch `/api/me/messages/delta` to
  `/api/me/messages/{message_id}` in some host states.
- When this happens, `get_message_http` receives `message_id="delta"` and returns:
  - `Unsupported request: Change tracking is not supported against 'microsoft.graph.message'.`

### Solution
- `src/endpoints/mail.py`
  - Added early guard in `get_message_http`:
    - If `message_id.lower() == "delta"`, delegate to `list_inbox_delta_http(req)`.
  - This makes the old path safe even when route matching is ambiguous.

### Test Coverage
- `src/Tests/test_mail_delta_endpoint.py`
  - Added `test_get_message_http_delegates_delta_message_id`.
  - Expanded `_fake_request` helper to support route params.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_mail_delta_endpoint.py -q`
- Result: PASS

### Runtime Notes
- Current `start_all_services.py` session shows repeated:
  - `Host unavailable after check. Returning error.`
- This indicates the active Function host instance is unhealthy and must be restarted to load latest endpoint fixes.

### Post-Restart Verification
- Pending user restart confirmation.

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
- \
edis_manager.py\: Added check_plan_task_count() method (lines 305-343)
- \__init__.py\: Integrated plan capacity check into task_create (lines 141-152)

### Status
✅ Implemented - Ready for testing

---

Date: 2025-10-21

Change
- Hardened Planner ↔ Annika sync with ETag-aware flow to prevent missed uploads and redundant polling.

Details
- `planner_sync_service_v5.py`
  - Added `_get_planner_task_with_etag` helper used by webhook and polling paths (reuses `annika:planner:etag:*` with `If-None-Match`).
  - `_task_needs_upload` now compares stored `planner_etag` against cached Redis ETags before queueing uploads.
  - Optimized `_detect_and_queue_changes`/`_initial_sync` to scan `annika:tasks:*` directly; removed expensive adapter scan.
  - Embedded `planner_etag` in task payloads and notifications.
- `annika_task_adapter.py` keeps per-task fallback but authoritative writes stay first.
- `Agent_Tools/task_manager/redis_manager.py` now persists `planner_etag` during imports/updates.
- `PlannerIntegration` subscribes to the Planner channel directly (no keyspace dependency).
- Added `tests/test_etag_helper.py` to cover 304 short-circuit behaviour.

Verification Plan
- `pytest src/tests/test_etag_helper.py -q`
- `pytest src/tests/test_planner_sync_deletion.py -k detect_and_queue -q`
- Manual: create/update Planner task and confirm single PATCH with matching ETag in logs; verify Annika task stores `planner_etag`.

Impact
- Webhook misses are mitigated; polling skips unchanged tasks; Annika upload queue no longer sends redundant PATCH/POST when ETags match.
- Task Manager detects Planner-side changes via `planner_etag`, keeping mirror data consistent without scanning all tasks.

Next Steps
- Monitor `annika:planner:metrics` for 304/412 counts after rollout.
- Expand end-to-end regression (`tests/test_planner_regressions.py`) with ETag scenarios.

---

