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
