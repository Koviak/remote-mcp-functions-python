# Remote MCP Functions Bug Fix Log 2.0

## 2026-07-12 - Restore Teams chat read and exact-reply contracts

### Problem

- The local Annika tool advertised `GET /api/chats/{chat_id}/messages`, but the
  Azure Functions app registered no matching handler, so live reads returned a
  local 404 after chat discovery succeeded.
- The shared Teams chat POST handler used a nonexistent chat-message
  `/replies` URL when `replyToId` was present, breaking exact-origin replies.

### Solution

- Added `endpoints.teams.list_chat_messages_http` and registered
  `GET chats/{chat_id}/messages`. It validates the route parameter, uses the
  existing delegated/application token authority, forwards only Graph-supported
  query parameters, and returns the Graph JSON response.
- Both the modular and compatibility POST handlers now map `replyToId` to
  Graph `/chats/{chatId}/messages/replyWithQuote`, preserve the source ID in
  `messageIds`, and return the provider JSON receipt.

### Verification

- A real-provider Annika test reproduced the message-list 404, then passed
  after restarting only the remote MCP bridge.
- Focused remote Teams contract tests passed: 2 tests.
- Changed Python files compiled; the modular endpoint/test passed Ruff and the
  legacy compatibility module passed its focused F821 gate.
- Both contracts were checked against current Microsoft Graph v1.0
  documentation before implementation.

### 2026-07-18 21:47 CDT - Recover Required Function Host Child Exits

**Files / Functions:** `start_all_services.py::main`,
`ServiceManager.supervise_function_app`,
`ServiceManager._recover_function_app`,
`ServiceManager._cleanup_function_app_generation`, and
`Tests/test_start_all_services_runtime.py`.

**Problem / Root Cause:** The Python launcher stayed alive after its required
Azure Functions Core Tools child exited, so Planner/contact/subscription loops
could continue while port 7071 remained down indefinitely. `main()` waited only
for the parent shutdown event and never subscribed to child process completion.
The first recovery proof exposed a sibling defect: after the Core Tools leader
was killed, its listener ignored `SIGTERM`, retained the owned port, and caused
replacement generations to collide.

**Solution:** The launcher now creates an event-driven supervisor task that
blocks on the owned child process and autonomously repairs unexpected exits.
Recovery reaps the exact owned process group, verifies ownership before a
bounded `SIGKILL` escalation, confirms port release, and retries replacement
boots with capped backoff until the normal readiness gate succeeds. It never
force-kills an unrelated listener. Structured JSON events connect detection,
cleanup, retry, and completion through one operation ID.

**Class / Sweep / Detector / Prevention:** Class
`parent_alive_required_child_dead`. The sweep covered launcher wait ownership,
shutdown cancellation, Core Tools leader/listener process groups, port 7071
ownership, replacement readiness, retry backoff, and the outer Annika remote
health/restart detector. Detector
`remote_mcp.function_host_exit_supervisor.v1` records stable lifecycle and
outcome evidence. The event-driven wait, exact-group cleanup, ownership guard,
recovery loop, and positive/negative regressions prevent recurrence and give RSI
a machine-actionable repair contract.

**Testing / Live Proof:** [RED] the initial supervisor tests failed before the
methods existed. The first controlled live leader exit then proved detection but
left the owned listener alive, producing the escalation regression. [PASS] all
16 launcher runtime tests, Ruff E/F/I, `py_compile`, and `git diff --check`.
After a `remote_only` activation, a second controlled leader `SIGKILL` kept the
same wrapper alive, emitted detected/force-kill/restart/recovered events under
one operation, replaced the leader and listener on attempt one, and restored
HTTP 200 readiness. Annika strict census then reported 15/15 required services,
11 producing, four idle-by-design, and zero stale components.
