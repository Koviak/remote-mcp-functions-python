# Planner Agent Task Creation Guide

## How Agents Create Tasks with Redis-First Architecture

This guide explains how your Planner Agent creates tasks using our optimized Redis-first architecture, where agents work at microsecond speeds while background services handle Microsoft Planner synchronization.

### 🚀 Quick Reference
- **Create Tasks**: Direct Redis or HTTP API (see Methods 1 & 2)
- **Access Cached Data**: `GET /api/metadata?type={user|group|plan|task}&id={id}` (see Accessing Cached Data)
- **Cache Benefits**: 2000-4000x faster, no API limits, works offline
- **Task Storage**: Tasks never expire, other data cached for 24 hours

## 🚀 Why Redis-First Architecture?

### Traditional (Slow) Approach:
```
Agent → MS Graph API (200-500ms) → Planner → Other Agents
```

### Our Optimized Approach:
```
Agent → Redis (0.1ms) → Other Agents (instant)
         ↓
      Sync Service → Planner (background)
```

**Benefits:**
- **2000-5000x faster** agent operations
- **No API rate limits** for agents
- **Instant task delegation** between agents
- **Works offline** - continues even if Planner is down
- **Event-driven uploads** - changes sync immediately to Planner

## 🎯 Overview

Agents have two ways to create tasks in Redis:

1. **Direct Redis Access** (Recommended for agents) - Microsecond operations
2. **HTTP API Endpoint** - For external systems or testing

Both methods write to Redis, triggering immediate background sync to Planner.

## 🔴 Method 1: Direct Redis Access (Recommended for Agents)

For maximum speed (0.1ms operations), agents should write tasks directly to Redis.

### Redis Storage Pattern
```
annika:tasks:{id}  # Primary task storage
```

### Task Format
```python
import redis
import json
from datetime import datetime

# Connect to Redis
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    password='password',
    decode_responses=True
)

# Create task object
task = {
    "id": f"agent-task-{datetime.utcnow().timestamp()}",
    "title": "Complete Project Documentation",
    "planId": "CbfN3rLYAkS0ZutzQP5J9mUAFxxt",
    "bucketId": "BUCKET_ID_HERE",  # Optional
    "assignedTo": ["5ac3e02f-825f-49f1-a2e2-8fe619020b60"],
    "dueDate": "2025-06-20",
    "percentComplete": 0,
    "createdBy": "agent",
    "createdAt": datetime.utcnow().isoformat()
}

# Store task in Redis (no expiry - tasks persist until completed/deleted)
redis_client.set(
    f"annika:tasks:{task['id']}",
    json.dumps(task)
)

# Publish notification (optional but recommended)
redis_client.publish(
    "annika:tasks:updates",
    json.dumps({
        "action": "created",
        "task": task,
        "source": "agent"
    })
)
```

## 📋 Method 2: HTTP API Endpoint (For External Systems)

Use this method when calling from external systems or for testing.

### Endpoint
```
POST http://localhost:7071/api/agent/tasks
```

### Required Fields
- `title` (string) - The task title
- `planId` (string) - The Microsoft Planner plan ID

### Optional Fields
- `bucketId` (string) - Specific bucket in the plan
- `assignedTo` (array) - Array of user IDs to assign
- `dueDate` (string) - Due date in ISO format (YYYY-MM-DD)
- `percentComplete` (number) - Progress percentage (0-100)

### Example Request

```python
import requests
import json

# Create a new task
task_data = {
    "title": "Review Q4 Marketing Strategy",
    "planId": "CbfN3rLYAkS0ZutzQP5J9mUAFxxt",  # Your plan ID
    "bucketId": "BUCKET_ID_HERE",  # Optional
    "assignedTo": ["5ac3e02f-825f-49f1-a2e2-8fe619020b60"],  # Annika's ID
    "dueDate": "2025-06-15",
    "percentComplete": 0
}

response = requests.post(
    "http://localhost:7071/api/agent/tasks",
    json=task_data,
    headers={"Content-Type": "application/json"},
    timeout=10
)

if response.status_code == 201:
    result = response.json()
    print(f"Task queued: {result['task']['id']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

## 📊 How Syncing Works (Enhanced Architecture)

### Agent Creates/Updates Task:
1. **Agent writes to Redis** (0.1ms) - Task stored in `annika:tasks:{id}`
2. **Pub/sub notification** (instant) - Message sent on `annika:tasks:updates`
3. **Other agents see immediately** - Can read and react to the task
4. **Sync service uploads** (background) - Task uploaded to Planner within seconds
5. **Confirmation published** - Success notification on `annika:tasks:sync`

### Human Creates Task in Planner:
1. **Polling service checks** (every 30 seconds)
2. **Downloads to Redis** - Stored as `annika:tasks:{id}`
3. **Agents notified** - Pub/sub message on `annika:tasks:updates`
4. **Agents can work on task** - Full speed Redis operations

**Key Difference**: Agent operations are never blocked waiting for Planner API!

## 🔍 Finding Plan and Bucket IDs

### List Available Plans
```python
# Get all plans the agent has access to
response = requests.get("http://localhost:7071/api/plans")
plans = response.json()["value"]

for plan in plans:
    print(f"Plan: {plan['title']} - ID: {plan['id']}")
```

### List Buckets in a Plan
```python
plan_id = "YOUR_PLAN_ID"
response = requests.get(f"http://localhost:7071/api/plans/{plan_id}/buckets")
buckets = response.json()["value"]

for bucket in buckets:
    print(f"Bucket: {bucket['name']} - ID: {bucket['id']}")
```

## 🚀 Accessing Cached Data (Super Fast!)

Our Redis caching layer provides microsecond-speed access to Microsoft Graph data. Here's how agents can access cached information:

### Cache-First API Endpoint
```
GET http://localhost:7071/api/metadata?type={resource_type}&id={resource_id}
```

Resource types: `user`, `group`, `plan`, `task`

### Examples

#### Get Cached User Details (0.1ms vs 200-500ms)
```python
# Get user information from cache
user_id = "5ac3e02f-825f-49f1-a2e2-8fe619020b60"
response = requests.get(
    f"http://localhost:7071/api/metadata?type=user&id={user_id}"
)
user_data = response.json()
print(f"User: {user_data['displayName']} - {user_data['mail']}")
```

#### Get Cached Group with Plans (0.1ms vs 300-600ms)
```python
# Get group and its associated plans from cache
group_id = "795b880a-be88-45f9-9a11-d1777169ffb8"
response = requests.get(
    f"http://localhost:7071/api/metadata?type=group&id={group_id}"
)
group_data = response.json()
print(f"Group: {group_data['displayName']}")
for plan in group_data.get('plans', []):
    print(f"  - Plan: {plan['title']} ({plan['id']})")
```

#### Get Cached Plan with Buckets (0.1ms vs 400-800ms)
```python
# Get plan details including buckets from cache
plan_id = "CbfN3rLYAkS0ZutzQP5J9mUAFxxt"
response = requests.get(
    f"http://localhost:7071/api/metadata?type=plan&id={plan_id}"
)
plan_data = response.json()
print(f"Plan: {plan_data['title']}")
for bucket in plan_data.get('buckets', []):
    print(f"  - Bucket: {bucket['name']} ({bucket['id']})")
```

#### Get Cached Task Details (0.1ms vs 200-400ms)
```python
# Get task information from cache
task_id = "AAMkAGI5MWY5Ym..."
response = requests.get(
    f"http://localhost:7071/api/metadata?type=task&id={task_id}"
)
task_data = response.json()
print(f"Task: {task_data['title']} - {task_data['percentComplete']}% complete")
```

### Direct Redis Access for Maximum Speed

For agents that need absolute maximum performance, access Redis directly:

```python
import redis
import json

redis_client = redis.Redis(
    host='localhost',
    port=6379,
    password='password',
    decode_responses=True
)

# Direct cache access patterns
user_data = redis_client.get("annika:graph:users:{user_id}")
group_data = redis_client.get("annika:graph:groups:{group_id}")
plan_data = redis_client.get("annika:graph:plans:{plan_id}")
task_data = redis_client.get("annika:graph:tasks:{task_id}")

# Parse JSON if data exists
if user_data:
    user = json.loads(user_data)
    print(f"Cached user: {user['displayName']}")
```

### Cache Benefits
- **2000-4000x faster** than MS Graph API calls
- **No rate limits** - Redis handles millions of requests/second
- **Always available** - Works even if MS Graph is down
- **Auto-updated** - Webhooks keep cache fresh
- **24-hour TTL** - Data stays fresh for a full day

### When to Use Cache vs Direct API

**Use Cache When:**
- Looking up user names, emails, or departments
- Getting group memberships or plan lists
- Retrieving task details or bucket information
- Need instant response times (<1ms)

**Force API Refresh When:**
- Need absolute latest data
- Cache returns 404 (data not yet cached)
- Explicitly need to refresh stale data

To force a refresh, just call the regular endpoint (e.g., `GET /api/users/{id}`) which will update the cache.

## 📡 Subscribing to Task Updates

Your agent can subscribe to Redis pub/sub channels to receive real-time updates:

```python
import redis

# Subscribe to task updates
pubsub = redis_client.pubsub()
pubsub.subscribe("annika:tasks:updates")

# Listen for messages
for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        action = data['action']  # created, updated, deleted
        
        if action == 'created':
            print(f"New task: {data['task']['title']}")
        elif action == 'updated':
            print(f"Task updated: {data['task']['title']}")
        elif action == 'deleted':
            print(f"Task deleted: {data['taskId']}")
```

## 🚨 Important Architecture Benefits

1. **Speed**: Agents operate at Redis speed (0.1ms) vs API speed (200-500ms)
2. **No Rate Limits**: Agents never hit MS Graph API limits
3. **Instant Sync**: Task changes upload immediately (event-driven)
4. **Works Offline**: Agents continue working even if Planner is down
5. **Real-time Coordination**: Agents see each other's changes instantly
6. **Comprehensive Caching**: User, group, plan, and task data cached for 24 hours
7. **Task Persistence**: Tasks never expire - they persist until completed/deleted

## 📝 Important Notes

1. **Plan ID Required**: You must specify a valid plan ID that Annika has access to
2. **Permissions**: The agent user (Annika) must have permissions in the specified plan
3. **Human Tasks**: Tasks created by humans in Planner appear in Redis within 30 seconds
4. **Error Handling**: The sync service handles retries automatically
5. **Task IDs**: Use Redis IDs for agent operations, Planner IDs are handled by sync service
6. **Cache TTL**: User/group/plan data cached for 24 hours, tasks never expire
7. **Cache Warming**: First access may be slower if not cached, subsequent calls are instant

## 🧪 Testing Your Integration

1. **Create a test task**:
```bash
curl -X POST http://localhost:7071/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Task from Agent",
    "planId": "YOUR_PLAN_ID"
  }'
```

2. **Check Redis tasks**:
```bash
redis-cli -a password
KEYS annika:tasks:*
```

3. **Monitor updates**:
```bash
redis-cli -a password
SUBSCRIBE annika:tasks:updates
```

4. **Verify in Planner**: Check Microsoft Planner to see if the task appears

## 🔧 Troubleshooting

### Task not appearing in Planner?
1. Check Function App logs for errors
2. Verify the plan ID is correct
3. Ensure Annika has access to the plan
4. Check Redis connection

### Getting 400 Bad Request?
- Ensure `title` and `planId` are provided
- Verify JSON format is correct
- Check field names are exactly as specified

### Getting 503 Service Unavailable?
- Ensure Function App is running: `func start`
- Check port 7071 is accessible
- Verify Redis is running

## 📚 Additional Resources

- **List all tasks**: `GET http://localhost:7071/api/tasks?planId={planId}`
- **Update task**: `PATCH http://localhost:7071/api/tasks/{taskId}`
- **Delete task**: `DELETE http://localhost:7071/api/tasks/{taskId}`
- **Get task details**: `GET http://localhost:7071/api/tasks/{taskId}`

## ✨ Example: Complete Task Creation Flow with Caching

```python
import requests
import json
import time

# Step 1: Get available plans (uses cache if available)
plans_response = requests.get("http://localhost:7071/api/plans")
plans = plans_response.json()["value"]
plan_id = plans[0]["id"]  # Use first plan

# Step 2: Get cached plan details (super fast!)
plan_cache_response = requests.get(
    f"http://localhost:7071/api/metadata?type=plan&id={plan_id}"
)
if plan_cache_response.status_code == 200:
    plan_data = plan_cache_response.json()
    print(f"📋 Using cached plan: {plan_data['title']}")
    buckets = plan_data.get('buckets', [])
    bucket_id = buckets[0]["id"] if buckets else None
else:
    # Fallback to API if not cached
    buckets_response = requests.get(
        f"http://localhost:7071/api/plans/{plan_id}/buckets"
    )
    buckets = buckets_response.json()["value"]
    bucket_id = buckets[0]["id"] if buckets else None

# Step 3: Get user details from cache (0.1ms vs 300ms!)
user_id = "5ac3e02f-825f-49f1-a2e2-8fe619020b60"
user_response = requests.get(
    f"http://localhost:7071/api/metadata?type=user&id={user_id}"
)
if user_response.status_code == 200:
    user_data = user_response.json()
    print(f"📧 Assigning to: {user_data['displayName']} ({user_data['mail']})")

# Step 4: Create a task
task_data = {
    "title": f"Automated Task for {user_data.get('displayName', 'User')}",
    "planId": plan_id,
    "bucketId": bucket_id,
    "assignedTo": [user_id],
    "dueDate": "2025-06-30",
    "percentComplete": 0
}

create_response = requests.post(
    "http://localhost:7071/api/agent/tasks",
    json=task_data
)

if create_response.status_code == 201:
    result = create_response.json()
    print(f"✅ Task created successfully!")
    print(f"   Task ID: {result['task']['id']}")
    print(f"   Status: {result['status']}")
    
    # Task syncs immediately (event-driven)
    print("⚡ Task will sync to Planner within seconds...")
    
    # Optional: Subscribe to sync confirmations
    print("💡 Tip: Subscribe to 'annika:tasks:sync' for sync confirmations")
else:
    print(f"❌ Error: {create_response.status_code}")
    print(create_response.text)
```

This completes the guide for creating tasks that sync with Microsoft Planner! 🎉 