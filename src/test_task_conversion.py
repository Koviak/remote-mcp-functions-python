#!/usr/bin/env python3
"""Test script to demonstrate task format conversions"""

import json
from annika_task_adapter import AnnikaTaskAdapter
import asyncio
import redis.asyncio as redis


async def test_conversions():
    """Test task format conversions."""
    # Create mock Redis client
    client = await redis.Redis(
        host='localhost', port=6379, password='password', 
        decode_responses=True
    )
    
    adapter = AnnikaTaskAdapter(client)
    
    print("🔄 TASK CONVERSION EXAMPLES")
    print("="*60)
    
    # Example Planner task
    planner_task = {
        "id": "AAMkAGI3NDdhZmVi",
        "title": "Review project documentation",
        "percentComplete": 75,
        "assignedTo": {
            "5ac3e02f-825f-49f1-a2e2-8fe619020b60": True
        },
        "assignments": {
            "5ac3e02f-825f-49f1-a2e2-8fe619020b60": {
                "@odata.type": "#microsoft.graph.plannerAssignment",
                "orderHint": " !"
            }
        },
        "dueDateTime": "2024-01-25T00:00:00Z",
        "createdDateTime": "2024-01-15T10:30:00Z",
        "priority": 3,
        "notes": "Need to review API documentation and update examples",
        "bucketId": "bucket-123",
        "planId": "plan-456"
    }
    
    print("\n📥 MS PLANNER TASK:")
    print(json.dumps(planner_task, indent=2))
    
    # Convert to Annika format
    annika_task = await adapter.planner_to_annika(planner_task)
    
    print("\n📤 CONVERTED TO ANNIKA FORMAT:")
    print(json.dumps(annika_task, indent=2))
    
    print("\n" + "-"*60 + "\n")
    
    # Example Annika task
    annika_task_example = {
        "id": "Task-CV123-1",
        "title": "Implement user authentication",
        "description": "Add OAuth2 authentication to the API endpoints",
        "priority": "high",
        "status": "in_progress",
        "percent_complete": 0.3,
        "assigned_to": "Joshua Koviak",
        "due_date": "2024-01-30",
        "created_at": "2024-01-10T08:00:00Z",
        "bucket_id": "bucket-789"
    }
    
    print("📥 ANNIKA TASK:")
    print(json.dumps(annika_task_example, indent=2))
    
    # Convert to Planner format
    planner_converted = adapter.annika_to_planner(annika_task_example)
    
    print("\n📤 CONVERTED TO PLANNER FORMAT:")
    print(json.dumps(planner_converted, indent=2))
    
    # Close Redis connection
    await client.close()


async def test_extraction():
    """Test extracting tasks from conscious_state."""
    client = await redis.Redis(
        host='localhost', port=6379, password='password', 
        decode_responses=True
    )
    
    adapter = AnnikaTaskAdapter(client)
    
    print("\n\n🔍 EXTRACTING TASKS FROM CONSCIOUS_STATE")
    print("="*60)
    
    try:
        all_tasks = await adapter.get_all_annika_tasks()
        
        print(f"\nFound {len(all_tasks)} total tasks")
        
        # Group by source list
        by_list = {}
        for task in all_tasks:
            list_type = task.get("_source_list", "unknown")
            if list_type not in by_list:
                by_list[list_type] = []
            by_list[list_type].append(task)
        
        print("\nTasks by list:")
        for list_type, tasks in by_list.items():
            print(f"  - {list_type}: {len(tasks)} tasks")
            
            # Show first task as example
            if tasks:
                example = tasks[0]
                print(f"    Example: {example.get('title', 'Untitled')}")
                print(f"    Status: {example.get('status', 'unknown')}")
                assigned = example.get('assigned_to', 'unassigned')
                print(f"    Assigned to: {assigned}")
        
    except Exception as e:
        print(f"Error extracting tasks: {e}")
    
    await client.close()


if __name__ == "__main__":
    print("Testing Annika-Planner task conversions...\n")
    asyncio.run(test_conversions())
    asyncio.run(test_extraction()) 