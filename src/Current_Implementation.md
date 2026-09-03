# Remote MCP Functions - Current Implementation

**Last Updated:** 2026-09-03
**Module Path:** `src/`

## Purpose

This directory hosts the Azure Functions app and local orchestration layer for
the remote MCP bridge. It starts ngrok, the local Azure Functions host, Microsoft
Graph webhooks, token services, and Planner/contact sync services.

## Startup Orchestration

| Component | Entry Point | Behavior |
| --- | --- | --- |
| Service launcher | `start_all_services.py` | Starts ngrok, launches Azure Functions Core Tools, waits for readiness, supervises the owned Functions process, repairs unexpected child exits, sets up webhooks, and starts sync background services. |
| Function app | `function_app.py` | Registers Azure Functions HTTP triggers and background service hooks. |
| Local bootstrap | `startup_local_services.py` | Lightweight startup path for local service initialization. |
| Token cache | `mcp_redis_config.py` | Redis-backed token and configuration helpers. |
| Graph subscriptions | `graph_subscription_manager.py` | Creates, renews, and repairs Graph webhook subscriptions. |
| Planner sync | `planner_sync_service_v5.py` | Webhook-driven Planner/Annika sync engine. |

## Function Host Environment

`build_function_host_env(...)` constructs the child environment for
`func start --port 7071`.

Current behavior:
- resolves `FUNCTIONS_PYTHON_EXE` against the current host
- falls back to `sys.executable` when the configured interpreter is unusable
- sets `FUNCTIONS_PYTHON_EXE`, `languageWorkers:python:defaultExecutablePath`,
  `languageWorkers__python__defaultExecutablePath`, `FUNCTIONS_WORKER_RUNTIME`,
  and `PYTHONEXECUTABLE`
- prepends the selected Python worker directory to `PATH` so Azure Functions
  Core Tools can complete its own Python discovery
- synchronizes only the non-secret Python worker/runtime keys in
  `local.settings.json` before spawning `func`, preventing stale Windows
  interpreter paths from overriding the Linux child environment
- defaults blank `AzureWebJobsStorage` to `UseDevelopmentStorage=true`
- sets `GRAPH_RENEW_LOOP_OWNER=start_all_services` unless already configured

## Health Checks

Remote startup waits on:
- `http://localhost:7071/api/health/ready`
- fallback `http://localhost:7071/api/hello`

## Function Host Supervision

After startup succeeds, `ServiceManager.supervise_function_app(...)` blocks on
the owned Azure Functions Core Tools process rather than waiting only on the
parent launcher's shutdown event. An unexpected child exit is classified as
`parent_alive_required_child_dead` and starts an event-driven repair operation.

The repair path:
- terminates the exact owned process group and waits for port 7071 to close
- verifies any surviving listener still belongs to that group before escalating
  to `SIGKILL`; unrelated listeners are never force-killed
- starts a replacement with capped backoff and repeats until the existing
  readiness gate passes or the parent receives shutdown
- retains the same launcher process so Graph, Planner, contact, and subscription
  background ownership does not need a full wrapper recycle

Structured lifecycle records use detector
`remote_mcp.function_host_exit_supervisor.v1`, a process-unique operation ID,
reason codes, affected PID/process group, exit code, attempt, exception class,
and UTC timestamp. RSI can therefore harvest detection, cleanup escalation,
retry, and recovery as one operation.

The Annika tmux remote pane runs the Python Functions host path:

```bash
env PYTHONUNBUFFERED=1 FUNCTIONS_WORKER_RUNTIME=python FUNCTIONS_PYTHON_EXE=/home/joshua-koviak/miniforge3/envs/Annika_2.1/bin/python FUNC_PATH=/home/joshua-koviak/.nvm/versions/node/v24.14.1/bin/func NGROK_EXE=/home/joshua-koviak/.nvm/versions/node/v24.14.1/bin/ngrok AzureWebJobsStorage=UseDevelopmentStorage=true /home/joshua-koviak/miniforge3/envs/Annika_2.1/bin/python start_all_services.py --verbose
```

## Observability

Startup logs go to the managed remote stream and `logs/mcp_server.log`.
Function-host supervisor records are emitted as JSON after the stable
`[REMOTE_MCP:FUNCTION_HOST_SUPERVISOR]` marker.
Graph/token/sync state is persisted through Redis-backed managers; new code
should continue using those helpers rather than direct Redis clients.

## Teams Chat Read and Delivery

Annika's `Agent_Tools/office_teams_chat/_common.py` ENDPOINT_MAPPING is the
client half of this contract; `register_http_endpoints` in `http_endpoints.py`
is the server half. Five chat routes are registered, and the route table is
documented in a comment at the registration site
(`http_endpoints.py:2143-2147`) so the two halves can be compared by reading:

| Route | Graph call | Tool name |
| --- | --- | --- |
| `GET /api/me/chats` | `GET /me/chats` | `list_chats` |
| `GET /api/chats/{chat_id}` | `GET /chats/{chat-id}` | `get_chat` |
| `GET /api/chats/{chat_id}/members` | `GET /chats/{chat-id}/members` | `list_chat_members` |
| `GET /api/chats/{chat_id}/messages` | `GET /chats/{chat-id}/messages` | `list_chat_messages` |
| `POST /api/me/chats/messages` | `POST /chats/{chatId}/messages` or `.../replyWithQuote` | `send_chat_message` / `reply_chat_message` |

All four read handlers live in `endpoints/teams.py` and share one shape: the
route parameter is validated first, delegated `Chat.Read Chat.ReadWrite`
authority is acquired through `_get_token_and_base_for_me(...)` with the
existing application-token fallback, only Graph-supported query parameters are
forwarded, the Graph JSON body is returned unchanged on 200, and any other
Graph status is passed through as `Error: {status_code} - {text}` so the caller
sees Graph's own status rather than a synthesized one. A missing route
parameter returns 400 `Missing chat_id in URL path`; an unavailable token
returns 503 with an `auth_unavailable` JSON body. Each Graph request uses a
10 second timeout.

Route-specific behavior:

- `get_chat_http` sets `$expand=members` by default, so one call answers both
  "which chat is this" and "who is in it". A caller-supplied `$expand`
  overrides the default, and `$select` may be added to narrow the payload.
- `list_chat_members_http` forwards `$top` and `$select` only.
- `list_chat_messages_http` forwards `$top`, `$orderby`, and `$filter` only.

`POST /api/me/chats/messages` accepts the flat Annika proxy contract. A normal
message maps to Graph `POST /chats/{chatId}/messages`. When `replyToId` is
present, the handler maps the immutable source message to
`POST /chats/{chatId}/messages/replyWithQuote`, sends it in `messageIds`, and
returns the Graph JSON response as provider-delivery evidence. The legacy
compatibility handler and the modular `endpoints/teams.py` implementation share
this contract.

### Route-registration detector

An advertised-but-unregistered chat route is a recurring failure class in this
module: it presents to the caller as a per-chat 404, which reads like missing
data rather than a missing server route. It was fixed once for
`list_chat_messages` (2026-07-12) and recurred for `get_chat` and
`list_chat_members` until 2026-09-03.

`src/Tests/test_teams_contract_endpoints.py::test_chat_read_routes_are_registered_in_the_functions_app`
is the standing detector. It calls `register_http_endpoints` against a
route-capturing stand-in app and asserts that the chat read routes are actually
served. If a future ENDPOINT_MAPPING entry ever advertises a chat read route
the Functions app does not register, this test fails in the ordinary contract
suite instead of surfacing as a live 404 in a Teams conversation.

Route changes here are only live after the Functions host is restarted
(`sudo systemctl restart annika-remote-mcp.service`); until then a 404 from a
newly added route means the old host is still serving.
