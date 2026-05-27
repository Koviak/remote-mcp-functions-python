# Remote MCP Functions - Current Implementation

**Last Updated:** 2026-05-19
**Module Path:** `src/`

## Purpose

This directory hosts the Azure Functions app and local orchestration layer for
the remote MCP bridge. It starts ngrok, the local Azure Functions host, Microsoft
Graph webhooks, token services, and Planner/contact sync services.

## Startup Orchestration

| Component | Entry Point | Behavior |
| --- | --- | --- |
| Service launcher | `start_all_services.py` | Starts ngrok, launches Azure Functions Core Tools, waits for readiness, sets up webhooks, and starts sync background services. |
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
  `languageWorkers__python__defaultExecutablePath`, and `PYTHONEXECUTABLE`
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

The Annika tmux remote pane runs:

```bash
env PYTHONUNBUFFERED=1 FUNCTIONS_PYTHON_EXE=/home/joshua-koviak/miniforge3/envs/Annika_2.1/bin/python FUNC_PATH=/home/joshua-koviak/.nvm/versions/node/v24.14.1/bin/func NGROK_EXE=/home/joshua-koviak/.nvm/versions/node/v24.14.1/bin/ngrok AzureWebJobsStorage=UseDevelopmentStorage=true /home/joshua-koviak/miniforge3/envs/Annika_2.1/bin/python start_all_services.py --verbose
```

## Observability

Startup logs go to the tmux remote console and `logs/mcp_server.log`.
Graph/token/sync state is persisted through Redis-backed managers; new code
should continue using those helpers rather than direct Redis clients.
