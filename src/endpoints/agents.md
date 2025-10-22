## Upstream Context
- [src](../agents.md) - Azure Functions app, Planner sync, auth, and webhook implementation guide
- [Root agents.md](../../agents.md) - Remote MCP Functions mission, stack, and global workflow expectations
# endpoints module guide

## Mission
- Provide the modular HTTP surface for Microsoft Graph features exposed through the Azure Function app. The architecture and registration flow are defined in `.cursor/rules/module_HTTP_Endpoints.mdc` and `.cursor/rules/http-endpoints-modular-architecture.mdc`.
- Routes must remain compatible with the legacy import path (`http_endpoints.py`) while delegating to the modular files in this folder.

## Key files
- `common.py` centralises auth helpers, metadata manager access, and shared response helpers. Keep changes aligned with `.cursor/rules/module_Auth_Manager.mdc`, `.cursor/rules/module_Token_Service.mdc`, and `.cursor/rules/module_Graph_Metadata.mdc`.
- `admin.py`, `planner.py`, `tasks_buckets.py`, `planner_formats.py`, `mail.py`, `calendar.py`, `teams.py`, `files_sites.py`, `security_reports.py`, `agent_webhook.py`, and `agent_tools.py` each register routes via `register_endpoints(app)`. Reference the module rule above before refactoring any handler.
  - `agent_webhook.py` now exposes `POST /api/annika/task-events` for Task Manager → MS‑MCP ingress. Health metrics count these events under `annika:webhooks:notifications`.
- `users_groups.py` performs privileged user management tasks. Double-check permitted scopes in `.cursor/rules/active-scopes.mdc` when editing.
- Add new feature files only after extending `http_endpoints.py` registration to import them in a deterministic order.

## Development workflow
- Add or update routes inside the appropriate module and wire them through `http_endpoints.py` for backwards compatibility.
- Always call `get_agent_token` or the app-token helpers from `common.py`; do not instantiate credential objects per handler.
- Cache-friendly operations must use `GraphMetadataManager` helpers instead of direct Graph calls unless the rule allows otherwise.
- Update docstrings and inline comments sparingly; rely on rule cross-references for policy details.

## Testing and verification
- Unit: `python -m pytest src/Tests/test_http_delegated.py -q | tee ../../.cursor/artifacts/test-http-delegated.log` validates delegated flows.
- Planner coverage: `python -m pytest src/Tests/test_planner_sync_deletion.py -q` when touching Planner-specific handlers.
- Integration: `python -m pytest src/Tests/integration/test_http_endpoints_live.py -k <route>` requires live Graph credentials; review `.cursor/rules/module_HTTP_Endpoints.mdc` for prerequisites before running.
- Webhook ingress sanity: POST a minimal payload to `POST /api/annika/task-events` and verify Planner Sync logs increment `webhooks` in health checks and trigger a quick poll.
- When adding new endpoints, extend the manifest in `src/Tests/integration/endpoints_manifest.json` so live checks include them.

## Observability
- HTTP requests inherit logging from `function_app.py`; expand logs cautiously to avoid leaking secrets. Prefer structured dictionaries and redact tokens.
- For mutation routes, confirm they publish the expected Redis events (see `.cursor/rules/redis-component-keys-map.mdc`).
 - Storage policy: Route handlers must persist state via RedisJSON only; do not store JSON as strings. Strings allowed only for pub/sub payloads and counters.
- Webhook cache writes (`http_endpoints.py`, `agent_webhook.py`) now call the centralized `set_json` helper so Planner payloads land in RedisJSON with TTL; keep this as the single write path.
- Planner and webhook endpoints interact with sync telemetry keys noted in `.cursor/rules/module_Planner_Sync.mdc` and `.cursor/rules/module_Webhook_System.mdc`.

## Caveats and escalation
- Scopes: Any new Graph call must map to an approved scope in `.cursor/rules/active-scopes.mdc`. Escalate before introducing broader permissions.
- Response shape: Maintain JSON schema compatibility; agents depend on stable fields. Update consuming rules if a change is unavoidable.
- Error handling: Prefer raising `HttpResponse` with `status_code` and JSON body. Avoid returning raw exceptions; log them and surface sanitized payloads.
- Batch operations or long-running Graph jobs should leverage Planner sync queues instead of synchronous work here.

## Maintenance checklist
- Confirm `register_http_endpoints(app)` imports the module once and avoids circular dependencies.
- Update this file whenever you add a module, adjust testing commands, or change observability hooks. Follow `.cursor/rules/agents-md.mdc` to keep the guidance actionable.

