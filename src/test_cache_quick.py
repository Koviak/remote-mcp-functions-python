#!/usr/bin/env python3
"""Quick test to check if caching is working"""

import requests
import redis
import json

# Configuration
API_BASE = "http://localhost:7071/api"
TEST_USER_ID = "5ac3e02f-825f-49f1-a2e2-8fe619020b60"

print("🧪 Quick Cache Test")
print("==================")

# 1. Test API endpoint (this should populate cache)
print("\n1. Testing user API endpoint...")
try:
    response = requests.get(f"{API_BASE}/users/{TEST_USER_ID}", timeout=5)
    if response.status_code == 200:
        user_data = response.json()
        print(f"✅ API call successful: {user_data.get('displayName', 'Unknown')}")
    else:
        print(f"❌ API failed: {response.status_code}")
except Exception as e:
    print(f"❌ API error: {e}")

# 2. Check Redis directly
print("\n2. Checking Redis cache...")
try:
    client = redis.Redis(host='localhost', port=6379, password='password', decode_responses=True)
    client.ping()
    print("✅ Connected to Redis")
    
    # Check for cached user
    user_key = f"annika:graph:users:{TEST_USER_ID}"
    cached_data = client.get(user_key)
    
    if cached_data:
        cached_user = json.loads(cached_data)
        print(f"✅ Found cached user: {cached_user.get('displayName', 'Unknown')}")
        
        # Check TTL
        ttl = client.ttl(user_key)
        if ttl > 0:
            hours = ttl / 3600
            print(f"⏰ TTL: {hours:.1f} hours remaining")
        else:
            print("⏰ No TTL (persistent)")
    else:
        print("❌ No cached data found")
        
except Exception as e:
    print(f"❌ Redis error: {e}")

# 3. Test cache endpoint
print("\n3. Testing cache metadata endpoint...")
try:
    response = requests.get(f"{API_BASE}/metadata?type=user&id={TEST_USER_ID}", timeout=5)
    if response.status_code == 200:
        cache_data = response.json()
        print(f"✅ Cache endpoint works: {cache_data.get('displayName', 'Unknown')}")
    elif response.status_code == 404:
        print("❌ Cache miss (404)")
    else:
        print(f"❌ Cache endpoint failed: {response.status_code}")
except Exception as e:
    print(f"❌ Cache endpoint error: {e}")

print("\n✅ Test complete!")
print("\nIf you see cached data above, the cache is working!")
print("If not, check that:")
print("- Function App is running (func start)")
print("- Redis is running (docker ps)")
print("- GraphMetadataManager is integrated in http_endpoints.py") 