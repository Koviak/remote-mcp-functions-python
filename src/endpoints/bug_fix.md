## 2026-07-12 - Register the missing chat-message list route

### Problem
- Annika advertised `GET /api/chats/{chat_id}/messages`, but the Azure
  Functions app had neither a registered route nor a modular handler.
- Live chat discovery worked while every subsequent message read returned a
  local 404, blocking exact Teams conversation replay.

### Solution
- Added `list_chat_messages_http` in `endpoints/teams.py` and registered
  `GET chats/{chat_id}/messages` in `http_endpoints.py`.
- The handler validates `chat_id`, uses the existing delegated/app token
  authority, forwards only supported Graph query parameters, and returns the
  Graph JSON response.

### Verification
- A real-provider regression reproduced the 404 before the fix and passed
  after restarting only the remote bridge.
- Focused remote Teams contract tests passed; changed Python files compiled and
  passed the scoped Ruff gates.
- Microsoft Graph v1.0 documentation was checked before implementation.

---

## 2026-07-12 - Fix Microsoft Graph chat quote-reply endpoint

### Problem
- `post_chat_message_http` treated `replyToId` as
  `/chats/{chatId}/messages/{messageId}/replies`.
- That URL shape is not the Microsoft Graph chat reply contract and broke
  exact-origin Annika status/completion replies.

### Solution
- Updated the modular and legacy-compatible handlers to call
  `POST /chats/{chatId}/messages/replyWithQuote`.
- The source message is sent in `messageIds` and the outbound chat message is
  sent under `replyMessage`.
- Successful quote replies return the provider JSON body so callers retain the
  Graph message ID as delivery evidence.

### Verification
- `conda run -n Annika_2.1 python -m pytest src/Tests/test_teams_contract_endpoints.py -q --tb=short -p no:cacheprovider` selected contract tests: 2 passed.
- Full Ruff passed for the modular endpoint/test; the legacy compatibility
  module passed the focused F821 undefined-name gate (it retains unrelated
  pre-existing style findings).
- Python compilation of all three changed files passed.

---

## 2026-02-17 - Mail endpoint contract expansion for Outlook agent operations

### Problem
- Endpoint contracts for mail compose operations were too narrow for full Outlook agent support.
- No dedicated endpoint existed for read/unread state toggling.

### Solution
- Updated `mail.py`:
  - Added canonical message payload normalization helpers.
  - Hardened draft/send parsing and validation.
  - Added `mark_as_read_http` endpoint behavior.

### Verification
- Contract tests in `src/Tests/test_mail_contract_endpoints.py` pass.

### Post-Restart Verification
- Pending user restart confirmation.

---

## 2026-02-17 - Fix Graph search/orderby conflict in inbox listing

### Problem
- Outlook search calls through `list_inbox_http` failed with Graph error:
  - `SearchWithOrderBy: The query parameter '$orderBy' is not supported with '$search'.`
- Cause: endpoint always applied default `$orderby=receivedDateTime desc` even when `$search` was provided.

### Solution
- Updated `mail.py` in `list_inbox_http`:
  - Build base query params without `$orderby`.
  - Apply `$search` when provided.
  - Apply default/explicit `$orderby` **only when search is absent**.

### Verification
- Unit tests in `src/Tests/test_mail_contract_endpoints.py` now assert:
  - search requests omit `$orderby`
  - non-search requests retain default ordering
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest src/Tests/test_mail_contract_endpoints.py -q`
- Result: PASS

### Post-Restart Verification
- Pending user restart confirmation for live endpoint behavior in running MS-MCP service.

---

## 2026-03-10 - Delegated Microsoft To Do endpoint module

### Problem
- The remote MCP HTTP surface exposed Planner task routes but not delegated Microsoft To Do task-list/task CRUD endpoints.
- Agents had a delegated MCP tool for creating a To Do task, but there was no matching HTTP route family for list discovery, task reads, task updates, or deletes.

### Solution
- Added `src/endpoints/todo.py` with delegated handlers for:
  - listing To Do lists
  - listing tasks inside a list
  - creating a task in an explicit list or the detected default list
  - getting, updating, and deleting a task inside a list
- Added To Do-only delegated-user selection (`joshua`, `annika`) with Joshua as the default.
- Updated `src/endpoints/agents.md` to document the new module and its focused test command.

### Verification
- `C:\Users\JoshuaKoviak\.conda\envs\Annika_2.1\python.exe -m pytest ..\remote-mcp-functions-python\src\Tests\test_todo_http_endpoints.py -q -p no:cacheprovider`

### Post-Restart Verification
- Pending user restart confirmation for live `me/todo/*` HTTP behavior.
