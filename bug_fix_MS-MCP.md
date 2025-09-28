# MS-MCP Bug Fix Summary

- Planner sync now gates polling on webhook availability, memoizes plan/bucket discovery, and reuses a shared HTTP session for Graph calls.
- Webhook status tracking logs subscription metadata plus last-event timestamps and dynamically throttles polling.
- Planner CRUD flows handle 403/412 fallbacks, cache plan selections, and manage Redis processed/pending queues per spec.
- Health monitoring honors a configurable 5-minute TTL for `annika:sync:health`, and housekeeping respects the same TTL.
- Teams chat subscription manager records persistent metadata (`mode`, timestamps) for both global and per-chat subscriptions.
