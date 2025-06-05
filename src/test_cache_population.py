#!/usr/bin/env python3
"""
Test Cache Population Script

This script:
1. Makes API calls to trigger cache population
2. Verifies data is stored in Redis cache
3. Checks TTL settings
4. Tests cache retrieval endpoints
"""

import json
import time
import requests
import redis
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
API_BASE = "http://localhost:7071/api"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# Test data
AGENT_USER_ID = "5ac3e02f-825f-49f1-a2e2-8fe619020b60"  # Annika's ID
TEST_GROUP_ID = "795b880a-be88-45f9-9a11-d1777169ffb8"  # Engineering Team
TEST_PLAN_ID = "CbfN3rLYAkS0ZutzQP5J9mUAFxxt"  # Default test plan

# Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)


def make_api_call(
    endpoint: str, method: str = "GET", data: Optional[Dict] = None
) -> Optional[Dict]:
    """Make an API call and return response"""
    try:
        url = f"{API_BASE}/{endpoint}"
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return None
            
        if response.status_code in [200, 201]:
            return response.json() if response.text else {}
        else:
            print(f"❌ API call failed: {endpoint} - {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ API error: {endpoint} - {str(e)}")
        return None


def check_redis_cache(key: str) -> Dict[str, Any]:
    """Check if data exists in Redis cache"""
    try:
        data = redis_client.get(key)
        if data:
            ttl = redis_client.ttl(key)
            return {
                "exists": True,
                "data": json.loads(data),
                "ttl": ttl,
                "ttl_hours": round(ttl / 3600, 1) if ttl > 0 else "No expiry"
            }
        return {"exists": False}
    except Exception as e:
        return {"exists": False, "error": str(e)}


def test_user_cache():
    """Test user caching"""
    print("\n" + "="*60)
    print("1️⃣ Testing User Cache")
    print("="*60)
    
    # Clear any existing cache
    cache_key = f"annika:graph:users:{AGENT_USER_ID}"
    redis_client.delete(cache_key)
    
    # Verify cache is empty
    cache_check = check_redis_cache(cache_key)
    print(f"✓ Cache empty before API call: {not cache_check['exists']}")
    
    # Make API call to trigger caching
    print(f"\n📞 Calling GET /api/users/{AGENT_USER_ID}")
    user_data = make_api_call(f"users/{AGENT_USER_ID}")
    
    if user_data:
        print(f"✅ API returned: {user_data.get('displayName', 'Unknown')}")
        
        # Wait a moment for caching
        time.sleep(0.5)
        
        # Check cache
        cache_check = check_redis_cache(cache_key)
        if cache_check["exists"]:
            print("\n✅ USER CACHED!")
            print(f"  - Key: {cache_key}")
            print(f"  - Name: {cache_check['data'].get('displayName')}")
            print(f"  - TTL: {cache_check['ttl_hours']} hours")
            print(f"  - Email: {cache_check['data'].get('mail')}")
            return True
        else:
            print("❌ User NOT cached after API call")
            return False
    else:
        print("❌ API call failed")
        return False


def test_group_cache():
    """Test group caching"""
    print("\n" + "="*60)
    print("2️⃣ Testing Group Cache")
    print("="*60)
    
    cache_key = f"annika:graph:groups:{TEST_GROUP_ID}"
    redis_client.delete(cache_key)
    
    # Get groups first to find a valid one
    print("\n📞 Getting list of groups...")
    groups = make_api_call("groups")
    
    if groups and groups.get("value"):
        # Use first group
        group = groups["value"][0]
        group_id = group["id"]
        cache_key = f"annika:graph:groups:{group_id}"
        
        print(f"✓ Using group: {group.get('displayName')} ({group_id})")
        
        # Clear cache and make specific call
        redis_client.delete(cache_key)
        time.sleep(0.5)
        
        # Check cache after list call
        cache_check = check_redis_cache(cache_key)
        if cache_check["exists"]:
            print("\n✅ GROUP CACHED (from list call)!")
            print(f"  - Key: {cache_key}")
            print(f"  - Name: {cache_check['data'].get('displayName')}")
            print(f"  - TTL: {cache_check['ttl_hours']} hours")
            return True
        else:
            print("❌ Group NOT cached")
            return False
    else:
        print("❌ No groups found")
        return False


def test_plan_cache():
    """Test plan caching"""
    print("\n" + "="*60)
    print("3️⃣ Testing Plan Cache")
    print("="*60)
    
    # Get plans first
    print("\n📞 Getting list of plans...")
    plans = make_api_call("plans")
    
    if plans and plans.get("value"):
        # Use first plan
        plan = plans["value"][0]
        plan_id = plan["id"]
        cache_key = f"annika:graph:plans:{plan_id}"
        
        print(f"✓ Using plan: {plan.get('title')} ({plan_id})")
        
        # Clear cache
        redis_client.delete(cache_key)
        
        # Make specific plan call
        print(f"\n📞 Calling GET /api/plans/{plan_id}")
        plan_data = make_api_call(f"plans/{plan_id}")
        
        if plan_data:
            time.sleep(0.5)
            
            # Check cache
            cache_check = check_redis_cache(cache_key)
            if cache_check["exists"]:
                print("\n✅ PLAN CACHED!")
                print(f"  - Key: {cache_key}")
                print(f"  - Title: {cache_check['data'].get('title')}")
                print(f"  - TTL: {cache_check['ttl_hours']} hours")
                return True
            else:
                print("❌ Plan NOT cached after API call")
                return False
    else:
        print("❌ No plans found")
        return False


def test_task_cache():
    """Test task caching"""
    print("\n" + "="*60)
    print("4️⃣ Testing Task Cache")
    print("="*60)
    
    # Create a test task
    print("\n📞 Creating a test task...")
    current_time = datetime.now().strftime('%H:%M:%S')
    task_data = make_api_call(
        "agent/tasks",
        method="POST",
        data={
            "title": f"Cache Test Task - {current_time}",
            "planId": TEST_PLAN_ID
        }
    )
    
    if task_data and task_data.get("task"):
        task = task_data["task"]
        task_id = task["id"]
        
        # Check both possible cache locations
        cache_key1 = f"annika:tasks:{task_id}"
        cache_key2 = f"annika:graph:tasks:{task_id}"
        
        print(f"✓ Created task: {task['title']}")
        time.sleep(0.5)
        
        # Check primary storage
        cache_check1 = check_redis_cache(cache_key1)
        cache_check2 = check_redis_cache(cache_key2)
        
        if cache_check1["exists"]:
            print("\n✅ TASK STORED (Primary)!")
            print(f"  - Key: {cache_key1}")
            print(f"  - Title: {cache_check1['data'].get('title')}")
            print(f"  - TTL: {cache_check1['ttl_hours']}")
            
            # Verify no expiry
            if cache_check1['ttl'] == -1:
                print("  - ✅ No expiry (persists forever)")
            else:
                print(f"  - ⚠️ Has expiry: {cache_check1['ttl']} seconds")
                
        if cache_check2["exists"]:
            print("\n✅ TASK CACHED (Metadata)!")
            print(f"  - Key: {cache_key2}")
            print(f"  - TTL: {cache_check2['ttl_hours']}")
            
        return cache_check1["exists"] or cache_check2["exists"]
    else:
        print("❌ Failed to create task")
        return False


def test_metadata_endpoint():
    """Test the metadata endpoint for cache retrieval"""
    print("\n" + "="*60)
    print("5️⃣ Testing Metadata Endpoint")
    print("="*60)
    
    # Test user metadata
    print("\n📞 Testing metadata endpoint for user...")
    response = requests.get(
        f"{API_BASE}/metadata?type=user&id={AGENT_USER_ID}",
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ User metadata retrieved: {data.get('displayName')}")
    else:
        print(f"❌ User metadata failed: {response.status_code}")
    
    return response.status_code == 200


def display_cache_statistics():
    """Display overall cache statistics"""
    print("\n" + "="*60)
    print("📊 Cache Statistics")
    print("="*60)
    
    # Count different types of cached items
    patterns = {
        "Users": "annika:graph:users:*",
        "Groups": "annika:graph:groups:*",
        "Plans": "annika:graph:plans:*",
        "Tasks (Graph)": "annika:graph:tasks:*",
        "Tasks (Primary)": "annika:tasks:*"
    }
    
    total = 0
    for name, pattern in patterns.items():
        keys = redis_client.keys(pattern)
        count = len(keys)
        total += count
        if count > 0:
            print(f"  - {name}: {count} items cached")
            
            # Show sample TTLs
            if keys and count <= 3:
                for key in keys[:3]:
                    ttl = redis_client.ttl(key)
                    ttl_display = (
                        f"{round(ttl/3600, 1)}h" if ttl > 0 else "No expiry"
                    )
                    print(f"    • {key}: TTL={ttl_display}")
    
    print(f"\n  Total cached items: {total}")


def main():
    """Run all cache tests"""
    print("🧪 Cache Population Test Suite")
    print("="*60)
    print(f"API: {API_BASE}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check services
    print("\n🔍 Checking services...")
    
    # Check Redis
    try:
        redis_client.ping()
        print("✅ Redis is running")
    except redis.ConnectionError:
        print("❌ Redis is not running!")
        return
    
    # Check API
    api_working = False
    test_endpoints = [
        "/hello",
        "/metadata?type=user&id=test",
        "/users/test",
        "/groups"
    ]
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(f"{API_BASE}{endpoint}", timeout=5)
            if response.status_code in [200, 400, 401, 404]:
                # Any response other than 503 means the API is running
                print(f"✅ Function App is running (tested {endpoint})")
                api_working = True
                break
        except requests.exceptions.RequestException:
            continue
    
    if not api_working:
        print("❌ Function App is not running!")
        print("   Please start it with: func start")
        return
    
    # Run tests
    results = {
        "User Cache": test_user_cache(),
        "Group Cache": test_group_cache(),
        "Plan Cache": test_plan_cache(),
        "Task Cache": test_task_cache(),
        "Metadata Endpoint": test_metadata_endpoint()
    }
    
    # Display statistics
    display_cache_statistics()
    
    # Summary
    print("\n" + "="*60)
    print("🏁 Test Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Cache population is working correctly!")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main() 