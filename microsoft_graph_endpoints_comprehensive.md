# Comprehensive Microsoft Graph Endpoints (with Agent-Facing Annotations)

This document provides a complete, intelligently organized catalog of endpoints used in the MCP Functions project, annotated for remote agent developers.

**Legend:**
- **[AGENT-FACING]**: Call this MCP HTTP API endpoint from your agent code.
- **[INTERNAL]**: MCP server calls this Microsoft Graph endpoint internally; agents do NOT call this directly.

**Base URL**: `https://graph.microsoft.com/v1.0`  
**Beta URL**: `https://graph.microsoft.com/beta`

## Implementation Status Legend
- ✅ **Implemented**: Fully implemented with HTTP endpoints
- 🔄 **Sync Service**: Used in sync services and background processes  
- 📊 **Metadata Cache**: Cached in Redis for performance
- 🔗 **Webhook**: Webhook subscription available
- 📋 **Documented**: Available in documentation but not implemented

---

## 1. Authentication & Token Management

### Core Authentication
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/auth/me` | `GET /api/auth/me` | Get current agent profile |
| [INTERNAL] | GET | `/me` | | MCP calls Graph for user info |
| [INTERNAL] | GET | `/organization` | | MCP calls Graph for tenant info |

### Token Scopes Used
- `https://graph.microsoft.com/.default` - Application permissions
- `User.Read` - Basic user profile
- `Mail.ReadWrite` - Email operations
- `Calendars.ReadWrite` - Calendar operations
- `Tasks.ReadWrite` - Planner operations
- `Group.ReadWrite.All` - Group management

---

## 2. User & Identity Management

### User Operations
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/users` | `GET /api/users` | List all users |
| [AGENT-FACING] | GET | `/api/users/{user_id}` | `GET /api/users/123` | Get specific user |
| [INTERNAL] | GET | `/users` | | MCP calls Graph for user list |
| [INTERNAL] | GET | `/users/{user-id}` | | MCP calls Graph for user details |
| [INTERNAL] | GET | `/users/{user-id}/memberOf` | | MCP calls Graph for group memberships |

### User Profile Extensions
```text
/users/{id}?$select=id,displayName,mail,userPrincipalName,jobTitle,department
```

---

## 3. Group & Team Management

### Group Operations
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/groups` | `GET /api/groups` | List all groups |
| [AGENT-FACING] | GET | `/api/groups/{group_id}` | `GET /api/groups/456` | Get specific group |
| [INTERNAL] | GET | `/groups` | | MCP calls Graph for group list |
| [INTERNAL] | GET | `/groups/{group-id}` | | MCP calls Graph for group details |

### Group Filtering
```text
/groups?$filter=groupTypes/any(c:c eq 'Unified')&$select=id,displayName,description,mail
```

---

## 4. Microsoft Planner (Task Management)

### Plan Management
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/planner/plans` | `GET /api/planner/plans` | List all plans |
| [AGENT-FACING] | GET | `/api/planner/plans/{plan_id}` | `GET /api/planner/plans/789` | Get specific plan |
| [INTERNAL] | GET | `/planner/plans` | | MCP calls Graph for plan list |
| [INTERNAL] | GET | `/planner/plans/{plan-id}` | | MCP calls Graph for plan details |

### Task Management
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/planner/tasks` | `GET /api/planner/tasks` | List all tasks |
| [AGENT-FACING] | POST | `/api/planner/tasks` | `POST /api/planner/tasks` | Create a new task |
| [AGENT-FACING] | GET | `/api/planner/tasks/{task_id}` | `GET /api/planner/tasks/202` | Get specific task |
| [AGENT-FACING] | PATCH | `/api/planner/tasks/{task_id}` | `PATCH /api/planner/tasks/202` | Update a task |
| [INTERNAL] | GET | `/planner/tasks` | | MCP calls Graph for task list |
| [INTERNAL] | POST | `/planner/tasks` | | MCP calls Graph to create task |
| [INTERNAL] | GET | `/planner/tasks/{task-id}` | | MCP calls Graph for task details |

### Bucket Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/planner/plans/{plan-id}/buckets` | ✅ | List plan buckets | GET | `list_buckets_http()` |
| `/planner/buckets` | ✅ | Create bucket | POST | `create_bucket_http()` |
| `/planner/buckets/{bucket-id}` | ✅📊 | Get/Update/Delete bucket | GET/PATCH/DELETE | Full CRUD + cache |

### Task Board Formats
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/planner/tasks/{task-id}/assignedToTaskBoardFormat` | ✅ | Get assigned-to format | GET | `get_assigned_to_format_http()` |
| `/planner/tasks/{task-id}/bucketTaskBoardFormat` | ✅ | Get bucket format | GET | `get_bucket_format_http()` |
| `/planner/tasks/{task-id}/progressTaskBoardFormat` | ✅ | Get progress format | GET | `get_progress_format_http()` |

---

## 5. Mail & Messaging

### Core Mail Operations
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/mail/messages` | `GET /api/mail/messages` | List inbox messages |
| [AGENT-FACING] | POST | `/api/mail/messages` | `POST /api/mail/messages` | Send a new message |
| [AGENT-FACING] | GET | `/api/mail/messages/{message_id}` | `GET /api/mail/messages/abc` | Get specific message |
| [INTERNAL] | GET | `/me/messages` | | MCP calls Graph for messages |
| [INTERNAL] | POST | `/me/sendMail` | | MCP calls Graph to send mail |

### Message Actions
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/messages/{message-id}/move` | ✅ | Move message | POST | `move_message_http()` |
| `/me/messages/{message-id}/copy` | ✅ | Copy message | POST | `copy_message_http()` |
| `/me/messages/{message-id}/reply` | ✅ | Reply to message | POST | `reply_to_message_http()` |
| `/me/messages/{message-id}/replyAll` | ✅ | Reply all | POST | `reply_all_http()` |
| `/me/messages/{message-id}/forward` | ✅ | Forward message | POST | `forward_message_http()` |

### Mail Folders
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/mailFolders` | ✅ | List mail folders | GET | `list_mail_folders_http()` |
| `/me/mailFolders/{folder-id}` | ✅ | Get specific folder | GET | Folder operations |
| `/users/{user-id}/mailFolders` | ✅ | List user's folders | GET | `list_user_mail_folders_http()` |

### Attachments
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/messages/{message-id}/attachments` | ✅ | List/Add attachments | GET/POST | `list_attachments_http()` |

---

## 6. Calendar & Events

### Calendar Management
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/calendar/events` | `GET /api/calendar/events` | List calendar events |
| [AGENT-FACING] | POST | `/api/calendar/events` | `POST /api/calendar/events` | Create a new event |
| [AGENT-FACING] | GET | `/api/calendar/events/{event_id}` | `GET /api/calendar/events/evt1` | Get specific event |
| [INTERNAL] | GET | `/me/events` | | MCP calls Graph for events |
| [INTERNAL] | POST | `/me/events` | | MCP calls Graph to create event |

### Event Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/events/{event-id}` | ✅ | Get/Update/Delete event | GET/PATCH/DELETE | Full CRUD operations |
| `/me/events/{event-id}/accept` | ✅ | Accept event | POST | `accept_event_http()` |
| `/me/events/{event-id}/decline` | ✅ | Decline event | POST | `decline_event_http()` |

---

## 7. Microsoft Teams Integration

### Teams & Channels
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/teams` | `GET /api/teams` | List all teams |
| [AGENT-FACING] | GET | `/api/teams/{team_id}/channels` | `GET /api/teams/123/channels` | List team channels |
| [INTERNAL] | GET | `/teams` | | MCP calls Graph for teams |
| [INTERNAL] | GET | `/teams/{team-id}/channels` | | MCP calls Graph for channels |

### Chats & Messages
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/teams/chats` | `GET /api/teams/chats` | List user chats |
| [AGENT-FACING] | POST | `/api/teams/chats/messages` | `POST /api/teams/chats/messages` | Send message to chat |
| [AGENT-FACING] | POST | `/api/teams/chats/messages/reply` | `POST /api/teams/chats/messages/reply` | Reply to chat message |
| [INTERNAL] | GET | `/me/chats` | | MCP calls Graph for chats |
| [INTERNAL] | POST | `/chats/{chat-id}/messages` | | MCP calls Graph to send message |
| [INTERNAL] | POST | `/chats/{chat-id}/messages/{message-id}/replies` | | MCP calls Graph to reply |

### Teams Chat Management (Enhanced)

### Chat Discovery & Management
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | GET | `/api/teams/chats` | `GET /api/teams/chats` | List user's chats |
| [AGENT-FACING] | GET | `/api/teams/chats/{chat_id}/members` | `GET /api/teams/chats/123/members` | List chat members |
| [INTERNAL] | GET | `/me/chats/{chat-id}/members` | | MCP calls Graph for chat members |

### Chat Message Operations
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [AGENT-FACING] | POST | `/api/teams/chats/messages` | `POST /api/teams/chats/messages` | Send message to chat |
| [AGENT-FACING] | POST | `/api/teams/chats/messages/reply` | `POST /api/teams/chats/messages/reply` | Reply to chat message |
| [AGENT-FACING] | GET | `/api/teams/chats/{chat_id}/messages` | `GET /api/teams/chats/123/messages` | List messages in chat |
| [INTERNAL] | POST | `/chats/{chat-id}/messages` | | MCP calls Graph to send message |
| [INTERNAL] | POST | `/chats/{chat-id}/messages/{message-id}/replies` | | MCP calls Graph to reply |
| [INTERNAL] | GET | `/me/chats/{chat-id}/messages` | | MCP calls Graph for chat messages |

### Chat Webhook Subscriptions
| MCP API Endpoint | Method | Path | Example | Notes |
|------------------|--------|------|---------|-------|
| [INTERNAL] | POST | `/me/chats/getAllMessages` | | MCP sets up webhook for user chat messages |
| [INTERNAL] | POST | `/chats/getAllMessages` | | MCP sets up webhook for tenant chat messages |
| [INTERNAL] | POST | `/chats/{chat-id}/messages` | | MCP sets up webhook for specific chat |

### Chat Message Format
```json
{
  "body": {
    "content": "Hello from Annika!",
    "contentType": "text"
  },
  "importance": "normal"
}
```

### Reply Message Format
```json
{
  "body": {
    "content": "This is a reply to your message",
    "contentType": "text"
  },
  "replyToId": "message-id-to-reply-to"
}
```

---

## 8. Files & SharePoint

### OneDrive Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/drives` | ✅ | List user drives | GET | `list_drives_http()` |
| `/me/drive/root/children` | ✅ | List drive items | GET | `list_drive_items_http()` |
| `/drives/{drive-id}/items/{item-id}/content` | ✅ | Download file | GET | `download_file_http()` |

### SharePoint Sites
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/sites?search={query}` | ✅ | Search sites | GET | `sites_search_http()` |

---

## 9. Webhook Subscriptions

### Subscription Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/subscriptions` | 🔗 | Create/List subscriptions | POST/GET | Webhook setup |
| `/subscriptions/{subscription-id}` | 🔗 | Update/Delete subscription | PATCH/DELETE | Webhook management |

### Active Webhook Resources
| Resource | Client State | Purpose | Implementation |
|----------|-------------|---------|----------------|
| `/groups` | `annika_groups_webhook_v5` | Group changes | Planner sync trigger |
| `/chats` | `annika_teams_chats_v5` | Chat events | Teams integration |
| `/teams/getAllChannels` | `annika_teams_channels_v5` | Channel events | Teams integration |
| `/me/chats/getAllMessages` | `annika_user_chat_messages` | User chat messages | Message monitoring (delegated) |
| `/chats/getAllMessages` | `annika_tenant_chat_messages` | Tenant chat messages | Message monitoring (app permissions) |
| `/chats/{chat-id}/messages` | `annika_chat_{chat-id}` | Specific chat messages | Individual chat monitoring |

---

## 10. Reports & Analytics

### Usage Reports
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/reports/{report-name}` | ✅ | Get usage reports | GET | `get_reports_http()` |

---

## 11. Security & Compliance

### Security Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/security/alerts` | ✅ | List security alerts | GET | `list_security_alerts_http()` |

---

## 12. Device Management

### Intune Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/deviceManagement/managedDevices` | ✅ | List managed devices | GET | `list_managed_devices_http()` |

---

## 13. Specialized Query Parameters

### Common OData Parameters
```text
$select=id,displayName,mail,userPrincipalName,jobTitle,department
$filter=groupTypes/any(c:c eq 'Unified')
$top=5
$orderby=displayName
$expand=members
```

### Time Zone Handling
```text
Prefer: outlook.timezone="Pacific Standard Time"
```

### Immutable IDs
```text
Prefer: IdType="ImmutableId"
```

### ETag Handling (Planner)
```text
If-Match: W/"JzEtVGFzayAgQEBAQEBAQEBAQEBAQEBAWCc="
```

---

## 14. Error Handling & Rate Limits

### Common HTTP Status Codes
- `200 OK` - Success
- `201 Created` - Resource created
- `204 No Content` - Success with no response body
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - ETag mismatch (Planner)
- `429 Too Many Requests` - Rate limit exceeded

### Rate Limiting
- **Planner**: 300 requests per 5 minutes per app per tenant
- **Mail**: 10,000 requests per 10 minutes per app per mailbox
- **General**: Varies by service, typically 10,000-30,000 requests per hour

---

## 15. Implementation Architecture

### Token Management
- **Agent Tokens**: Stored in `annika:tokens:agent:{scope}`
- **User Tokens**: Stored in `annika:tokens:user:{user_id}:{scope}`
- **Automatic Refresh**: Background service refreshes tokens before expiration

### Caching Strategy
- **Metadata Cache**: 24-hour TTL for users, groups, plans, buckets
- **Task Cache**: No expiration (actively managed)
- **Cache Keys**: `annika:graph:{type}:{id}`

### Sync Services
- **Planner Sync V5**: Bidirectional sync with conflict resolution
- **Webhook-Driven**: Real-time updates via Graph webhooks
- **Polling Fallback**: 30-second polling for missed events

### Real-time Updates
- **Pub/Sub Channels**: Redis channels for real-time notifications
- **Webhook Processing**: Automatic cache updates on changes
- **Event Streaming**: Live event feeds for agents

---

## 16. Security & Permissions

### Authentication Methods
- **Application Permissions**: For background services
- **Delegated Permissions**: For user-context operations
- **Client Credentials Flow**: For autonomous operations

### Permission Scopes by Feature
```text
Mail Operations:
- Mail.Read, Mail.ReadWrite, Mail.Send

Calendar Operations:
- Calendars.Read, Calendars.ReadWrite

Planner Operations:
- Tasks.Read, Tasks.ReadWrite, Group.Read.All, Group.ReadWrite.All

Teams Operations:
- Chat.Read, Chat.ReadWrite, Chat.ReadBasic
- Chat.Create, Chat.ReadWrite.All (for app permissions)
- ChannelMessage.Read.All, ChannelMessage.UpdatePolicyViolation.All

User/Group Management:
- User.Read.All, Group.Read.All, Directory.Read.All
```

---

## 17. Performance Optimizations

### Batch Operations
- **Batch Requests**: Combine multiple operations
- **Parallel Processing**: Concurrent API calls
- **Connection Pooling**: Reuse HTTP connections

### Caching Strategies
- **Redis Caching**: Fast local cache with TTL
- **ETag Support**: Conditional requests for unchanged data
- **Selective Fields**: Use `$select` to minimize payload

### Rate Limit Management
- **Exponential Backoff**: Automatic retry with increasing delays
- **Request Queuing**: Queue requests during rate limits
- **Health Monitoring**: Track API health and performance

---

This comprehensive endpoint catalog provides everything needed for agents to interact with Microsoft Graph API effectively, with clear implementation status, caching strategies, and real-time capabilities. 