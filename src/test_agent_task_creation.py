#!/usr/bin/env python3
"""
Test script for Planner Agent task creation
Tests both HTTP API and direct Redis methods
"""

import requests
import redis
import json
from datetime import datetime


def test_http_api_method():
    """Test creating a task via HTTP API"""
    print("\n🧪 Testing HTTP API Method...")
    
    # First, get available plans
    try:
        response = requests.get(
            "http://localhost:7071/api/plans",
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ Failed to get plans: {response.status_code}")
            return False
            
        plans = response.json().get("value", [])
        if not plans:
            print("❌ No plans found")
            return False
            
        # Use the first plan
        plan = plans[0]
        print(f"✅ Found plan: {plan['title']} (ID: {plan['id']})")
        
        # Create a task
        task_data = {
            "title": f"Test Task from Agent - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "planId": plan['id'],
            "assignedTo": ["5ac3e02f-825f-49f1-a2e2-8fe619020b60"],  # Annika
            "dueDate": "2025-06-30",
            "percentComplete": 0
        }
        
        print(f"📝 Creating task: {task_data['title']}")
        
        response = requests.post(
            "http://localhost:7071/api/agent/tasks",
            json=task_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"✅ Task created successfully!")
            print(f"   Task ID: {result['task']['id']}")
            print(f"   Status: {result['status']}")
            return True
        else:
            print(f"❌ Failed to create task: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Function App on port 7071")
        print("   Make sure to run: cd src && func start")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_redis_direct_method():
    """Test creating a task directly via Redis"""
    print("\n🧪 Testing Direct Redis Method...")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        
        # Test connection
        redis_client.ping()
        print("✅ Connected to Redis")
        
        # Create task
        task = {
            "id": f"agent-task-{datetime.utcnow().timestamp()}",
            "title": f"Direct Redis Task - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "planId": "CbfN3rLYAkS0ZutzQP5J9mUAFxxt",  # You should replace with actual plan ID
            "assignedTo": ["5ac3e02f-825f-49f1-a2e2-8fe619020b60"],
            "dueDate": "2025-06-30",
            "percentComplete": 0,
            "createdBy": "test-agent",
            "createdAt": datetime.utcnow().isoformat()
        }
        
        print(f"📝 Creating task: {task['title']}")
        
        # Store task in Redis (primary storage)
        redis_client.set(
            f"annika:tasks:{task['id']}",
            json.dumps(task),
            ex=86400  # 24 hour expiry
        )
        print(f"✅ Task stored in Redis: annika:tasks:{task['id']}")
        
        # Publish notification
        redis_client.publish(
            "annika:tasks:updates",
            json.dumps({
                "action": "created",
                "task": task,
                "source": "test-agent"
            })
        )
        print("✅ Published notification to annika:tasks:updates")
        
        return True
        
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
        print("   Make sure Redis is running on port 6379")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def monitor_task_updates():
    """Monitor Redis pub/sub for task updates"""
    print("\n📡 Monitoring task updates (press Ctrl+C to stop)...")
    
    try:
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            password='password',
            decode_responses=True
        )
        
        pubsub = redis_client.pubsub()
        pubsub.subscribe("annika:tasks:updates")
        
        print("✅ Subscribed to annika:tasks:updates")
        print("   Waiting for messages...")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                action = data.get('action')
                
                if action == 'created':
                    print(f"🆕 New task: {data['task']['title']}")
                elif action == 'updated':
                    print(f"📝 Task updated: {data['task']['title']}")
                elif action == 'deleted':
                    print(f"🗑️ Task deleted: {data.get('taskId')}")
                elif action == 'task_synced':
                    print(f"✅ Task synced to Planner: {data['task']['title']}")
                    
    except KeyboardInterrupt:
        print("\n👋 Stopped monitoring")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main test function"""
    print("🚀 Planner Agent Task Creation Test")
    print("=" * 50)
    
    # Test HTTP API
    http_success = test_http_api_method()
    
    # Test Redis direct
    redis_success = test_redis_direct_method()
    
    print("\n📊 Test Results:")
    print(f"   HTTP API: {'✅ Passed' if http_success else '❌ Failed'}")
    print(f"   Redis Direct: {'✅ Passed' if redis_success else '❌ Failed'}")
    
    if http_success or redis_success:
        print("\n💡 Tasks have been queued for syncing to Microsoft Planner.")
        print("   They should appear in Planner within 30 seconds.")
        print("\n🔍 Would you like to monitor task updates? (y/n): ", end="")
        
        choice = input().strip().lower()
        if choice == 'y':
            monitor_task_updates()


if __name__ == "__main__":
    main() 