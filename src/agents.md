## Upstream Context
- [Root agents.md](../agents.md) - Remote MCP Functions mission, stack, runtime environment, and global workflow expectations
# src subsystem guide

## Folder mission
- Hosts the Azure Functions app and background services that make the remote MCP bridge run. Follow `.cursor/rules/ms-mcp-system-architecture.mdc` for the overarching design.
- Implements authentication, Planner sync, webhook ingestion, and HTTP surface area for Microsoft Graph. All behaviour here must respect the Redis-first contracts defined in `.cursor/rules/redis-component-keys-map.mdc` and `.cursor/rules/redis-tasks-keys-and-channels.mdc`.

## Entry points and modules
- `function_app.py` bootstraps the Azure Functions host, MCP triggers, and background threads. See `.cursor/rules/module_Function_App.mdc` for lifecycle and health-route requirements.
- `http_endpoints.py` plus the modular files under `endpoints/` expose Graph REST routes. The canonical contract lives in `.cursor/rules/module_HTTP_Endpoints.mdc` and `.cursor/rules/http-endpoints-modular-architecture.mdc`.
- `planner_sync_service_v5.py` is the active webhook-driven sync engine. Guard its queues, ID maps, and timestamp logic with `.cursor/rules/module_Planner_Sync.mdc` and `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc`.
- `webhook_handler.py`, `setup_local_webhooks.py`, and `webhook_monitor.py` manage webhook ingress and diagnostics. Reference `.cursor/rules/module_Webhook_System.mdc` before touching them.
- `chat_subscription_manager.py`, `setup_teams_subscriptions.py`, and supporting scripts handle Teams chat subscriptions. Rules: `.cursor/rules/module_Chat_Subscriptions.mdc`.
- `agent_auth_manager.py`, `dual_auth_manager.py`, and `http_auth_helper.py` own delegated/app token acquisition. Keep scope normalisation aligned with `.cursor/rules/module_Auth_Manager.mdc` and `.cursor/rules/active-scopes.mdc`.
- `token_refresh_service.py` and `mcp_redis_config.py` maintain the Redis-backed token cache. Behaviour is documented in `.cursor/rules/module_Token_Service.mdc`.
- `start_all_services.py` and `startup_local_services.py` orchestrate local automation. Follow `.cursor/rules/module_Start_Services.mdc` for process management and shutdown sequencing.
- Legacy design notes inside `Documentation/` are historical. Treat `.cursor/rules/*.mdc` as the source of truth and update those when behaviour changes.

## Local commands
- Full orchestration: `python start_all_services.py --verbose | tee ../.cursor/artifacts/start-all.log` (run from `src`). Stops cleanly with `Ctrl+C`; confirm each stage in the log before committing.
- Lightweight bootstrap: `python startup_local_services.py | tee ../.cursor/artifacts/startup-local.log` to validate tokens and webhook registration without Planner sync.
- Function host only: `func start --python | tee ../.cursor/artifacts/func-host.log` with your virtual environment activated.
- Planner sync smoke: `python test_phase2_webhooks.py | tee ../.cursor/artifacts/phase2-webhooks.log`. Ensure Redis has the Annika task schema seeded first.
- Webhook diagnostics: `python webhook_monitor.py --tail | tee ../.cursor/artifacts/webhook-monitor.log` to watch Redis channels listed in `.cursor/rules/module_Webhook_System.mdc`.
- When you add scripts, document CLI flags, required environment variables, and output paths here.

## Observability and state
- Function host emits to `logs/mcp_server.log`; rotate or copy before truncating. Planner sync writes structured health snapshots to Redis keys enumerated in `.cursor/rules/module_Planner_Sync.mdc`.
- Token cache and auth metrics live under `annika:tokens:*` and related sets. Use `mcp_redis_config.py` helpers instead of raw Redis clients.
- Webhook + chat subscription status keys are captured in `.cursor/rules/module_Webhook_System.mdc` and `.cursor/rules/module_Chat_Subscriptions.mdc`. Verify TTLs after modifying renewal loops.

## Escalation cues and caveats
- Never instantiate `redis.Redis` directly in new code; reuse `mcp_redis_config.get_redis_token_manager()` or the async helpers already present.
- Planner sync timestamp or ID mapping regressions break the Annika contract. If you observe divergence, follow the remediation steps in `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc` and escalate alongside logs.
- Scope changes, new delegated permissions, or token refresh failures require tenant approval. Reference `.cursor/rules/active-scopes.mdc` and capture evidence before escalating.
- When adding endpoints, update the modular registration and associated tests (`src/Tests/test_http_delegated.py`, integration manifest). Keep response schemas backward compatible unless the rule set is updated.

## Keep this guide current
- Update this file whenever you introduce a new module, change bootstrap commands, or modify Redis contracts. Cross-check `.cursor/rules/agents-md.mdc` during reviews and note adjustments in your PR summary.

