# Comprehensive Microsoft Graph Endpoints

This document provides a complete, intelligently organized catalog of Microsoft Graph API endpoints used in the MCP Functions project, organized by functional areas and implementation status.

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
| Endpoint | Status | Purpose | Implementation |
|----------|--------|---------|----------------|
| `/me` | ✅ | Get current user profile | Used for token validation |
| `/organization` | ✅ | Get tenant information | Organization details |

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
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/users` | ✅ | List all users | GET | `list_users_http()` |
| `/users/{user-id}` | ✅📊 | Get specific user | GET | `get_user_http()` + Redis cache |
| `/users/{user-id}/memberOf` | 🔄 | Get user's group memberships | GET | Sync service polling |
| `/directory/deletedItems/microsoft.graph.user` | ✅ | List deleted users | GET | `list_deleted_users_http()` |

### User Profile Extensions
```text
/users/{id}?$select=id,displayName,mail,userPrincipalName,jobTitle,department
```

---

## 3. Group & Team Management

### Group Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/groups` | ✅🔗 | List all groups | GET | `list_groups_http()` + webhooks |
| `/groups/{group-id}` | 📊 | Get specific group | GET | Redis metadata cache |
| `/groups/{group-id}/members` | ✅ | List group members | GET | `list_group_members_http()` |
| `/groups/{group-id}/members/$ref` | ✅ | Add user to group | POST | `add_user_to_group_http()` |

### Group Filtering
```text
/groups?$filter=groupTypes/any(c:c eq 'Unified')&$select=id,displayName,description,mail
```

---

## 4. Microsoft Planner (Task Management)

### Plan Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/planner/plans` | 🔄 | List user's plans | GET | Sync service polling |
| `/groups/{group-id}/planner/plans` | ✅📊 | List group plans | GET | `list_plans_http()` + cache |
| `/planner/plans` | ✅ | Create new plan | POST | `create_plan_http()` |
| `/planner/plans/{plan-id}` | ✅📊 | Get/Update/Delete plan | GET/PATCH/DELETE | Full CRUD operations |
| `/planner/plans/{plan-id}/details` | ✅ | Get plan details | GET | `get_plan_details_http()` |

### Task Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/planner/tasks` | ✅🔄 | Create task | POST | `create_task_http()` + sync |
| `/planner/tasks/{task-id}` | ✅🔄📊 | Get/Update/Delete task | GET/PATCH/DELETE | Full CRUD + sync + cache |
| `/planner/tasks/{task-id}/details` | ✅📊 | Get/Update task details | GET/PATCH | Detailed task info |
| `/planner/plans/{plan-id}/tasks` | 🔄 | List plan tasks | GET | Sync service polling |
| `/me/planner/tasks` | ✅ | List user's tasks | GET | `list_my_tasks_http()` |
| `/users/{user-id}/planner/tasks` | ✅ | List user tasks | GET | `list_user_tasks_http()` |

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
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/messages` | ✅ | List inbox messages | GET | `list_inbox_messages_http()` |
| `/me/messages/{message-id}` | ✅ | Get specific message | GET | `get_message_http()` |
| `/me/sendMail` | ✅ | Send email | POST | `send_email_http()` |
| `/me/messages/{message-id}/send` | ✅ | Send draft message | POST | `send_draft_message_http()` |

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
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/calendars` | ✅ | List/Create calendars | GET/POST | `list_calendars_http()` |
| `/me/calendar/calendarView` | ✅ | Get calendar view | GET | `get_calendar_view_http()` |
| `/me/findMeetingTimes` | ✅ | Find meeting times | POST | `find_meeting_times_http()` |

### Event Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/events` | ✅ | List/Create events | GET/POST | `create_event_http()` |
| `/me/events/{event-id}` | ✅ | Get/Update/Delete event | GET/PATCH/DELETE | Full CRUD operations |
| `/me/events/{event-id}/accept` | ✅ | Accept event | POST | `accept_event_http()` |
| `/me/events/{event-id}/decline` | ✅ | Decline event | POST | `decline_event_http()` |

---

## 7. Microsoft Teams Integration

### Teams & Channels
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/teams` | ✅ | List teams | GET | `list_teams_http()` |
| `/teams/{team-id}/channels` | ✅ | List team channels | GET | `list_team_channels_http()` |
| `/teams/{team-id}/channels/{channel-id}/messages` | ✅ | Send channel message | POST | `send_channel_message_http()` |
| `/teams/getAllChannels` | 🔗 | All channels (webhook) | GET | Webhook subscription |

### Chats & Messages
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/chats` | ✅ | List user chats | GET | `list_chats_http()` |
| `/chats/{chat-id}/messages` | ✅🔗 | List/Send chat messages | GET/POST | `post_chat_message_http()` + webhooks |
| `/chats/{chat-id}/messages/{message-id}/replies` | ✅ | Reply to chat message | POST | `post_chat_message_http()` (with replyToId) |
| `/me/chats/{chat-id}/messages` | ✅ | List chat messages for user | GET | Direct Graph API access |
| `/me/chats/{chat-id}/members` | ✅ | List chat members | GET | Chat discovery functionality |
| `/me/chats/getAllMessages` | 🔗 | All chat messages (webhook) | GET | Webhook subscription |
| `/chats/getAllMessages` | 🔗 | All tenant chat messages (webhook) | GET | Webhook subscription (app permissions) |

---

## 8. Teams Chat Management (Enhanced)

### Chat Discovery & Management
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/chats` | ✅ | List user's chats | GET | `list_chats_http()` |
| `/me/chats/{chat-id}/members` | ✅ | List chat members | GET | Chat discovery service |
| `/chats/{chat-id}` | 📋 | Get specific chat details | GET | Available but not implemented |

### Chat Message Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/chats/{chat-id}/messages` | ✅🔗 | Send message to chat | POST | `post_chat_message_http()` |
| `/chats/{chat-id}/messages/{message-id}/replies` | ✅ | Reply to specific message | POST | `post_chat_message_http()` (with replyToId) |
| `/me/chats/{chat-id}/messages` | ✅ | List messages in user's chat | GET | Direct API access |

### Chat Webhook Subscriptions
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/me/chats/getAllMessages` | 🔗 | Subscribe to user's chat messages | POST | `create_teams_chat_message_subscriptions()` |
| `/chats/getAllMessages` | 🔗 | Subscribe to all tenant chat messages | POST | Requires app permissions |
| `/chats/{chat-id}/messages` | 🔗 | Subscribe to specific chat | POST | Individual chat subscriptions |

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

## 9. Files & SharePoint

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

## 10. Webhook Subscriptions

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

## 11. Reports & Analytics

### Usage Reports
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/reports/{report-name}` | ✅ | Get usage reports | GET | `get_reports_http()` |

---

## 12. Security & Compliance

### Security Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/security/alerts` | ✅ | List security alerts | GET | `list_security_alerts_http()` |

---

## 13. Device Management

### Intune Operations
| Endpoint | Status | Purpose | HTTP Method | Implementation |
|----------|--------|---------|-------------|----------------|
| `/deviceManagement/managedDevices` | ✅ | List managed devices | GET | `list_managed_devices_http()` |

---

## 14. Specialized Query Parameters

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

## 15. Error Handling & Rate Limits

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

## 16. Implementation Architecture

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

## 17. Security & Permissions

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

## 18. Performance Optimizations

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