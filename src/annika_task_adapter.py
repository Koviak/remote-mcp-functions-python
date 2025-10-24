"""
Annika Task Adapter

Converts between Annika's task format and MS Planner format
for bidirectional synchronization.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Iterable

from uuid import uuid4

try:
    from src.graph_metadata_manager import GraphMetadataManager  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local execution fallback
    try:
        from graph_metadata_manager import GraphMetadataManager  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - optional dependency in isolated tests
        GraphMetadataManager = None  # type: ignore[assignment]

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
        if GraphMetadataManager:
            self.metadata_manager = GraphMetadataManager()
        else:
            self.metadata_manager = None
        # Log current mappings on init
        logger.info(f"Initialized with {len(USER_ID_MAP)} user mappings")

    @staticmethod
    def _parse_json_result(raw: Any) -> Any:
        """Normalize RedisJSON responses into native Python objects."""
        if raw is None:
            return None
        if isinstance(raw, (dict, list)):
            return raw
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logger.debug("Failed to decode RedisJSON payload", exc_info=True)
            return None
        if isinstance(data, list) and len(data) == 1:
            return data[0]
        return data

    @staticmethod
    def _serialize_json_value(value: Any) -> str:
        """Serialize a value for RedisJSON operations."""
        return json.dumps(value)

    async def _redis_json_get(self, key: str, path: str = "$") -> Any:
        """Retrieve a value from RedisJSON storage."""
        try:
            raw = await self.redis.execute_command("JSON.GET", key, path)
        except Exception as exc:
            logger.debug("RedisJSON GET failed for %s: %s", key, exc)
            return None
        return self._parse_json_result(raw)

    async def _redis_json_set(
        self, key: str, value: Any, path: str = "$", expire: Optional[int] = None
    ) -> None:
        """Store a value using RedisJSON and optionally apply a TTL."""
        payload = self._serialize_json_value(value)
        await self.redis.execute_command("JSON.SET", key, path, payload)
        if expire is not None:
            await self.redis.expire(key, expire)

    async def _redis_json_update(self, key: str, path: str, value: Any) -> None:
        """Perform a partial update on a RedisJSON document."""
        payload = self._serialize_json_value(value)
        await self.redis.execute_command("JSON.SET", key, path, payload)

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
            "planner_id": planner_task["id"],
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

        plan_id = planner_task.get("planId")
        plan_data: Optional[Dict[str, Any]] = None
        if plan_id:
            annika_task["planner_plan_id"] = plan_id
            annika_task.setdefault("plan_id", plan_id)
            plan_data = None
            if self.metadata_manager:
                try:
                    plan_data = await self.metadata_manager.get_cached_metadata("plan", plan_id)
                    if not plan_data:
                        plan_data = await self.metadata_manager.cache_plan_metadata(plan_id)
                except Exception:
                    plan_data = None
            if isinstance(plan_data, dict):
                annika_task.setdefault(
                    "planner_plan_title", plan_data.get("title")
                )
                annika_task.setdefault(
                    "planner_plan_owner_id",
                    (plan_data.get("createdBy", {}).get("user") or {}).get("id"),
                )

        bucket_id = planner_task.get("bucketId")
        bucket_name = None
        order_hint = planner_task.get("orderHint")
        bucket_order_hint = order_hint
        if bucket_id:
            annika_task["planner_bucket_id"] = bucket_id
            annika_task.setdefault("bucket_id", bucket_id)
            # Try to hydrate bucket metadata from cache
            if self.metadata_manager:
                try:
                    bucket_data = await self.metadata_manager.get_cached_metadata("bucket", bucket_id)
                    if not bucket_data and plan_id:
                        await self.metadata_manager.cache_plan_metadata(plan_id)  # refresh plan+buckets
                        bucket_data = await self.metadata_manager.get_cached_metadata("bucket", bucket_id)
                    if isinstance(bucket_data, dict):
                        bucket_name = bucket_data.get("name")
                        bucket_order_hint = bucket_data.get("orderHint", order_hint)
                    elif order_hint and isinstance(plan_data, dict):
                        try:
                            for bucket in plan_data.get("buckets", []) or []:
                                if bucket.get("id") == bucket_id:
                                    bucket_name = bucket.get("name", bucket_name)
                                    bucket_order_hint = bucket.get("orderHint", bucket_order_hint)
                                    break
                        except Exception:
                            pass
                except Exception:
                    bucket_name = None
            if bucket_name is None:
                try:
                    bucket_data = await self._redis_json_get(f"annika:graph:buckets:{bucket_id}")
                    if isinstance(bucket_data, dict):
                        bucket_name = bucket_data.get("name", bucket_name)
                        bucket_order_hint = bucket_data.get("orderHint", bucket_order_hint)
                except Exception:
                    pass
        annika_task.setdefault("planner_bucket_id", bucket_id)
        annika_task.setdefault("planner_bucket_name", bucket_name)
        annika_task.setdefault("planner_bucket_order_hint", bucket_order_hint)
        
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
            due_date = annika_task["due_date"]
            # Check if due_date already has time component (contains 'T')
            if 'T' in due_date:
                # Already has time component, use as-is
                # But ensure it ends with 'Z' timezone indicator
                date_str = due_date if due_date.endswith('Z') else due_date + 'Z'
            else:
                # Just a date string, append time component
                date_str = due_date + "T00:00:00Z"
            planner_task["dueDateTime"] = date_str
            
        bucket_id = (
            annika_task.get("planner_bucket_id")
            or annika_task.get("bucket_id")
        )
        if bucket_id:
            planner_task["bucketId"] = bucket_id
            
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
            state = await self._redis_json_get("annika:conscious_state")

            if isinstance(state, dict):
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
                    data = await self._redis_json_get(key)
                    if isinstance(data, dict):
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
                            task = await self._redis_json_get(task_key)
                            if not isinstance(task, dict):
                                logger.debug(
                                    "Skipping non-object RedisJSON payload for %s",
                                    task_key,
                                )
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

    async def get_subtasks_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all subtasks for a parent task from Redis."""
        subtasks = []
        try:
            # Get parent task to find subtask_ids
            parent = await self._redis_json_get(f"annika:tasks:{task_id}")
            if parent and parent.get("subtask_ids"):
                for subtask_id in parent["subtask_ids"]:
                    subtask = await self._redis_json_get(f"annika:tasks:{subtask_id}")
                    if subtask:
                        subtasks.append(subtask)
        except Exception as e:
            logger.debug(f"Error loading subtasks for {task_id}: {e}")
        return subtasks

    async def annika_subtasks_to_planner_checklist(
        self,
        task_id: str,
        inline_subtasks: Optional[Iterable[Dict[str, Any]]] = None,
        inline_prerequisites: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Convert Annika subtasks/prerequisites to Planner checklist format."""

        checklist: Dict[str, Dict[str, Any]] = {}
        seen_ids: set[str] = set()

        def _derive_title(source: Dict[str, Any], fallback_index: int) -> str:
            raw_title = (
                source.get("title")
                or source.get("name")
                or source.get("description")
                or f"Checklist item {fallback_index}"
            )
            return str(raw_title)[:256]

        def _derive_state(source: Dict[str, Any]) -> bool:
            if "isChecked" in source:
                return bool(source["isChecked"])
            if "completed" in source:
                return bool(source["completed"])
            status = (source.get("status") or "").lower()
            return status in {"completed", "done", "finished"}

        def _normalize_item_id(candidate: Optional[str]) -> str:
            if not candidate:
                return uuid4().hex
            candidate = str(candidate)
            if candidate.startswith("Task-"):
                candidate = candidate.replace("Task-", "", 1)
            if candidate in seen_ids:
                candidate = uuid4().hex
            seen_ids.add(candidate)
            return candidate

        aggregated: List[Dict[str, Any]] = []

        if inline_subtasks:
            aggregated.extend(list(inline_subtasks))
        if inline_prerequisites:
            aggregated.extend(list(inline_prerequisites))

        redis_subtasks = await self.get_subtasks_for_task(task_id)
        aggregated.extend(redis_subtasks)

        for idx, subtask in enumerate(aggregated, start=1):
            item_id = _normalize_item_id(subtask.get("id") or subtask.get("external_id"))
            checklist[item_id] = {
                "@odata.type": "microsoft.graph.plannerChecklistItem",
                "title": _derive_title(subtask, idx),
                "isChecked": _derive_state(subtask),
                "orderHint": subtask.get("order_hint") or " !",
            }

        return checklist

    async def planner_checklist_to_annika_subtasks(
        self, parent_task_id: str, checklist: Dict[str, Any]
    ) -> List[str]:
        """Convert Planner checklist items to Annika subtasks.
        
        Returns list of subtask IDs created/updated.
        """
        subtask_ids = []
        
        for item_id, item_data in checklist.items():
            if item_data is None:
                # Deleted item - remove corresponding subtask
                subtask_id = f"Task-{item_id}"
                await self.redis.delete(f"annika:tasks:{subtask_id}")
                continue
                
            # Create or update subtask
            subtask_id = f"Task-{item_id}"
            subtask = {
                "id": subtask_id,
                "title": item_data.get("title", ""),
                "status": "completed" if item_data.get("isChecked") else "not_started",
                "parent_task_id": parent_task_id,
                "source": "planner",
                "external_id": item_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            
            await self._redis_json_set(f"annika:tasks:{subtask_id}", subtask)
            subtask_ids.append(subtask_id)
        
        return subtask_ids
