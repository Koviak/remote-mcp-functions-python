#!/usr/bin/env python
"""
Test script to verify Planner ↔ Annika sync is working after fixes
"""
import json
import redis
import asyncio
from datetime import datetime
from typing import Dict, List, Any

def connect_redis():
    """Connect to Redis using standard configuration"""
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        r.ping()
        print("✓ Connected to Redis successfully\n")
        return r
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return None

def check_mappings(r: redis.Redis):
    """Check if ID mappings are correctly stored"""
    print("=" * 70)
    print("CHECKING ID MAPPINGS")
    print("=" * 70)
    
    # Get all mapping keys
    forward_keys = r.keys("annika:planner:id_map:*")
    reverse_keys = r.keys("annika:task:mapping:planner:*")
    
    print(f"\nForward mappings (Annika → Planner): {len(forward_keys)}")
    print(f"Reverse mappings (Planner → Annika): {len(reverse_keys)}")
    
    # Check a sample of mappings
    correct_count = 0
    incorrect_count = 0
    
    for key in forward_keys[:10]:
        key_id = key.replace("annika:planner:id_map:", "")
        value = r.get(key)
        
        # Check if key looks like Annika ID and value looks like Planner ID
        if key_id.startswith("Task-"):
            # This is correct
            correct_count += 1
            print(f"✅ Correct: {key_id[:20]}... → {value[:20] if value else 'None'}...")
        else:
            # This looks like a Planner ID as key (wrong)
            incorrect_count += 1
            print(f"❌ Wrong: {key_id[:20]}... → {value[:20] if value else 'None'}...")
    
    print(f"\nMapping Status: {correct_count} correct, {incorrect_count} incorrect")
    return incorrect_count == 0

def check_tasks(r: redis.Redis):
    """Check if tasks are properly stored"""
    print("\n" + "=" * 70)
    print("CHECKING TASK STORAGE")
    print("=" * 70)
    
    # Get all task keys
    task_keys = r.keys("annika:tasks:*")
    print(f"\nTotal tasks in annika:tasks:*: {len(task_keys)}")
    
    if task_keys:
        print("\nSample tasks:")
        for key in task_keys[:5]:
            task_data = r.get(key)
            if task_data:
                try:
                    task = json.loads(task_data)
                    task_id = key.replace("annika:tasks:", "")
                    print(f"\n📋 Task: {task_id}")
                    print(f"   Title: {task.get('title', 'No title')}")
                    print(f"   Status: {task.get('status', 'Unknown')}")
                    print(f"   Source: {task.get('source', 'Unknown')}")
                    print(f"   External ID: {task.get('external_id', 'None')}")
                except Exception as e:
                    print(f"   Error parsing task: {e}")
    else:
        print("\n⚠️ No tasks found in annika:tasks:*")
    
    return len(task_keys) > 0

def check_sync_health(r: redis.Redis):
    """Check sync service health"""
    print("\n" + "=" * 70)
    print("SYNC SERVICE HEALTH")
    print("=" * 70)
    
    # Check sync health
    sync_health = r.get("annika:sync:health")
    if sync_health:
        try:
            health_data = json.loads(sync_health)
            print(f"\n📊 Health Status (as of {health_data.get('timestamp', 'Unknown')})")
            print(f"   Processed tasks: {health_data.get('processed_tasks', 0)}")
            print(f"   Pending uploads: {health_data.get('pending_uploads', 0)}")
            print(f"   Failed operations: {health_data.get('failed_operations', 0)}")
            print(f"   Webhook status: {health_data.get('webhook_status', 'Unknown')}")
        except:
            print("   Error parsing health data")
    else:
        print("\n⚠️ No sync health data available")
    
    # Check recent sync log
    sync_log = r.lrange("annika:sync:log", 0, 5)
    if sync_log:
        print("\n📜 Recent Sync Operations:")
        for entry in sync_log:
            try:
                log_data = json.loads(entry)
                print(f"\n   {log_data.get('timestamp', 'Unknown time')}")
                print(f"   Operation: {log_data.get('operation', 'Unknown')}")
                print(f"   Status: {log_data.get('status', 'Unknown')}")
                if log_data.get('error'):
                    print(f"   Error: {log_data.get('error')}")
            except:
                pass

async def listen_for_notifications():
    """Listen for task notifications on Redis pub/sub"""
    print("\n" + "=" * 70)
    print("LISTENING FOR NOTIFICATIONS (10 seconds)")
    print("=" * 70)
    
    try:
        r = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        
        pubsub = r.pubsub()
        pubsub.subscribe("annika:tasks:updates")
        
        print("\n🎧 Listening on annika:tasks:updates channel...")
        print("   (Create or update a task in Planner to test)")
        
        start_time = datetime.now()
        timeout = 10  # seconds
        
        while (datetime.now() - start_time).seconds < timeout:
            message = pubsub.get_message(timeout=1)
            if message and message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    print(f"\n📬 Notification received!")
                    print(f"   Action: {data.get('action')}")
                    print(f"   Task ID: {data.get('task_id')}")
                    print(f"   Source: {data.get('source')}")
                    if data.get('task'):
                        print(f"   Title: {data['task'].get('title')}")
                except:
                    print(f"   Raw message: {message['data']}")
        
        print(f"\n⏱️ Timeout after {timeout} seconds")
        
    except Exception as e:
        print(f"\n❌ Error listening for notifications: {e}")

def main():
    print("\n" + "=" * 70)
    print("PLANNER ↔ ANNIKA SYNC TEST")
    print("=" * 70)
    
    # Connect to Redis
    r = connect_redis()
    if not r:
        return
    
    # Run checks
    mappings_ok = check_mappings(r)
    tasks_exist = check_tasks(r)
    check_sync_health(r)
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    if mappings_ok:
        print("✅ ID mappings are correctly stored")
    else:
        print("❌ Some ID mappings are still reversed")
    
    if tasks_exist:
        print("✅ Tasks are being stored in annika:tasks:*")
    else:
        print("❌ No tasks found - sync may not be creating tasks")
    
    print("\n📝 Next Steps:")
    print("1. Restart the MS-MCP sync service to apply the fixes")
    print("2. Create a test task in Microsoft Planner")
    print("3. Run this script again to verify the task appears")
    print("4. Check if agents receive notifications")
    
    # Optional: Listen for notifications
    user_input = input("\nListen for notifications? (y/n): ")
    if user_input.lower() == 'y':
        asyncio.run(listen_for_notifications())

if __name__ == "__main__":
    main()
