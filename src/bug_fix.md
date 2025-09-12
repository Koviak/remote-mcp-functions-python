Bug Fix Log

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

