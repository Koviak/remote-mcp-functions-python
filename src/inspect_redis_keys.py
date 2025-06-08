#!/usr/bin/env python3
"""Inspect Redis keys to understand MCP and Annika format differences."""

import redis
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Connect to Redis
client = redis.Redis(
    host='localhost', port=6379, password='password', 
    decode_responses=True
)


def inspect_redis_keys():
    """Inspect all Redis keys and categorize them"""
    logger.info("🔍 Inspecting Redis Keys for MCP-Annika Integration")
    logger.info("="*60)
    
    # Get all annika keys
    all_keys = client.keys("annika:*")
    logger.info(f"\nTotal annika keys: {len(all_keys)}")
    
    # Categorize keys
    categories = {
        "conscious_state": [],
        "consciousness_conv": [],
        "tasks_individual": [],
        "task_mappings": [],
        "task_ops": [],
        "graph_cache": [],
        "planner_mappings": [],
        "other": []
    }
    
    for key in all_keys:
        if key == "annika:conscious_state":
            categories["conscious_state"].append(key)
        elif ":consciousness:" in key and ":components:" in key:
            categories["consciousness_conv"].append(key)
        elif key.startswith("annika:tasks:") and "mapping" not in key:
            categories["tasks_individual"].append(key)
        elif "mapping" in key:
            categories["task_mappings"].append(key)
        elif "task_ops" in key:
            categories["task_ops"].append(key)
        elif "graph" in key:
            categories["graph_cache"].append(key)
        elif "planner" in key:
            categories["planner_mappings"].append(key)
        else:
            categories["other"].append(key)
    
    # Display categorized keys
    for category, keys in categories.items():
        if keys:
            logger.info(f"\n📁 {category.upper()} ({len(keys)} keys)")
            for key in keys[:5]:  # Show first 5
                logger.info(f"  - {key}")
            if len(keys) > 5:
                logger.info(f"  ... and {len(keys) - 5} more")
    
    # Inspect conscious_state structure
    if categories["conscious_state"]:
        logger.info("\n🧠 CONSCIOUS STATE STRUCTURE:")
        try:
            # Use JSON.GET for RedisJSON documents
            data = client.execute_command(
                "JSON.GET", "annika:conscious_state", "$"
            )
            if data:
                # JSON.GET returns JSON array, get first element
                state = json.loads(data)[0]
                if "task_lists" in state:
                    for list_name, list_data in state["task_lists"].items():
                        task_count = len(list_data.get("tasks", []))
                        logger.info(f"  - {list_name}: {task_count} tasks")
                        
                        # Show sample task structure
                        if task_count > 0:
                            sample_task = list_data["tasks"][0]
                            fields = list(sample_task.keys())[:10]
                            logger.info(
                                f"    Sample task fields: {fields}..."
                            )
        except Exception as e:
            logger.error(f"  Error reading conscious_state: {e}")
    
    # Inspect individual task format
    if categories["tasks_individual"]:
        logger.info("\n📋 INDIVIDUAL TASK FORMAT (MCP Style):")
        sample_key = categories["tasks_individual"][0]
        try:
            data = client.get(sample_key)
            if data:
                task = json.loads(data)
                logger.info(f"  Key: {sample_key}")
                logger.info(f"  Fields: {list(task.keys())}")
                logger.info("  Sample data:")
                fields = ["title", "percentComplete", 
                          "assignedTo", "createdBy"]
                for field in fields:
                    if field in task:
                        logger.info(f"    - {field}: {task[field]}")
        except Exception as e:
            logger.error(f"  Error reading task: {e}")
    
    # Check for task operation queue
    logger.info("\n⚙️ TASK OPERATION QUEUE:")
    queue_len = client.llen("annika:task_ops:requests")
    logger.info(f"  - annika:task_ops:requests: {queue_len} pending operations")
    
    # Check mappings
    if categories["task_mappings"] or categories["planner_mappings"]:
        logger.info("\n🔗 MAPPING KEYS:")
        all_mappings = categories["task_mappings"] + categories["planner_mappings"]
        for key in all_mappings[:10]:
            value = client.get(key)
            if value:
                logger.info(f"  - {key} -> {value}")
    
    # Recommendations
    logger.info("\n💡 RECOMMENDATIONS FOR INTEGRATION:")
    logger.info("1. MCP server should read from annika:conscious_state instead of individual keys")
    logger.info("2. Need to convert field names: percentComplete -> percent_complete")
    logger.info("3. Need to convert assignedTo array to assigned_to string")
    logger.info("4. Use annika:task_ops:requests for creating/updating tasks")
    logger.info("5. Keep mapping keys but consider renaming to annika:planner:mapping:*")

def check_task_format_differences():
    """Compare task formats between MCP and Annika"""
    logger.info("\n\n📊 TASK FORMAT COMPARISON")
    logger.info("="*60)
    
    # Try to find a task in both formats
    mcp_task = None
    annika_task = None
    
    # Get MCP style task
    mcp_keys = client.keys("annika:tasks:*")
    for key in mcp_keys:
        if "mapping" not in key:
            data = client.get(key)
            if data:
                mcp_task = json.loads(data)
                logger.info(f"\n🔸 MCP Task Format (from {key}):")
                break
    
    # Get Annika style task from conscious_state
    conscious_data = client.get("annika:conscious_state")
    if conscious_data:
        state = json.loads(conscious_data)
        for list_name, list_data in state.get("task_lists", {}).items():
            if list_data.get("tasks"):
                annika_task = list_data["tasks"][0]
                logger.info(f"\n🔹 Annika Task Format (from conscious_state.{list_name}):")
                break
    
    # Compare formats
    if mcp_task and annika_task:
        # Field mapping
        field_map = {
            "MCP Field": "Annika Field",
            "percentComplete": "percent_complete",
            "assignedTo": "assigned_to", 
            "dueDateTime": "due_date",
            "createdDateTime": "created_at",
            "plannerId": "external_id"
        }
        
        logger.info("\n📌 Field Mapping Required:")
        for mcp_field, annika_field in field_map.items():
            if mcp_field == "MCP Field":
                logger.info(f"  {mcp_field:<20} -> {annika_field}")
                logger.info("  " + "-"*40)
            else:
                mcp_val = mcp_task.get(mcp_field, "N/A")
                annika_val = annika_task.get(annika_field, "N/A")
                logger.info(f"  {mcp_field:<20} -> {annika_field:<20}")
                logger.info(f"    MCP: {str(mcp_val)[:50]}")
                logger.info(f"    Annika: {str(annika_val)[:50]}")

if __name__ == "__main__":
    inspect_redis_keys()
    check_task_format_differences()
    logger.info("\n✅ Inspection complete!") 