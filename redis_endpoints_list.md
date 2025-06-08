# New Redis Endpoints for Agent Monitoring

## Token Management System

### Token Storage Keys
- **Agent Tokens**: `annika:tokens:agent:{scope}`
  - Purpose: Store delegated access tokens for agent authentication
  - TTL: Based on token expiration (with 5-minute buffer)
  - Data: JSON with token, expires_on, scope, stored_at, refresh_count

- **User-Specific Tokens**: `annika:tokens:user:{user_id}:{scope}`
  - Purpose: Store user-specific delegated access tokens
  - TTL: Based on token expiration (with 5-minute buffer)
  - Data: JSON with token, expires_on, scope, user_id, stored_at, refresh_count

- **Active Token Tracking**: `annika:tokens:active`
  - Purpose: Set containing all active token keys for monitoring
  - Type: Redis SET
  - Data: List of active token key names

## Microsoft Graph Metadata Caching

### Graph Data Cache Keys
- **Users**: `annika:graph:users:{user_id}`
  - Purpose: Cache MS Graph user metadata
  - TTL: 24 hours (86400 seconds)
  - Data: JSON user object from MS Graph API

- **Groups**: `annika:graph:groups:{group_id}`
  - Purpose: Cache MS Graph group metadata
  - TTL: 24 hours (86400 seconds)
  - Data: JSON group object from MS Graph API

- **Plans**: `annika:graph:plans:{plan_id}`
  - Purpose: Cache MS Graph Planner plan metadata
  - TTL: 24 hours (86400 seconds)
  - Data: JSON plan object from MS Graph API

- **Tasks**: `annika:graph:tasks:{task_id}`
  - Purpose: Cache MS Graph Planner task metadata
  - TTL: Never expires (tasks are actively managed)
  - Data: JSON task object from MS Graph API

- **Buckets**: `annika:graph:buckets:{bucket_id}`
  - Purpose: Cache MS Graph Planner bucket metadata
  - TTL: 24 hours (86400 seconds)
  - Data: JSON bucket object from MS Graph API

## Planner Sync Service

### ID Mapping and ETags
- **ID Mapping**: `annika:planner:id_map:{annika_id}`
  - Purpose: Map Annika task IDs to MS Planner task IDs
  - TTL: Persistent
  - Data: JSON with annika_id, planner_id, mapping metadata

- **ETags**: `annika:planner:etag:{planner_id}`
  - Purpose: Store ETags for optimistic concurrency control
  - TTL: Persistent
  - Data: String ETag value

- **Cached Tasks**: `annika:planner:tasks:{task_id}`
  - Purpose: Cache Planner task data for sync operations
  - TTL: 1 hour (3600 seconds)
  - Data: JSON task object from Planner API

### Sync Monitoring
- **Sync Log**: `annika:sync:log`
  - Purpose: Log of sync operations for debugging
  - Type: Redis LIST
  - Data: JSON log entries with timestamps and operation details

- **Pending Operations**: `annika:sync:pending`
  - Purpose: Queue of pending sync operations
  - Type: Redis LIST
  - Data: JSON operation objects

- **Failed Operations**: `annika:sync:failed`
  - Purpose: Queue of failed sync operations for retry
  - Type: Redis LIST
  - Data: JSON operation objects with error details

- **Webhook Status**: `annika:sync:webhook_status`
  - Purpose: Track webhook processing status
  - TTL: Persistent
  - Data: JSON status object

- **Last Upload Timestamp**: `annika:sync:last_upload:{annika_id}`
  - Purpose: Track last successful upload time for each task
  - TTL: Persistent
  - Data: Unix timestamp

- **Sync Health**: `annika:sync:health`
  - Purpose: Overall sync service health status
  - TTL: 5 minutes (300 seconds)
  - Data: JSON health metrics

## Webhook System

### Webhook Logging and Notifications
- **Webhook Log**: `annika:webhook:log`
  - Purpose: Log of all webhook events for debugging
  - Type: Redis LIST (trimmed to 500 entries)
  - Data: JSON webhook event objects

- **Webhook Notifications**: `annika:webhooks:notifications`
  - Purpose: Store recent webhook notifications
  - TTL: 1 hour (3600 seconds)
  - Data: JSON notification objects

## Microsoft Teams Integration

### Teams Message History
- **Chat Messages History**: `annika:teams:chat_messages:history`
  - Purpose: Store recent Teams chat messages
  - Type: Redis LIST (trimmed to 100 entries)
  - Data: JSON message objects

- **Channel Messages History**: `annika:teams:channel_messages:history`
  - Purpose: Store recent Teams channel messages
  - Type: Redis LIST (trimmed to 100 entries)
  - Data: JSON message objects

- **Chats History**: `annika:teams:chats:history`
  - Purpose: Store recent Teams chat events
  - Type: Redis LIST (trimmed to 50 entries)
  - Data: JSON chat event objects

- **Channels History**: `annika:teams:channels:history`
  - Purpose: Store recent Teams channel events
  - Type: Redis LIST (trimmed to 50 entries)
  - Data: JSON channel event objects

### Chat Subscription Management
- **Chat Subscriptions**: `annika:chat_subscriptions:{subscription_id}`
  - Purpose: Manage Teams chat webhook subscriptions
  - TTL: Based on subscription expiration
  - Data: JSON subscription metadata

## Pub/Sub Channels for Real-time Monitoring

### Webhook Channels
- **Planner Webhooks**: `annika:planner:webhook`
  - Purpose: Real-time Planner webhook notifications
  - Type: Pub/Sub channel
  - Data: JSON webhook payloads

### Teams Channels
- **Teams Chat Messages**: `annika:teams:chat_messages`
  - Purpose: Real-time Teams chat message notifications
  - Type: Pub/Sub channel
  - Data: JSON message objects

- **Teams Channel Messages**: `annika:teams:channel_messages`
  - Purpose: Real-time Teams channel message notifications
  - Type: Pub/Sub channel
  - Data: JSON message objects

- **Teams Chats**: `annika:teams:chats`
  - Purpose: Real-time Teams chat event notifications
  - Type: Pub/Sub channel
  - Data: JSON chat event objects

- **Teams Channels**: `annika:teams:channels`
  - Purpose: Real-time Teams channel event notifications
  - Type: Pub/Sub channel
  - Data: JSON channel event objects

### Task Management Channels
- **Task Updates**: `annika:tasks:updates`
  - Purpose: Real-time task update notifications
  - Type: Pub/Sub channel
  - Data: JSON task update objects

- **Metadata Updates**: `annika:pubsub:metadata`
  - Purpose: Real-time metadata update notifications
  - Type: Pub/Sub channel
  - Data: JSON metadata update objects

- **Task Events**: `annika:pubsub:tasks`
  - Purpose: Real-time task event notifications
  - Type: Pub/Sub channel
  - Data: JSON task event objects

## Configuration Storage

### System Configuration
- **Default Plan ID**: `annika:config:default_plan_id`
  - Purpose: Store default Planner plan ID for task creation
  - TTL: Persistent
  - Data: String plan ID

## Task Storage

### Individual Tasks
- **Task Data**: `annika:tasks:{task_id}`
  - Purpose: Store individual task data for agent access
  - TTL: Persistent
  - Data: JSON task object with full task details

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