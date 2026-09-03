## Bug-Fix Index

| ID | Timestamp | Component | Tags | Lines |
|----|-----------|-----------|------|-------|
| [BUG-2026-09-03-001](#bug-2026-09-03-001) | 2026-09-03T16:50:45-05:00 | remote-mcp-functions-python/src/endpoints/teams.py | [P1][FIX][MCP][TEST] | +306 -0 |
| legacy | - | - | - | 4 entries grandfathered |

---
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

---

### 2026-09-03T16:50:45-05:00 BUG-2026-09-03-001 [P1][FIX][MCP][TEST]

#### Problem
| Problem | Severity | Component |
|---------|----------|-----------|
| `Agent_Tools/office_teams_chat/_common.py` ENDPOINT_MAPPING (L35-75) advertised 18 chat tools, but the Azure Functions app registered only three chat routes (GET me/chats, GET chats/{chat_id}/messages, POST me/chats/messages). `get_chat` and `list_chat_members` therefore returned 404 for every chat id, and the Teams Chat Agent rationalized this in a live Teams group chat (M060) as a per-chat "local Graph shim bug" rather than a permanent, server-side contract gap. State unchanged since commit 3cceedb (2026-07-12). | P1 | remote-mcp-functions-python/src/endpoints/teams.py |

#### Root-Cause
| Root-Cause | Root-Cause-ID |
|------------|---------------|
| The server-side handlers were never written when ENDPOINT_MAPPING was authored to advertise them: `endpoints/teams.py` contained only `list_teams_http`, `list_channels_http`, `post_channel_message_http`, `list_chats_http`, `list_chat_messages_http` and `post_chat_message_http`. This is the identical class the 2026-07-12 `bug_fix_2.0.md` entry fixed for `list_chat_messages` -- a mapped-but-unregistered route -- and no detector was added then, so it recurred silently for two more routes. | mapped_but_unregistered_route |

#### Fix-Summary
| Fix-Summary | Files-Modified | Lines-Changed |
|-------------|----------------|---------------|
| Added `endpoints/teams.py::get_chat_http` (Graph GET /chats/{chat-id}, `$expand=members` by default, caller may override `$expand` and add `$select`) and `endpoints/teams.py::list_chat_members_http` (Graph GET /chats/{chat-id}/members, forwards `$top`/`$select`). Both mirror `list_chat_messages_http` exactly: delegated `_get_token_and_base_for_me("Chat.Read Chat.ReadWrite")` with the existing application-token fallback, 400 "Missing chat_id in URL path", 503 `auth_unavailable` JSON, and `Error: {status_code} - {text}` passthrough carrying Graph's own status, on the same 10s timeout. Registered as GET chats/{chat_id} and GET chats/{chat_id}/members at `http_endpoints.py:2150` and `:2152`, with a new route-table comment at `:2143-2147` mapping all five chat routes to their tool names. | src/endpoints/teams.py, src/http_endpoints.py, src/Tests/test_teams_contract_endpoints.py | +306 -0 |

#### Verification
| Test-File | Result | Notes |
|-----------|--------|-------|
| src/Tests/test_teams_contract_endpoints.py | PASS | RED 10 failed / 2 passed before the handlers existed; GREEN 12 passed after (10 new tests). Regression sweep `timeout 900 python -m pytest src/Tests/test_teams_contract_endpoints.py src/Tests/test_http_delegated.py src/Tests/test_chat_tools.py src/Tests/test_webhook_teams_chat_routing.py -q --no-header -p no:cacheprovider` -> 17 passed. ruff (E501,F,E,I,UP,A) and py_compile clean. NOT RESTART-VERIFIED: live Graph proof requires `sudo systemctl restart annika-remote-mcp.service`, which this pass did not perform; after that restart the expected result is `{"status": "success", ...}` from both `get_chat` (id, chatType oneOnOne, topic, expanded members array) and `list_chat_members` (value array with the two aadUserConversationMember entries 27eefddd and 5ac3e02f). A 404 after restart would then mean a genuine Graph chat-not-found rather than a missing route, subject to the open `_common.py:260` handoff that currently masks that distinction. |

#### Impact
| Signal-Tags | Signal-Count |
|-------------|--------------|
| get_chat,list_chat_members,chat_read_route_registration | 3 |

#### References
| Link | Description |
|------|-------------|
| src/bug_fix_2.0.md 2026-07-12 entry | Prior instance of the same class, fixed for `list_chat_messages` without adding a detector. |
| src/endpoints/teams.py | Class: `mapped_but_unregistered_route` -- ENDPOINT_MAPPING advertises a Graph proxy route the Azure Functions app never registers, so the tool returns 404 for every input and callers misread a permanent contract gap as per-chat data trouble. |
| src/http_endpoints.py:2140-2156 | Sweep: audited every chat route ENDPOINT_MAPPING claims against `register_http_endpoints`. Three were served (me/chats, chats/{chat_id}/messages, me/chats/messages); the two missing ones (chats/{chat_id}, chats/{chat_id}/members) are now registered. No advertised chat read route remains unregistered. |
| src/Tests/test_teams_contract_endpoints.py::test_chat_read_routes_are_registered_in_the_functions_app | Detector: registers `register_http_endpoints` against a route-capturing app and fails if any ENDPOINT_MAPPING-advertised chat read route is ever unregistered again. |
| src/http_endpoints.py:2143-2147 | Prevention: the route-table comment maps all five chat routes to their tool names at the registration site, and the route-registration detector runs with the ordinary contract suite so the next recurrence fails in pytest instead of in a live Teams chat. |
