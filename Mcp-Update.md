1. Adapt MS-MCP to work with current Task Manager and redis Keys. 
2. Each agent can handle its own subscriptions. 


How does agent know if it is for them?
Multiple Recognition Signals:
Labels: [AGENT:researcher]

This is simple. Task manager can simply use labels. When a new task arrives from planner the task manager can take the task and assign it by adding the proper labels to it. (Modify Task)


Let's adapt the MS-MCP server to work with the existing TaskListManager structure. This is actually a much cleaner approach. Here's how to modify the MS-MCP server to be compatible:

## 🎯 MS-MCP Server Adaptation Strategy

### 1. **Understanding Current Key Structure**

```python
# Current TaskListManager keys:
REDIS_NAMESPACE = "annika:"  # From redis_connection.py

# Global conscious state (all non-conversation tasks)
annika:conscious_state
{
    "task_lists": {
        "user_tasks": {"tasks": [...], "buckets": [...]},
        "research_tasks": {"tasks": [...]},
        "system_two_tasks": {"tasks": [...]},
        # ... other lists
    }
}

# Conversation-specific tasks
annika:consciousness:{conversation_id}:components:tasks
{
    "active_conversation": {"tasks": [...]}
}

# Task operation channels (already exists!)
annika:task_ops:requests         # Operation queue
annika:task_ops:results:{op_id}  # Results
```

### 2. **MS-MCP Server Redis Monitor Configuration**

```python
# MS-MCP Server should monitor these patterns:
MONITOR_PATTERNS = [
    # Global task lists
    "__keyspace@0__:annika:conscious_state",
    
    # Conversation-specific tasks
    "__keyspace@0__:annika:consciousness:*:components:tasks",
    
    # Task operation requests (if needed)
    "__keyspace@0__:annika:task_ops:requests"
]

# MS-MCP Server Redis adapter
class AnnikaTaskAdapter:
    """Adapts Annika's task structure to MS Planner format."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.task_to_planner_map = {}  # Internal mapping
        
    async def extract_all_tasks(self) -> List[Dict]:
        """Extract tasks from Annika's structure."""
        all_tasks = []
        
        # 1. Get global tasks
        global_state = await self.redis.execute_command(
            "JSON.GET", "annika:conscious_state", "$"
        )
        if global_state:
            state = json.loads(global_state)
            for list_type, task_list in state.get("task_lists", {}).items():
                for task in task_list.get("tasks", []):
                    task["_source_list"] = list_type
                    task["_source_type"] = "global"
                    all_tasks.append(task)
        
        # 2. Get conversation-specific tasks
        conv_keys = await self.redis.keys("annika:consciousness:*:components:tasks")
        for key in conv_keys:
            # Extract conversation ID from key
            parts = key.split(":")
            conv_id = parts[2] if len(parts) > 2 else "unknown"
            
            conv_tasks = await self.redis.execute_command("JSON.GET", key, "$")
            if conv_tasks:
                data = json.loads(conv_tasks)
                if isinstance(data, list) and data:
                    data = data[0]
                
                for task in data.get("active_conversation", {}).get("tasks", []):
                    task["_source_list"] = "active_conversation"
                    task["_source_type"] = "conversation"
                    task["_conversation_id"] = conv_id
                    all_tasks.append(task)
        
        return all_tasks
    
    def convert_to_planner_task(self, annika_task: Dict) -> Dict:
        """Convert Annika task format to MS Planner format."""
        # Extract assignee
        assigned_to = annika_task.get("assigned_to", "")
        assignee_ids = []
        
        # Map Annika assignees to MS user IDs
        if assigned_to == "Joshua Koviak":
            assignee_ids = [self.get_user_id_by_name("Joshua Koviak")]
        elif assigned_to == "Annika":
            # Annika tasks might not have MS assignee
            assignee_ids = []
        elif "_agent" in assigned_to:
            # Agent tasks - maybe assign to a service account or leave empty
            assignee_ids = []
        
        # Determine bucket based on list type and status
        bucket_id = self.determine_bucket(
            annika_task.get("_source_list"),
            annika_task.get("status"),
            annika_task.get("priority")
        )
        
        return {
            "title": annika_task.get("title", "Untitled Task"),
            "notes": annika_task.get("description", ""),
            "bucketId": bucket_id,
            "assignedTo": assignee_ids,
            "percentComplete": int(annika_task.get("percent_complete", 0) * 100),
            "dueDate": annika_task.get("due_date"),
            "priority": self.map_priority(annika_task.get("priority")),
            "_annika_id": annika_task.get("id"),
            "_annika_list": annika_task.get("_source_list"),
            "_annika_conversation": annika_task.get("conversation_id")
        }
```

### 3. **Agent Subscription Pattern**

Agents can subscribe to the existing Redis patterns:

```python
# Agent subscription code
class ResearcherAgent:
    async def start_monitoring(self):
        """Monitor Annika's existing task structure."""
        pubsub = self.redis.pubsub()
        
        # Subscribe to both global and conversation updates
        await pubsub.subscribe(
            "annika:conscious_state",  # Global updates
            "annika:consciousness:*:components:tasks:updated"  # Conv updates
        )
        
        # Also monitor the operation queue for new tasks
        await pubsub.psubscribe("__keyspace@0__:annika:task_ops:requests")
        
        while self.running:
            message = await pubsub.get_message(timeout=1.0)
            if message:
                await self._handle_task_update(message)
    
    async def _handle_task_update(self, message):
        """Process task updates from existing structure."""
        if "conscious_state" in message.get("channel", ""):
            # Global task update
            await self._check_global_tasks()
        elif "components:tasks:updated" in message.get("channel", ""):
            # Conversation task update
            conv_id = self._extract_conv_id(message["channel"])
            await self._check_conversation_tasks(conv_id)
    
    async def _check_global_tasks(self):
        """Check global tasks for ones assigned to this agent."""
        state = await self.redis.execute_command(
            "JSON.GET", "annika:conscious_state", "$.task_lists.research_tasks"
        )
        if state:
            tasks = json.loads(state)[0].get("tasks", [])
            for task in tasks:
                if self._is_my_task(task):
                    await self._execute_task(task)
    
    def _is_my_task(self, task: Dict) -> bool:
        """Check if task is for this agent."""
        # Check assigned_to
        if task.get("assigned_to") == "researcher_agent":
            return True
        
        # Check task content for research keywords
        title = task.get("title", "").lower()
        desc = task.get("description", "").lower()
        
        research_keywords = ["research", "analyze", "investigate", "study"]
        return any(kw in title or kw in desc for kw in research_keywords)
```

### 4. **MS-MCP Server Sync Logic**

```python
# MS-MCP Server main sync loop
class MSMCPTaskSync:
    def __init__(self):
        self.adapter = AnnikaTaskAdapter(redis_client)
        self.planner_client = MSPlannerClient()
        self.sync_interval = 30  # seconds
        
    async def start_sync(self):
        """Main sync loop between Annika and MS Planner."""
        # Initial sync
        await self.full_sync()
        
        # Subscribe to updates
        pubsub = redis_client.pubsub()
        await pubsub.psubscribe(
            "__keyspace@0__:annika:conscious_state",
            "__keyspace@0__:annika:consciousness:*:components:tasks"
        )
        
        last_sync = time.time()
        
        while True:
            # Check for Redis updates
            message = await pubsub.get_message(timeout=1.0)
            if message and message["type"] == "pmessage":
                await self.handle_redis_update(message)
            
            # Periodic full sync
            if time.time() - last_sync > self.sync_interval:
                await self.sync_from_planner()  # Get human changes
                last_sync = time.time()
    
    async def handle_redis_update(self, message):
        """Handle updates from Annika's task system."""
        # Extract what changed
        key = message.get("channel", "").replace("__keyspace@0__:", "")
        
        # Get updated tasks
        tasks = await self.adapter.extract_all_tasks()
        
        # Sync changed tasks to Planner
        for task in tasks:
            annika_id = task.get("id")
            planner_id = self.get_planner_id(annika_id)
            
            if planner_id:
                # Update existing
                await self.update_planner_task(planner_id, task)
            else:
                # Create new
                planner_task = await self.create_planner_task(task)
                self.store_mapping(annika_id, planner_task["id"])
    
    async def sync_from_planner(self):
        """Sync changes from MS Planner back to Annika."""
        planner_tasks = await self.planner_client.get_all_tasks()
        
        for planner_task in planner_tasks:
            annika_id = self.get_annika_id(planner_task["id"])
            if not annika_id:
                # New task created in Planner
                await self.create_annika_task_from_planner(planner_task)
            else:
                # Update existing task
                await self.update_annika_task_from_planner(annika_id, planner_task)
```

### 5. **Task Creation Flow (Using Existing System)**

```python
# MS-MCP Server creates tasks in Annika format
async def create_annika_task_from_planner(self, planner_task: Dict):
    """Create task in Annika when human creates in Planner."""
    
    # Determine list type based on bucket/plan
    list_type = self.determine_list_type(planner_task)
    
    # Create task operation for TaskListManager
    operation = {
        "operation_id": str(uuid.uuid4()),
        "operation_type": "create_task",
        "payload": {
            "list_type": list_type,
            "title": planner_task["title"],
            "description": planner_task.get("notes", ""),
            "assigned_to": self.map_assignee_to_annika(planner_task),
            "percent_complete": planner_task.get("percentComplete", 0) / 100,
            "due_date": planner_task.get("dueDateTime"),
            "external_id": planner_task["id"],  # Store Planner ID
            "source": "planner"
        }
    }
    
    # Send to TaskListManager via existing operation queue
    await redis_client.lpush(
        "annika:task_ops:requests", 
        json.dumps(operation)
    )
    
    # Wait for result
    result_key = f"annika:task_ops:results:{operation['operation_id']}"
    # ... wait for result
```

### 6. **Simple Mapping Storage**

```python
# MS-MCP Server maintains simple mapping in Redis
class TaskMapping:
    """Simple bidirectional mapping between Annika and Planner IDs."""
    
    async def store_mapping(self, annika_id: str, planner_id: str):
        """Store ID mapping."""
        await redis.hset("annika:ms_planner:mapping", annika_id, planner_id)
        await redis.hset("annika:ms_planner:reverse_mapping", planner_id, annika_id)
    
    async def get_planner_id(self, annika_id: str) -> Optional[str]:
        """Get Planner ID for Annika task."""
        return await redis.hget("annika:ms_planner:mapping", annika_id)
    
    async def get_annika_id(self, planner_id: str) -> Optional[str]:
        """Get Annika ID for Planner task."""
        return await redis.hget("annika:ms_planner:reverse_mapping", planner_id)
```

## 📋 Summary: What MS-MCP Server Needs to Do

1. **Monitor existing Annika keys** (no new keys needed):
   - `annika:conscious_state`
   - `annika:consciousness:*:components:tasks`

2. **Extract and convert tasks**:
   - Parse nested JSON structures
   - Convert to MS Planner format
   - Maintain ID mappings

3. **Use existing operation queue** for creating tasks:
   - Send operations to `annika:task_ops:requests`
   - TaskListManager handles the actual task creation

4. **Agents subscribe to existing patterns**:
   - No new notification system needed
   - Use existing update channels

5. **Simple mapping storage**:
   - Just two hash maps for ID translation
   - No complex new key structures

This approach:
- ✅ Uses existing TaskListManager infrastructure
- ✅ No new MCP tools needed
- ✅ Agents can monitor existing patterns
- ✅ MS-MCP server adapts to Annika's structure
- ✅ Maintains bidirectional sync
- ✅ Achieves all goals from StepByStepSchema.md

The key insight is that the MS-MCP server becomes an **adapter** that translates between Annika's rich task structure and Microsoft Planner's format, rather than forcing a new structure on the existing system.