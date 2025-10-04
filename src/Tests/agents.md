## Upstream Context
- [src](../agents.md) - Azure Functions app, Planner sync, auth, and webhook implementation guide
- [Root agents.md](../../agents.md) - Remote MCP Functions mission, stack, and global workflow expectations
# Tests module guide

## Purpose
- Exercises authentication, HTTP endpoints, Planner sync, webhooks, and subscription flows for the remote MCP stack. Treat the suites here as the guardrails for `.cursor/rules/module_Auth_Manager.mdc`, `.cursor/rules/module_HTTP_Endpoints.mdc`, `.cursor/rules/module_Planner_Sync.mdc`, `.cursor/rules/module_Webhook_System.mdc`, and `.cursor/rules/module_Chat_Subscriptions.mdc`.

## Suite layout
- Root tests target discrete modules (`test_agent_auth.py`, `test_redis_token_storage.py`, `test_token_api_endpoints.py`, etc.). They rely on fixtures defined alongside each module and expect Redis + environment variables to be present.
- `integration/` contains live Graph coverage (`test_http_endpoints_live.py`) and the manifest `endpoints_manifest.json`. Run these only against authorised tenants with the scopes listed in `.cursor/rules/active-scopes.mdc`.
- Phase-2 scripts (`test_phase2_*`) simulate end-to-end Planner sync and webhook behaviour. They require Annika-side Redis keys populated according to `.cursor/rules/planner-annika-sync-fixes-and-trace.mdc`.

## Running tests
- Default regression: `python -m pytest src/Tests --maxfail=1 --disable-warnings -q | tee ../../.cursor/artifacts/pytest.txt` (re-use the same artifact when triggered from the repo root).
- Focused module checks: `python -m pytest src/Tests/test_agent_auth.py -q`, `python -m pytest src/Tests/test_token_api_endpoints.py -q`, etc. Capture logs under `.cursor/artifacts/` using descriptive names.
- Integration sweep: `python -m pytest src/Tests/integration/test_http_endpoints_live.py --maxfail=1 --disable-warnings -k planner | tee ../../.cursor/artifacts/pytest-integration.txt`. Requires live Azure credentials, Redis, and ngrok tunnel per `.cursor/rules/module_Start_Services.mdc`.
- Planner sync regression: `python -m pytest src/test_v5_sync.py -q | tee ../.cursor/artifacts/pytest-v5-sync.txt` after modifying sync internals.

## Fixtures and environment
- Load `.env` or `local.settings.json` before running tests so `load_env.py` can hydrate settings. Some suites import modules at collection time.
- Redis is mandatory for token, webhook, and sync tests. Point `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD` to the correct environment.
- Live integration requires valid delegated scopes, webhook URL, and DEFAULT_PLANNER_PLAN_ID. Verify via startup scripts before running.

## Maintenance
- Update manifests and expected payloads when adding endpoints or changing response formats.
- Prefer deterministic test data; store any large fixtures inside `.cursor/artifacts/` during runs and clean up afterwards.
- Keep this guide aligned with new suites, fixtures, or command changes. Follow `.cursor/rules/agents-md.mdc` during reviews and mention adjustments in summaries.

