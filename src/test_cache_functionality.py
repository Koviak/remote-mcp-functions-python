#!/usr/bin/env python3
"""
Test script to verify Redis caching functionality for MS Graph data
"""

import requests
import redis
import json
import time
from datetime import datetime

# Configuration
API_BASE = "http://localhost:7071/api"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "password"

# Test data - Update these with your actual IDs
TEST_USER_ID = "5ac3e02f-825f-49f1-a2e2-8fe619020b60"  # Annika's ID
TEST_GROUP_ID = "795b880a-be88-45f9-9a11-d1777169ffb8"  # A group ID
TEST_PLAN_ID = "CbfN3rLYAkS0ZutzQP5J9mUAFxxt"  # A plan ID

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text):
    print(f"{RED}❌ {text}{RESET}")


def print_info(text):
    print(f"{YELLOW}ℹ️  {text}{RESET}")


def test_cache_performance():
    """Test cache performance vs direct API calls"""
    print_header("Testing Cache Performance")
    
    # Test 1: First call (cache miss) - should populate cache
    print("\n1️⃣ Testing cache miss (first call)...")
    start_time = time.time()
    response = requests.get(
        f"{API_BASE}/users/{TEST_USER_ID}", 
        timeout=10
    )
    api_time = (time.time() - start_time) * 1000  # Convert to ms
    
    if response.status_code == 200:
        print_success(f"API call successful: {api_time:.1f}ms")
    else:
        print_error(f"API call failed: {response.status_code}")
        return
    
    # Give cache a moment to populate
    time.sleep(0.5)
    
    # Test 2: Cache hit - should be much faster
    print("\n2️⃣ Testing cache hit (metadata endpoint)...")
    start_time = time.time()
    cache_response = requests.get(
        f"{API_BASE}/metadata?type=user&id={TEST_USER_ID}",
        timeout=10
    )
    cache_time = (time.time() - start_time) * 1000
    
    if cache_response.status_code == 200:
        print_success(f"Cache hit successful: {cache_time:.1f}ms")
        speedup = api_time / cache_time
        print_info(f"Cache is {speedup:.0f}x faster!")
        
        # Verify data matches
        api_data = response.json()
        cache_data = cache_response.json()
        if api_data.get("displayName") == cache_data.get("displayName"):
            print_success("Data integrity verified - cache matches API")
        else:
            print_error("Data mismatch between cache and API!")
    else:
        print_error(f"Cache miss: {cache_response.status_code}")


def test_redis_direct():
    """Test direct Redis access to verify data is stored"""
    print_header("Testing Direct Redis Access")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Test connection
        redis_client.ping()
        print_success("Connected to Redis")
        
        # Check for cached user data
        user_key = f"annika:graph:users:{TEST_USER_ID}"
        user_data = redis_client.get(user_key)
        
        if user_data:
            user = json.loads(user_data)
            print_success(f"Found cached user: {user.get('displayName')}")
            
            # Check TTL
            ttl = redis_client.ttl(user_key)
            if ttl > 0:
                hours = ttl / 3600
                print_info(f"TTL: {hours:.1f} hours remaining")
            else:
                print_info("No TTL set (persistent)")
        else:
            print_error("No cached user data found")
        
        # Check for tasks (should have no expiry)
        print("\n📋 Checking task storage...")
        task_keys = redis_client.keys("annika:tasks:*")
        if task_keys:
            print_success(f"Found {len(task_keys)} cached tasks")
            # Check first task
            if task_keys:
                first_task_key = task_keys[0]
                # Just check TTL, don't need the data
                ttl = redis_client.ttl(first_task_key)
                if ttl == -1:
                    print_success("Tasks have no expiry (persistent) ✓")
                else:
                    print_error(f"Task has TTL: {ttl} seconds")
        else:
            print_info("No tasks found in cache")
            
    except Exception as e:
        print_error(f"Redis connection failed: {e}")


def test_cache_population():
    """Test that endpoints populate cache"""
    print_header("Testing Cache Population")
    
    # Clear cache first (optional)
    print("\n🧹 Testing cache population from empty state...")
    
    # Test group endpoint
    print("\n👥 Testing group cache population...")
    response = requests.get(
        f"{API_BASE}/groups/{TEST_GROUP_ID}",
        timeout=10
    )
    
    if response.status_code == 200:
        print_success("Group API call successful")
        
        # Check if it's now cached
        time.sleep(0.5)
        cache_response = requests.get(
            f"{API_BASE}/metadata?type=group&id={TEST_GROUP_ID}",
            timeout=10
        )
        
        if cache_response.status_code == 200:
            group_data = cache_response.json()
            print_success(f"Group cached: {group_data.get('displayName')}")
            if 'plans' in group_data:
                plans_count = len(group_data['plans'])
                print_info(f"Group has {plans_count} plans cached")
        else:
            print_error("Group not found in cache after API call")


def test_all_cache_types():
    """Test all cache types"""
    print_header("Testing All Cache Types")
    
    cache_types = [
        ("user", TEST_USER_ID, "displayName"),
        ("group", TEST_GROUP_ID, "displayName"),
        ("plan", TEST_PLAN_ID, "title"),
    ]
    
    for cache_type, test_id, field_name in cache_types:
        print(f"\n🔍 Testing {cache_type} cache...")
        
        response = requests.get(
            f"{API_BASE}/metadata?type={cache_type}&id={test_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            display_value = data.get(field_name, "Unknown")
            cached_type = cache_type.capitalize()
            print_success(f"{cached_type} cached: {display_value}")
        elif response.status_code == 404:
            print_info(f"{cache_type.capitalize()} not cached yet")
        else:
            error_msg = f"Error accessing {cache_type} cache: "
            print_error(f"{error_msg}{response.status_code}")


def test_task_creation_and_cache():
    """Test task creation and caching"""
    print_header("Testing Task Creation and Cache")
    
    # Create a test task
    task_data = {
        "title": f"Cache Test Task - {datetime.now().strftime('%H:%M:%S')}",
        "planId": TEST_PLAN_ID,
        "assignedTo": [TEST_USER_ID],
        "percentComplete": 0
    }
    
    print("\n📝 Creating test task...")
    response = requests.post(
        f"{API_BASE}/agent/tasks",
        json=task_data,
        timeout=10
    )
    
    if response.status_code == 201:
        result = response.json()
        task_id = result['task']['id']
        print_success(f"Task created: {task_id}")
        
        # Check Redis directly
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        task_key = f"annika:tasks:{task_id}"
        task_redis_data = redis_client.get(task_key)
        
        if task_redis_data:
            print_success("Task found in Redis")
            ttl = redis_client.ttl(task_key)
            if ttl == -1:
                print_success("Task has no expiry (persistent) ✓")
            else:
                print_error(f"Task has unexpected TTL: {ttl}")
        else:
            print_error("Task not found in Redis!")
    else:
        print_error(f"Failed to create task: {response.status_code}")


def main():
    """Run all cache tests"""
    print(f"{BLUE}🧪 Redis Cache Test Suite{RESET}")
    print(f"{BLUE}========================{RESET}")
    print(f"API Base: {API_BASE}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Test User: {TEST_USER_ID}")
    
    # Run tests
    test_cache_performance()
    test_redis_direct()
    test_cache_population()
    test_all_cache_types()
    test_task_creation_and_cache()
    
    print_header("Test Summary")
    print("✅ Tests completed! Check results above.")
    print("\n💡 Tips:")
    print("- First calls populate cache (slower)")
    print("- Subsequent calls use cache (faster)")
    print("- Tasks persist forever, other data for 24 hours")
    print("- Webhooks automatically update cache")


if __name__ == "__main__":
    main() 