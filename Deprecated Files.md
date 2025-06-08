discover_teams_chats.py
update_settings.py
check_chat_messages.py
sync_env_to_settings.py
find_annika_chats.py
planner_sync_service_v3.py
setup_teams_subscriptions.py
planner_sync_service_v4.py
setup_local_webhooks.py
listen_for_teams_messages.py
test_v5_sync.py
test_webhook_permissions_simple.py
generate_agent_certificate.py
http_auth_helper.py
test_webhook_flow.py
webhook_monitor.py
test_phase2_webhooks.py
test_phase2_comprehensive.py
check_subscriptions.py
test_teams_webhooks.py
test_phase2_simple.py


### Outdated Planner Sync Services
- `src/planner_sync_service.py` (original version)
- `src/planner_sync_service_v2.py` (superseded by V5)
- `src/planner_sync_service_v3.py` (superseded by V5)
- `src/planner_sync_service_v4.py` (superseded by V5)

**Reason**: V5 is the current production implementation with webhook-driven architecture

### Current (V5 Architecture)
- Redis_First_Architecture_Summary.md
- MS_Graph_Webhook_Integration_COMPLETE.md
- Comprehensive_Endpoints_Summary.md
- TOKEN_API_DOCUMENTATION.md

### Reference Only
- VERIFICATION_REPORT.md
- CLEANUP_SUMMARY.md
- MFA_AUTHENTICATION_ISSUE.md

### Legacy (Kept for Historical Reference)
- AUTOMATED_STARTUP_GUIDE.md (superseded by start_all_services.py)
- MANUAL_STARTUP_GUIDE.md (superseded by consolidated docs)


Additionally, Annika_1.0.md contains details of an old architecture (not referenced elsewhere), so it can also be treated as historical.