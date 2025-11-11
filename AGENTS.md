# Remote MCP Functions (Python) – agents guide

**Upstream Context**
- [src/agents.md](mdc:src/agents.md) – Azure Functions subsystem guide.
- `.cursor/rules/ms-mcp-system-architecture.mdc` – End-to-end architecture contract for this remote MCP.

## Mission & Current Focus
- Provide a production-ready remote MCP bridge between Annika 2.x agents and Microsoft 365. Architecture contract: `.cursor/rules/ms-mcp-system-architecture.mdc`.
- Maintain webhook-first Planner sync V5. Follow `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc` for ID-map, timestamp, and queue guarantees.
- Enforce Redis-first storage (`.cursor/rules/redis-component-keys-map.mdc`, `.cursor/rules/redis-tasks-keys-and-channels-microsoft-mcp.mdc`) and RedisJSON-only persistence. Anything stored via `SET`/`GET` must be migrated or whitelisted in rules.

## Repository Orientation
- `src/` – Azure Functions host, Planner sync engines, auth flows, webhook handling. See `src/agents.md`.
- `src/endpoints/` – Modular HTTP endpoints; reference `src/endpoints/agents.md` and `.cursor/rules/module_HTTP_Endpoints.mdc`.
- `src/Tests/` – Unit/integration suites aligned with the Azure Functions surface (`src/Tests/agents.md`).
- `tests/` – Focused Annika contract regression tests (e.g., RedisJSON adapters).
- `infra/` – Bicep deployment templates (`infra/agents.md`).
- `.cursor/rules/` – Single source of truth for development patterns, API contracts, and operational checklists.
- `start-services.ps1` – Convenience launcher that delegates to `src/start_all_services.py`.

## Environment & Bootstrap
1. Activate the shared Conda environment: `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\Scripts\activate.ps1`.
2. Install/upgrade dependencies inside that environment:
   - `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pip install -U pip wheel`
   - `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pip install -r src/requirements.txt`
3. Secrets: copy `src/local.settings.json` locally (never commit) and mirror values into `.env`. `src/load_env.py` consumes both.
4. Redis access: ensure `Redis_Master_Manager_Client.py` can reach the configured instance; connection is centralized in `src/mcp_redis_config.py`.
5. Tooling: Azure Functions Core Tools (`func`) and `ngrok` are staged under `src/tools/`. Override with `FUNC_PATH` / `NGROK_EXE` env vars when using global installs.

## Entry Points & Primary Modules
- `src/function_app.py` – Azure Functions entry; health routes and MCP triggers (`.cursor/rules/module_Function_App.mdc`).
- `src/start_all_services.py` – Orchestrates ngrok, func host, webhooks, Planner sync, Teams subscriptions (`.cursor/rules/module_Start_Services.mdc`).
- `src/startup_local_services.py` – Light bootstrap for auth + webhook validation without Planner sync.
- `src/planner_sync_service_v5.py` – Active Planner sync engine; earlier versions (`_v3`, `_v4`) remain for reference only.
- `src/webhook_handler.py`, `src/setup_local_webhooks.py`, `src/webhook_monitor.py` – Webhook ingress toolchain (`.cursor/rules/module_Webhook_System.mdc`).
- `src/chat_subscription_manager.py`, `src/setup_teams_subscriptions.py` – Teams chat subscriptions (`.cursor/rules/module_Chat_Subscriptions.mdc`).
- `src/agent_auth_manager.py`, `src/token_refresh_service.py`, `src/http_auth_helper.py` – Token and scope orchestration (`.cursor/rules/module_Auth_Manager.mdc`, `.cursor/rules/module_Token_Service.mdc`, `.cursor/rules/active-scopes.mdc`).

## Key Commands (PowerShell)
```powershell
# Activate environment
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\Scripts\activate.ps1

# Full orchestrated stack (from repo root)
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe src\start_all_services.py --verbose `
  | Tee-Object .cursor\artifacts\start-all.log

# Lightweight tokens + webhooks only
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe src\startup_local_services.py `
  | Tee-Object .cursor\artifacts\startup-local.log

# Azure Functions host only (run inside src)
cd src
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pip install -r requirements.txt  # ensure deps
func start --port 7071 | Tee-Object ..\.cursor\artifacts\func-host.log

# Tests
cd ..
C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src\Tests -v `
  | Tee-Object .cursor\artifacts\pytest.txt

# Lint
ruff check src --output-format text | Tee-Object .cursor\artifacts\ruff.txt
```
Confirm commands after toolchain updates and document any new scripts you add.

## Observability & Logs
- Azure Functions host logs: `src/logs/mcp_server.log` (rotate after incident capture).
- Health endpoints: `/api/health/ready`, `/api/sync/health`, `/api/chat_subscriptions/health` (spec in `.cursor/rules/module_Function_App.mdc`).
- Planner + webhook diagnostics: `src/webhook_monitor.py --tail`; Redis keys enumerated in `.cursor/rules/module_Webhook_System.mdc`.
- Redis telemetry: token storage under `ms_mcp:tokens:*`, Planner sync metrics under `annika:planner:*`. Use helpers in `mcp_redis_config.py` rather than raw clients.

## Relevant Rules
- `.cursor/rules/ms-mcp-system-architecture.mdc`
- `.cursor/rules/module_Start_Services.mdc`
- `.cursor/rules/module_Function_App.mdc`
- `.cursor/rules/module_Planner_Sync.mdc`
- `.cursor/rules/module_HTTP_Endpoints.mdc`
- `.cursor/rules/redis-component-keys-map.mdc`
- `.cursor/rules/redis-tasks-keys-and-channels-microsoft-mcp.mdc`

## Escalate When
- Scope or tenant permission drifts: capture logs + reference `.cursor/rules/active-scopes.mdc`.
- Planner sync divergence (missing mappings, stale timestamps, repeated 4xx/5xx): follow `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc` and escalate with Redis snapshots.
- Redis schema violations (string storage, WRONGTYPE errors, missing TTLs) – stop work, migrate to RedisJSON using sanctioned helpers, update conversion checklist.
- Ngrok or Azure Functions Core Tools not discoverable – update `src/tools/`, document overrides, and record in this guide.

## Keep This Guide Current
- Review during every PR touching bootstrap commands, environment variables, tooling, or rule references.
- Test each documented command inside `Annika_2.1` before publishing updates.
- Cross-link new rules or module guides rather than duplicating implementation details.
