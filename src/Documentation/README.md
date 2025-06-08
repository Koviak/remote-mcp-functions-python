# Documentation Index

This folder contains technical documentation for the Remote MCP Functions project. For general usage, see the main [CONSOLIDATED_DOCUMENTATION.md](../../CONSOLIDATED_DOCUMENTATION.md).

## 📚 Documentation Categories

### 🚀 Getting Started
- **[Quick_Start_Summary.md](Quick_Start_Summary.md)** - Quick setup guide
- **[AUTOMATED_STARTUP_GUIDE.md](AUTOMATED_STARTUP_GUIDE.md)** - Automated service startup
- **[MANUAL_STARTUP_GUIDE.md](MANUAL_STARTUP_GUIDE.md)** - Manual service startup

### 🏗️ Architecture & Design
- **[Redis_First_Architecture_Summary.md](Redis_First_Architecture_Summary.md)** - Core architecture principles
- **[Redis_Caching_Integration.md](Redis_Caching_Integration.md)** - Caching implementation details
- **[MS_Graph_Webhook_Integration_COMPLETE.md](MS_Graph_Webhook_Integration_COMPLETE.md)** - Webhook integration

### 🔧 API Documentation
- **[Comprehensive_Endpoints_Summary.md](Comprehensive_Endpoints_Summary.md)** - All API endpoints overview
- **[MS_Graph_Endpoints.md](MS_Graph_Endpoints.md)** - Microsoft Graph API wrappers
- **[Mail_Calendar_Planner_Endpoints.md](Mail_Calendar_Planner_Endpoints.md)** - Specific service endpoints
- **[TOKEN_API_DOCUMENTATION.md](TOKEN_API_DOCUMENTATION.md)** - Token management APIs

### 🤖 Agent Integration
- **[Planner_Agent_Task_Creation_Guide.md](Planner_Agent_Task_Creation_Guide.md)** - How agents create and manage tasks
- **[AUTONOMOUS_AGENT_SETUP.md](AUTONOMOUS_AGENT_SETUP.md)** - Agent configuration
- **[MS_Tasks_Capabilities.md](MS_Tasks_Capabilities.md)** - Task management capabilities

### 🔐 Authentication & Security
- **[HTTP_ENDPOINTS_AUTH_GUIDE.md](HTTP_ENDPOINTS_AUTH_GUIDE.md)** - Authentication patterns
- **[DELEGATED_ACCESS_SUCCESS.md](DELEGATED_ACCESS_SUCCESS.md)** - Delegated access implementation
- **[REDIS_TOKEN_STORAGE_IMPLEMENTATION.md](REDIS_TOKEN_STORAGE_IMPLEMENTATION.md)** - Token storage security
- **[MFA_AUTHENTICATION_ISSUE.md](MFA_AUTHENTICATION_ISSUE.md)** - MFA troubleshooting

### 📋 Reference
- **[Permissions List - Organized.md](Permissions%20List%20-%20Organized.md)** - Complete permissions reference
- **[VERIFICATION_REPORT.md](VERIFICATION_REPORT.md)** - System verification procedures
- **[CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)** - Cleanup and maintenance

POST http://localhost:7071/api/planner/poll

## 🔄 Document Status

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

## 📝 Maintenance Notes

- **Primary Documentation**: Use [CONSOLIDATED_DOCUMENTATION.md](../../CONSOLIDATED_DOCUMENTATION.md) for user-facing docs
- **Technical Details**: Use files in this folder for implementation specifics
- **Updates**: When updating architecture, update both consolidated docs and relevant technical docs
- **Deprecation**: Mark outdated docs clearly and move to archive if needed

---

*Last updated: Documentation consolidation cleanup* 