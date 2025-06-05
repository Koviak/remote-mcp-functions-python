# Planner Agent Task Creation Guide

## How Agents Create Tasks with Redis-First Architecture

This guide explains how your Planner Agent creates tasks using our optimized Redis-first architecture, where agents work at microsecond speeds while background services handle Microsoft Planner synchronization.

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

# Store task in Redis
redis_client.set(
    f"annika:tasks:{task['id']}",
    json.dumps(task),
    ex=86400  # 24 hour expiry
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

## 📝 Important Notes

1. **Plan ID Required**: You must specify a valid plan ID that Annika has access to
2. **Permissions**: The agent user (Annika) must have permissions in the specified plan
3. **Human Tasks**: Tasks created by humans in Planner appear in Redis within 30 seconds
4. **Error Handling**: The sync service handles retries automatically
5. **Task IDs**: Use Redis IDs for agent operations, Planner IDs are handled by sync service

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

## ✨ Example: Complete Task Creation Flow

```python
import requests
import json
import time

# Step 1: Get available plans
plans_response = requests.get("http://localhost:7071/api/plans")
plans = plans_response.json()["value"]
plan_id = plans[0]["id"]  # Use first plan

# Step 2: Get buckets in the plan
buckets_response = requests.get(
    f"http://localhost:7071/api/plans/{plan_id}/buckets"
)
buckets = buckets_response.json()["value"]
bucket_id = buckets[0]["id"] if buckets else None

# Step 3: Create a task
task_data = {
    "title": "Automated Task from Planner Agent",
    "planId": plan_id,
    "bucketId": bucket_id,
    "assignedTo": ["5ac3e02f-825f-49f1-a2e2-8fe619020b60"],
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
    
    # Wait for sync
    print("⏳ Waiting for sync to Planner...")
    time.sleep(35)
    
    print("✅ Task should now be visible in Microsoft Planner!")
else:
    print(f"❌ Error: {create_response.status_code}")
    print(create_response.text)
```

This completes the guide for creating tasks that sync with Microsoft Planner! 🎉 