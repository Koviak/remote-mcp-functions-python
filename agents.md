# Remote MCP Functions (Python) - agents guide

## Mission and Current Focus
- Remote MCP server bridging Annika 2.x with Microsoft 365 via Azure Functions, Graph, and Redis. See `.cursor/rules/ms-mcp-system-architecture.mdc` for the architecture contract.
- Active integration work tracks the Planner <-> Annika sync fixes described in `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc`. Keep webhook-driven V5 sync healthy and aligned with the ID map and timestamp requirements in that rule.
- Uphold Redis-first design: every feature must prefer caches and queues described in `.cursor/rules/redis-component-keys-map.mdc` before talking to Graph directly. Storage policy: Persisted data MUST use RedisJSON only (no string SET/GET). Exceptions: pub/sub payloads and ephemeral counters/locks.

## Stack and Runtime
- Python 3.11 per `pyproject.toml`. Azure Functions host drives HTTP and MCP triggers (`function_app.py`). Startup automation relies on Azure Functions Core Tools and ngrok (`src/tools/func.exe`, `src/tools/ngrok.exe`).
- Redis is the source of truth for tokens, sync queues, and webhook payloads. Access patterns and key shapes live in `.cursor/rules/redis-component-keys-map.mdc` and `.cursor/rules/redis-tasks-keys-and-channels.mdc`.
- Authentication uses delegated and app tokens via the Auth and Token modules (`.cursor/rules/module_Auth_Manager.mdc`, `.cursor/rules/module_Token_Service.mdc`). Ensure credentials in `.env`/`local.settings.json` match the scope set in `.cursor/rules/active-scopes.mdc`.

## Repository Map
- `src/` - Azure Functions app, Planner sync, auth, webhook code. Start with `src/agents.md` for module-level guidance.
- `src/endpoints/` - Modular HTTP handlers for Graph services. See `src/endpoints/agents.md`.
- `src/Tests/` - Unit and integration suites plus manifest files. See `src/Tests/agents.md`.
- `infra/` - Bicep templates and deployment parameters. See `infra/agents.md`.
- `.cursor/rules/` - Canonical rules; cite these instead of historic Markdown in `src/Documentation`.
- `src/logs/` - Function host log captures. Rotate or export when investigating incidents.

## Environment Bootstrap
1. Create a virtual environment (Python 3.11): `python -m venv .venv` then `.\\.venv\\Scripts\\activate`.
2. Upgrade tooling: `python -m pip install -U pip wheel`.
3. Install runtime deps. The Azure Function host reads `requirements.txt` from `src`; keep it in sync with imports (`azure-functions`, `azure-identity`, `redis`, `aiohttp`, `requests`, `msal`, `python-dotenv`). Document any additions in this file.
4. Load secrets: copy `src/local.settings.json` to local machine (do not commit secrets) and mirror values in a `.env` file. `src/load_env.py` reads both.
5. Ensure Redis reachable (Docker, Azure Cache, or the Annika stack). Connection info is consumed by `mcp_redis_config.py`.
6. Install Azure Functions Core Tools and ngrok if you plan to run `src/start_all_services.py`. Binaries are already staged under `src/tools/`; override with `NGROK_EXE` or `FUNC_PATH` when needed.

## Core Commands
- Full local stack (`module_Start_Services.mdc`): `python src/start_all_services.py --verbose | tee .cursor/artifacts/start-all.log`. This launches ngrok, the function host, webhook handler, Planner sync V5, and chat subscriptions. Stop with `Ctrl+C` to trigger graceful shutdown.
- Lightweight startup (tokens + webhooks): `python src/startup_local_services.py` (same tee pattern for artifacts).
- Direct Function host: from `src`, run `func start --python | tee .cursor/artifacts/func-host.log`. Requires the virtual environment to be active.
- Tests: `python -m pytest src/Tests --maxfail=1 --disable-warnings -q | tee .cursor/artifacts/pytest.txt`. Use targeted runs (for example `python -m pytest src/Tests/test_redis_token_storage.py`) after module work.
- Lint: `ruff check src --output-format text | tee .cursor/artifacts/ruff.txt`. Config lives in `pyproject.toml`.
- Planner sync smoke: `python src/test_phase2_webhooks.py` with Redis seeded; review `.cursor/rules/module_Planner_Sync.mdc` for prerequisites.

## Observability and Logs
- Function host log stream: `src/logs/mcp_server.log` (rotated by deployment scripts). Copy before truncating.
- Webhook diagnostics: `python src/webhook_monitor.py --tail` surfaces Redis keys described in `.cursor/rules/module_Webhook_System.mdc`.
- Health endpoints exposed under `/api/health/ready`, `/api/sync/health`, `/api/chat_subscriptions/health`; contracts defined in `.cursor/rules/module_Function_App.mdc`.
- Redis keys for sync and tokens are enumerated in `.cursor/rules/redis-component-keys-map.mdc`. Always validate expected TTLs after changes.

## RedisJSON Conversion Initiative
**Current Status:** Planning Phase  
**Priority:** High - Aligns with Annika 2.0 architecture principle: "RedisJSON for everything we can"

### Documentation
- **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - Executive summary and overview (15 min read)
- **[REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md)** - Quick patterns for developers (30 min read)
- **[REDISJSON_CONVERSION_PLAN.md](./REDISJSON_CONVERSION_PLAN.md)** - Complete implementation plan (2 hour read)

### Key Principle
ALL task storage MUST use RedisJSON operations (`JSON.SET`, `JSON.GET`) instead of plain string operations (`SET`, `GET`). This ensures:
1. Direct compatibility with OpenAI structured outputs
2. Atomic field-level updates without full document rewrites
3. JSONPath query capabilities for filtering and searching
4. Type safety and validation at storage time

### Quick Pattern Reference
```python
# ❌ FORBIDDEN - Plain string storage
await redis.set(f"annika:tasks:{id}", json.dumps(task))
raw = await redis.get(f"annika:tasks:{id}")

# ✅ REQUIRED - RedisJSON storage
await redis.execute_command("JSON.SET", f"annika:tasks:{id}", "$", json.dumps(task))
task_json = await redis.execute_command("JSON.GET", f"annika:tasks:{id}", "$")
task = json.loads(task_json)[0] if task_json else None
```

### Files Requiring Conversion (Priority Order)
1. **CRITICAL**: `src/annika_task_adapter.py` (Lines 292-295, 229-310)
2. **CRITICAL**: `src/http_endpoints.py` (Task CRUD operations)
3. **CRITICAL**: `src/planner_sync_service_v5.py` (All task reads/writes)
4. **HIGH**: `src/endpoints/planner.py`, `src/endpoints/tasks_buckets.py`, `src/endpoints/agent_tools.py`

### Implementation Timeline
- **Week 1**: Preparation (tests, backups, monitoring)
- **Week 2**: Core adapter changes
- **Week 3**: HTTP endpoints
- **Week 4**: Sync service
- **Week 5**: Data migration
- **Week 6**: Optimization

See [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) for complete timeline and success metrics.

## Escalation and Caveats
- Token or scope failures that require tenant admin action must be escalated with evidence and a link to `.cursor/rules/active-scopes.mdc`. Never self-edit scopes without approval.
- Planner sync regressions (missing ID maps, stale timestamps) block the Annika <> Planner contract. Follow the troubleshooting checklist in `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc` and flag upstream if Redis data diverges.
- ngrok or Function host binaries missing: record the failure and update `src/tools/` or environment overrides; log in this file during review.
- Webhook 400/401 responses or subscription churn often signal configuration drift. Coordinate with the Webhook and Chat Subscription module owners per `.cursor/rules/module_Webhook_System.mdc` and `.cursor/rules/module_Chat_Subscriptions.mdc`.
- **CRITICAL**: If you find JSON blobs stored via string `SET`/`GET`, this is a HIGH PRIORITY issue. Immediately migrate to RedisJSON per [REDISJSON_QUICK_REFERENCE.md](./REDISJSON_QUICK_REFERENCE.md) and document in the conversion plan. No exceptions unless explicitly whitelisted in `.cursor/rules/redis-component-keys-map.mdc` (pub/sub payloads and ephemeral counters/locks only).

## Automation Hygiene
- When you add helper scripts (PowerShell, Python, bash), log invocation syntax, required env vars, and artifact destinations here plus the closest directory-level guide.
- Structured outputs (`.cursor/artifacts/*.log`, `.cursor/artifacts/*.json`) are mandatory for test and startup runs. Remove transient artefacts after review unless they capture a reproducible defect.
- Update this guide whenever setup steps, commands, or escalation paths change. Review the nearest `agents.md` during every PR per `.cursor/rules/agents-md.mdc`.
- Keep all module rules up to date with any changes you make.  
