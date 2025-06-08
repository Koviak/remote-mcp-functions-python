# New Redis Endpoints for Agent Monitoring

## Token Management System

### Token Storage Keys
- **Agent Tokens**: `annika:tokens:agent:{scope}`
  - Purpose: Store delegated access tokens for agent authentication
  - TTL: Based on token expiration (with 5-minute buffer)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6...",
      "expires_on": 1704067200,
      "scope": "https://graph.microsoft.com/.default",
      "stored_at": 1704063600,
      "refresh_count": 0,
      "metadata": {
        "acquired_by": "agent_auth_manager",
        "client_id": "your-client-id"
      }
    }
    ```

- **User-Specific Tokens**: `annika:tokens:user:{user_id}:{scope}`
  - Purpose: Store user-specific delegated access tokens
  - TTL: Based on token expiration (with 5-minute buffer)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6...",
      "expires_on": 1704067200,
      "scope": "User.Read Mail.Send",
      "user_id": "user123",
      "stored_at": 1704063600,
      "refresh_count": 2,
      "last_refreshed": 1704065400,
      "metadata": {
        "acquired_by": "agent_auth_manager"
      }
    }
    ```

- **Active Token Tracking**: `annika:tokens:active`
  - Purpose: Set containing all active token keys for monitoring
  - Redis Type: SET
  - Data Format: Set members are key names like:
    ```
    annika:tokens:agent:https://graph.microsoft.com/.default
    annika:tokens:user:user123:User.Read Mail.Send
    ```

## Microsoft Graph Metadata Caching

### Graph Data Cache Keys
- **Users**: `annika:graph:users:{user_id}`
  - Purpose: Cache MS Graph user metadata
  - TTL: 24 hours (86400 seconds)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "id": "user-id-123",
      "displayName": "John Doe",
      "mail": "john.doe@company.com",
      "userPrincipalName": "john.doe@company.com",
      "jobTitle": "Software Engineer",
      "department": "Engineering"
    }
    ```

- **Groups**: `annika:graph:groups:{group_id}`
  - Purpose: Cache MS Graph group metadata
  - TTL: 24 hours (86400 seconds)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "id": "group-id-456",
      "displayName": "Engineering Team",
      "description": "Main engineering team",
      "mail": "engineering@company.com",
      "groupTypes": ["Unified"],
      "plans": [
        {
          "id": "plan-id-789",
          "title": "Sprint Planning"
        }
      ]
    }
    ```

- **Plans**: `annika:graph:plans:{plan_id}`
  - Purpose: Cache MS Graph Planner plan metadata
  - TTL: 24 hours (86400 seconds)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "id": "plan-id-789",
      "title": "Sprint Planning",
      "owner": "group-id-456",
      "createdDateTime": "2024-01-01T00:00:00Z",
      "buckets": [
        {
          "id": "bucket-id-101",
          "name": "To Do",
          "planId": "plan-id-789"
        }
      ]
    }
    ```

- **Tasks**: `annika:graph:tasks:{task_id}`
  - Purpose: Cache MS Graph Planner task metadata
  - TTL: Never expires (tasks are actively managed)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "id": "task-id-202",
      "title": "Implement feature X",
      "bucketId": "bucket-id-101",
      "planId": "plan-id-789",
      "percentComplete": 50,
      "priority": 5,
      "startDateTime": "2024-01-01T00:00:00Z",
      "dueDateTime": "2024-01-15T00:00:00Z",
      "assignments": {
        "user-id-123": {
          "assignedBy": {
            "user": {
              "id": "user-id-456"
            }
          }
        }
      },
      "details": {
        "description": "Detailed task description",
        "checklist": {
          "item1": {
            "title": "Subtask 1",
            "isChecked": false
          }
        }
      }
    }
    ```

- **Buckets**: `annika:graph:buckets:{bucket_id}`
  - Purpose: Cache MS Graph Planner bucket metadata
  - TTL: 24 hours (86400 seconds)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "id": "bucket-id-101",
      "name": "To Do",
      "planId": "plan-id-789",
      "orderHint": "8585269235419181677"
    }
    ```

## Planner Sync Service

### ID Mapping and ETags
- **ID Mapping**: `annika:planner:id_map:{annika_id}`
  - Purpose: Map Annika task IDs to MS Planner task IDs
  - TTL: Persistent
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "annika_id": "Task-CVd123-1-1",
      "planner_id": "planner-task-456",
      "created_at": "2024-01-01T00:00:00Z",
      "last_synced": "2024-01-01T12:00:00Z"
    }
    ```

- **ETags**: `annika:planner:etag:{planner_id}`
  - Purpose: Store ETags for optimistic concurrency control
  - TTL: Persistent
  - Redis Type: STRING
  - Data Format: Raw ETag string like `"W/\"JzEtVGFzayAgQEBAQEBAQEBAQEBAQEBAWCc=\""`

- **Cached Tasks**: `annika:planner:tasks:{task_id}`
  - Purpose: Cache Planner task data for sync operations
  - TTL: 1 hour (3600 seconds)
  - Redis Type: STRING (JSON)
  - Data Format: Full MS Graph Planner task object (same as `annika:graph:tasks:{task_id}`)

### Sync Monitoring
- **Sync Log**: `annika:sync:log`
  - Purpose: Log of sync operations for debugging
  - Redis Type: LIST
  - Data Format: JSON log entries (LPUSH/LTRIM to 500 entries)
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "operation": "create",
    "annika_id": "Task-CVd123-1-1",
    "planner_id": "planner-task-456",
    "status": "success",
    "error": null,
    "conflict_resolution": null
  }
  ```

- **Pending Operations**: `annika:sync:pending`
  - Purpose: Queue of pending sync operations
  - Redis Type: LIST
  - Data Format: JSON operation objects
  ```json
  {
    "operation_type": "upload",
    "task_id": "Task-CVd123-1-1",
    "queued_at": "2024-01-01T12:00:00Z",
    "retry_count": 0
  }
  ```

- **Failed Operations**: `annika:sync:failed`
  - Purpose: Queue of failed sync operations for retry
  - Redis Type: LIST
  - Data Format: JSON operation objects with error details
  ```json
  {
    "operation_type": "upload",
    "task_id": "Task-CVd123-1-1",
    "failed_at": "2024-01-01T12:00:00Z",
    "error": "Rate limit exceeded",
    "retry_count": 3,
    "next_retry": "2024-01-01T12:05:00Z"
  }
  ```

- **Webhook Status**: `annika:sync:webhook_status`
  - Purpose: Track webhook processing status
  - TTL: Persistent
  - Redis Type: HASH
  - Data Format: Hash with webhook types as fields
  ```
  HGETALL annika:sync:webhook_status
  groups -> {"subscription_id": "sub-123", "created_at": "2024-01-01T00:00:00Z", "expires_at": "2024-01-02T00:00:00Z", "resource": "/groups"}
  teams_chats -> {"subscription_id": "sub-456", "created_at": "2024-01-01T00:00:00Z", "expires_at": "2024-01-02T00:00:00Z", "resource": "/chats"}
  ```

- **Last Upload Timestamp**: `annika:sync:last_upload:{annika_id}`
  - Purpose: Track last successful upload time for each task
  - TTL: Persistent
  - Redis Type: STRING
  - Data Format: Unix timestamp as string like `"1704067200"`

- **Sync Health**: `annika:sync:health`
  - Purpose: Overall sync service health status
  - TTL: 5 minutes (300 seconds)
  - Redis Type: STRING (JSON)
  - Data Format:
    ```json
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "status": "healthy",
      "pending_operations": 5,
      "failed_operations": 0,
      "last_successful_sync": "2024-01-01T11:55:00Z",
      "webhook_subscriptions": {
        "groups": "active",
        "teams_chats": "active"
      }
    }
    ```

## Webhook System

### Webhook Logging and Notifications
- **Webhook Log**: `annika:webhook:log`
  - Purpose: Log of all webhook events for debugging
  - Redis Type: LIST (LPUSH/LTRIM to 500 entries)
  - Data Format: JSON webhook event objects
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "change_type": "created",
    "resource": "/groups/group-id-123",
    "resource_id": "group-id-123",
    "client_state": "annika_groups_webhook_v5",
    "subscription_id": "sub-456",
    "lifecycle_event": null
  }
  ```

- **Webhook Notifications**: `annika:webhooks:notifications`
  - Purpose: Store recent webhook notifications
  - TTL: 1 hour (3600 seconds)
  - Redis Type: LIST
  - Data Format: Same as webhook log entries

## Microsoft Teams Integration

### Teams Message History
- **Chat Messages History**: `annika:teams:chat_messages:history`
  - Purpose: Store recent Teams chat messages
  - Redis Type: LIST (LPUSH/LTRIM to 100 entries)
  - Data Format: JSON message notification objects
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "type": "teams_chat_message",
    "change_type": "created",
    "chat_id": "chat-id-123",
    "message_id": "message-id-456",
    "client_state": "chat_global",
    "resource": "/chats/chat-id-123/messages/message-id-456",
    "notification_id": "sub-789",
    "raw_notification": { /* full webhook payload */ }
  }
  ```

- **Channel Messages History**: `annika:teams:channel_messages:history`
  - Purpose: Store recent Teams channel messages
  - Redis Type: LIST (LPUSH/LTRIM to 100 entries)
  - Data Format: JSON message notification objects
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "type": "teams_channel_message",
    "change_type": "created",
    "team_id": "team-id-123",
    "channel_id": "channel-id-456",
    "message_id": "message-id-789",
    "client_state": "annika_teams_channels_v5",
    "resource": "/teams/team-id-123/channels/channel-id-456/messages/message-id-789",
    "notification_id": "sub-101",
    "raw_notification": { /* full webhook payload */ }
  }
  ```

- **Chats History**: `annika:teams:chats:history`
  - Purpose: Store recent Teams chat events
  - Redis Type: LIST (LPUSH/LTRIM to 50 entries)
  - Data Format: JSON chat event objects
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "type": "teams_chat",
    "change_type": "created",
    "chat_id": "chat-id-123",
    "client_state": "annika_teams_chats_v5",
    "notification_id": "sub-456",
    "raw_notification": { /* full webhook payload */ }
  }
  ```

- **Channels History**: `annika:teams:channels:history`
  - Purpose: Store recent Teams channel events
  - Redis Type: LIST (LPUSH/LTRIM to 50 entries)
  - Data Format: JSON channel event objects
  ```json
  {
    "timestamp": "2024-01-01T12:00:00.000Z",
    "type": "teams_channel",
    "change_type": "created",
    "channel_id": "channel-id-456",
    "client_state": "annika_teams_channels_v5",
    "notification_id": "sub-789",
    "raw_notification": { /* full webhook payload */ }
  }
  ```

### Chat Subscription Management
- **Chat Subscriptions**: `annika:chat_subscriptions:{subscription_id}`
  - Purpose: Manage Teams chat webhook subscriptions
  - TTL: Based on subscription expiration
  - Redis Type: HASH
  - Data Format: Hash fields with subscription metadata
  ```
  HGETALL annika:chat_subscriptions:global
  subscription_id -> "sub-123-456-789"
  created_at -> "2024-01-01T00:00:00Z"
  expires_at -> "2024-01-01T01:00:00Z"
  status -> "active"
  ```

## Pub/Sub Channels for Real-time Monitoring

### Webhook Channels
- **Planner Webhooks**: `annika:planner:webhook`
  - Purpose: Real-time Planner webhook notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Raw MS Graph webhook notification JSON
  ```json
  {
    "changeType": "created",
    "clientState": "annika_planner_sync_v5",
    "resource": "/groups/group-id-123",
    "resourceData": {
      "id": "group-id-123",
      "@odata.type": "#Microsoft.Graph.Group"
    },
    "subscriptionId": "sub-456",
    "subscriptionExpirationDateTime": "2024-01-02T00:00:00Z"
  }
  ```

### Teams Channels
- **Teams Chat Messages**: `annika:teams:chat_messages`
  - Purpose: Real-time Teams chat message notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Processed message notification objects (same as history format)

- **Teams Channel Messages**: `annika:teams:channel_messages`
  - Purpose: Real-time Teams channel message notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Processed message notification objects (same as history format)

- **Teams Chats**: `annika:teams:chats`
  - Purpose: Real-time Teams chat event notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Processed chat event objects (same as history format)

- **Teams Channels**: `annika:teams:channels`
  - Purpose: Real-time Teams channel event notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Processed channel event objects (same as history format)

### Task Management Channels
- **Task Updates**: `annika:tasks:updates`
  - Purpose: Real-time task update notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Task update event objects
  ```json
  {
    "action": "task_synced",
    "task": { /* full task object */ },
    "source": "webhook",
    "timestamp": "2024-01-01T12:00:00Z"
  }
  ```

- **Metadata Updates**: `annika:pubsub:metadata`
  - Purpose: Real-time metadata update notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Metadata update event objects
  ```json
  {
    "type": "user_updated",
    "id": "user-id-123",
    "data": { /* updated user object */ },
    "timestamp": "2024-01-01T12:00:00Z"
  }
  ```

- **Task Events**: `annika:pubsub:tasks`
  - Purpose: Real-time task event notifications
  - Redis Type: Pub/Sub Channel
  - Data Format: Task event objects
  ```json
  {
    "type": "task_cached",
    "id": "task-id-456",
    "data": { /* full task object */ },
    "timestamp": "2024-01-01T12:00:00Z"
  }
  ```

## Configuration Storage

### System Configuration
- **Default Plan ID**: `annika:config:default_plan_id`
  - Purpose: Store default Planner plan ID for task creation
  - TTL: Persistent
  - Redis Type: STRING
  - Data Format: Plain plan ID string like `"plan-id-789"`

## Task Storage

### Individual Tasks
- **Task Data**: `annika:tasks:{task_id}`
  - Purpose: Store individual task data for agent access
  - TTL: Persistent
  - Redis Type: STRING (JSON)
  - Data Format: Full Annika task object
  ```json
  {
    "id": "Task-CVd123-1-1",
    "title": "Implement feature X",
    "description": "Detailed task description",
    "status": "in_progress",
    "priority": "high",
    "percent_complete": 0.5,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "due_date": "2024-01-15T00:00:00Z",
    "assigned_to": "Annika",
    "conversation_id": "CVd123",
    "source": "conscious_state_analysis",
    "checklist_items": [],
    "dependencies": [],
    "labels": []
  }
  ```

## API Endpoints for External Access

### HTTP Endpoints (for external applications)
- **GET /api/tokens/{scope}** - Retrieve token for specific scope
- **GET /api/tokens** - List all active tokens (metadata only)
- **GET /api/tokens/health** - Health check for token service
- **POST /api/tokens/refresh/{scope}** - Manually refresh token
- **GET /api/metadata** - Retrieve cached Graph metadata

## Monitoring Recommendations

### Key Metrics to Monitor
1. **Token Health**: Monitor `annika:tokens:active` set size
2. **Sync Performance**: Monitor `annika:sync:log` for operation times
3. **Webhook Processing**: Monitor `annika:webhook:log` for processing delays
4. **Cache Hit Rates**: Monitor Graph metadata cache usage
5. **Pub/Sub Activity**: Monitor channel message rates
6. **Failed Operations**: Monitor `annika:sync:failed` queue size

### Health Check Keys
- `annika:sync:health` - Overall sync service health
- Token service health via `/api/tokens/health` endpoint
- Redis connection health via ping operations

### Performance Metrics
- Memory usage of cached data
- TTL monitoring for expiring tokens
- Queue depths for pending/failed operations
- Pub/Sub channel subscription counts 