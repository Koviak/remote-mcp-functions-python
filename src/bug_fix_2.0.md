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
