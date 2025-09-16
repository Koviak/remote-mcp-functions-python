"""
Annika Task Adapter

Converts between Annika's task format and MS Planner format
for bidirectional synchronization.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Field mappings
PLANNER_TO_ANNIKA_FIELDS = {
    "percentComplete": "percent_complete",
    "assignedTo": "assigned_to",
    "dueDateTime": "due_date",
    "createdDateTime": "created_at",
    "completedDateTime": "completed_at",
    "id": "external_id",  # Store Planner ID as external_id
}

ANNIKA_TO_PLANNER_FIELDS = {
    v: k for k, v in PLANNER_TO_ANNIKA_FIELDS.items()
}

# User ID mappings - automatically loaded from settings
USER_ID_MAP = {}

# Load from environment/settings
agent_user_id = os.getenv("AGENT_USER_ID")
agent_user_name = os.getenv("AGENT_USER_NAME", "Annika")

if agent_user_id:
    name = agent_user_name.split("@")[0].title()
    USER_ID_MAP[agent_user_id] = name
    logger.info(f"Auto-loaded user mapping: {agent_user_id} -> {name}")

# Add any additional mappings from environment
# Format: USER_ID_MAP_1="id:name", USER_ID_MAP_2="id:name"
for key, value in os.environ.items():
    if key.startswith("USER_ID_MAP_"):
        try:
            user_id, user_name = value.split(":", 1)
            USER_ID_MAP[user_id] = user_name
            logger.info(f"Loaded additional mapping: {user_id} -> {user_name}")
        except ValueError:
            logger.warning(f"Invalid user mapping format: {value}")

# Default fallback if no mappings
if not USER_ID_MAP:
    logger.warning("No user ID mappings found. Using defaults.")
    USER_ID_MAP = {
        "5ac3e02f-825f-49f1-a2e2-8fe619020b60": "Joshua Koviak",
    }

USER_NAME_MAP = {v: k for k, v in USER_ID_MAP.items()}


class AnnikaTaskAdapter:
    """Adapts between Annika and MS Planner task formats."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        # Log current mappings on init
        logger.info(f"Initialized with {len(USER_ID_MAP)} user mappings")
        
    async def planner_to_annika(
        self, planner_task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert MS Planner task to Annika format."""
        annika_task = {
            "id": f"planner-{planner_task['id']}",
            "title": planner_task.get("title", "Untitled Task"),
            "description": planner_task.get("notes", ""),
            "priority": self._map_priority_to_annika(
                planner_task.get("priority", 5)
            ),
            "status": self._map_status_to_annika(
                planner_task.get("percentComplete", 0)
            ),
            "percent_complete": planner_task.get("percentComplete", 0) / 100.0,
            "source": "planner",
            "external_id": planner_task["id"],
        }
        
        # Map assigned users
        assigned_to_ids = list(planner_task.get("assignments", {}).keys())
        if assigned_to_ids:
            # Convert first user ID to name
            user_id = assigned_to_ids[0]
            annika_task["assigned_to"] = USER_ID_MAP.get(
                user_id, "Unknown User"
            )
        else:
            annika_task["assigned_to"] = "Annika"
        
        # Convert dates
        if planner_task.get("dueDateTime"):
            annika_task["due_date"] = planner_task["dueDateTime"].split("T")[0]
            
        if planner_task.get("createdDateTime"):
            annika_task["created_at"] = planner_task["createdDateTime"]
            
        if planner_task.get("completedDateTime"):
            annika_task["completed_at"] = planner_task["completedDateTime"]
        
        # Add standard Annika fields
        annika_task["checklist_items"] = []
        annika_task["dependencies"] = []
        annika_task["blocking"] = []
        annika_task["labels"] = []
        annika_task["attachments"] = []
        annika_task["notifications"] = []
        annika_task["notes"] = planner_task.get("notes", "")
        annika_task["bucket_id"] = planner_task.get("bucketId")
        annika_task["order"] = planner_task.get("orderHint", "")
        
        # Set timestamps
        now = datetime.utcnow().isoformat() + "Z"
        if "created_at" not in annika_task:
            annika_task["created_at"] = now
        annika_task["updated_at"] = now
        
        return annika_task
    
    def annika_to_planner(self, annika_task: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Annika task to MS Planner format."""
        # Normalize percent precision and map to 0..100 int
        pct = annika_task.get("percent_complete", 0)
        try:
            pct = round(float(pct), 2)
        except Exception:
            pct = 0.0
        planner_task = {
            "title": annika_task.get("title", "Untitled Task"),
            "percentComplete": int(pct * 100),
        }
        
        # Map assigned user
        assigned_to = annika_task.get("assigned_to")
        if assigned_to and assigned_to != "Annika":
            user_id = USER_NAME_MAP.get(assigned_to)
            if user_id:
                planner_task["assignments"] = {
                    user_id: {
                        "@odata.type": "#microsoft.graph.plannerAssignment",
                        "orderHint": " !"
                    }
                }
        
        # Map notes/description/output to Planner notes
        notes_parts: List[str] = []
        if annika_task.get("description"):
            notes_parts.append(str(annika_task.get("description")))
        if annika_task.get("notes"):
            notes_parts.append(str(annika_task.get("notes")))
        if annika_task.get("output"):
            notes_parts.append(
                "[Agent Output]\n" + str(annika_task.get("output"))
            )
        if notes_parts:
            planner_task["notes"] = "\n\n".join([p for p in notes_parts if p])
            
        if annika_task.get("due_date"):
            # Convert date to datetime
            date_str = annika_task["due_date"] + "T00:00:00Z"
            planner_task["dueDateTime"] = date_str
            
        if annika_task.get("bucket_id"):
            planner_task["bucketId"] = annika_task["bucket_id"]
            
        if annika_task.get("priority"):
            planner_task["priority"] = self._map_priority_to_planner(
                annika_task["priority"]
            )
        
        return planner_task
    
    def _map_priority_to_annika(self, planner_priority: int) -> str:
        """Map Planner priority (0-10) to Annika priority."""
        if planner_priority <= 1:
            return "urgent"
        elif planner_priority <= 4:
            return "high"
        elif planner_priority <= 7:
            return "normal"
        else:
            return "low"
    
    def _map_priority_to_planner(self, annika_priority: str) -> int:
        """Map Annika priority to Planner priority (0-10)."""
        mapping = {
            "urgent": 1,
            "high": 3,
            "normal": 5,
            "low": 9
        }
        return mapping.get(annika_priority, 5)
    
    def _map_status_to_annika(self, percent_complete: int) -> str:
        """Map completion percentage to Annika status."""
        if percent_complete == 0:
            return "not_started"
        elif percent_complete == 100:
            return "completed"
        else:
            return "in_progress"
    
    async def get_all_annika_tasks(self) -> List[Dict[str, Any]]:
        """Extract all tasks from Annika's conscious_state structure."""
        all_tasks: List[Dict[str, Any]] = []
        # Map by id to deduplicate and to allow "latest wins" merging
        by_id: Dict[str, Dict[str, Any]] = {}

        def _ts(task: Dict[str, Any]) -> str:
            return (
                task.get("last_modified_at")
                or task.get("updated_at")
                or task.get("modified_at")
                or ""
            )
        
        try:
            # Get global conscious state
            state_json = await self.redis.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            
            if state_json:
                state = json.loads(state_json)[0]
                
                # Extract tasks from each list
                task_lists = state.get("task_lists", {})
                for list_type, list_data in task_lists.items():
                    for task in list_data.get("tasks", []):
                        # Add metadata about source
                        task["_source_list"] = list_type
                        task["_source_type"] = "global"
                        tid = task.get("id")
                        if not tid:
                            continue
                        # Keep latest by timestamp
                        prev = by_id.get(tid)
                        if not prev or _ts(task) > _ts(prev):
                            by_id[tid] = task
            
            # Also get conversation-specific tasks
            conv_keys = await self.redis.keys(
                "annika:consciousness:*:components:tasks"
            )
            
            for key in conv_keys:
                # Extract conversation ID
                parts = key.split(":")
                conv_id = parts[2] if len(parts) > 2 else "unknown"
                
                try:
                    conv_json = await self.redis.execute_command(
                        "JSON.GET", key, "$"
                    )
                    
                    if conv_json:
                        data = json.loads(conv_json)[0]
                        for task in data.get("active_conversation", {}).get(
                            "tasks", []
                        ):
                            task["_source_type"] = "conversation"
                            task["_conversation_id"] = conv_id
                            tid = task.get("id")
                            if not tid:
                                continue
                            prev = by_id.get(tid)
                            if not prev or _ts(task) > _ts(prev):
                                by_id[tid] = task
                except Exception as e:
                    logger.error("Error reading %s: %s", key, e)
            
            # Always also read per-task authoritative keys and merge (latest wins)
            try:
                cursor = 0
                pattern = "annika:tasks:*"
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=pattern, count=200
                    )
                    for task_key in keys:
                        try:
                            raw = await self.redis.get(task_key)
                            if not raw:
                                continue
                            task = json.loads(raw)
                            if not isinstance(task, dict):
                                continue
                            tid = task.get("id")
                            if not tid:
                                continue
                            prev = by_id.get(tid)
                            if not prev or _ts(task) > _ts(prev):
                                by_id[tid] = task
                        except Exception:
                            # skip malformed entries
                            continue
                    if cursor == 0:
                        break
            except Exception as e:
                logger.debug("Authoritative annika:tasks scan failed: %s", e)
                    
        except Exception as e:
            logger.error(f"Error extracting Annika tasks: {e}")
            
        # Consolidate map to list
        if by_id:
            all_tasks = list(by_id.values())
        return all_tasks
    
    def determine_task_list(self, planner_task: Dict[str, Any]) -> str:
        """Determine which Annika task list a Planner task belongs to."""
        # You can implement logic based on:
        # - Bucket name
        # - Plan name
        # - Task title/description keywords
        # - Assignee
        
        # Default logic
        title_lower = planner_task.get("title", "").lower()
        
        research_words = ["research", "analyze", "study"]
        if any(word in title_lower for word in research_words):
            return "research_tasks"
            
        follow_words = ["follow", "check", "review"]
        if any(word in title_lower for word in follow_words):
            return "follow_up_tasks"
        elif planner_task.get("assignments"):
            return "user_tasks"
        else:
            return "system_two_tasks"