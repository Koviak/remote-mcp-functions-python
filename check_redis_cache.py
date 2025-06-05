#!/usr/bin/env python3
"""Quick script to check Redis cache contents"""

import redis
import json

# Connect to Redis
client = redis.Redis(host='localhost', port=6379, password='password', decode_responses=True)

print("🔍 Checking Redis Cache Contents")
print("="*50)

# Get all annika keys
all_keys = client.keys("annika:*")
print(f"\nTotal annika keys: {len(all_keys)}")

# Categorize keys
graph_keys = [k for k in all_keys if "graph" in k]
task_keys = [k for k in all_keys if "tasks" in k and "mapping" not in k]
mapping_keys = [k for k in all_keys if "mapping" in k]

print(f"\n📊 Cache Statistics:")
print(f"  - Graph metadata keys: {len(graph_keys)}")
print(f"  - Task keys: {len(task_keys)}")
print(f"  - Mapping keys: {len(mapping_keys)}")

# Show graph cache details
if graph_keys:
    print(f"\n🔸 Graph Cache Keys:")
    for key in graph_keys[:5]:  # Show first 5
        ttl = client.ttl(key)
        ttl_hours = ttl / 3600 if ttl > 0 else "No expiry"
        print(f"  - {key} (TTL: {ttl_hours:.1f} hours)" if isinstance(ttl_hours, float) else f"  - {key} ({ttl_hours})")
        
        # Get sample data
        data = client.get(key)
        if data:
            try:
                obj = json.loads(data)
                if 'displayName' in obj:
                    print(f"    Name: {obj['displayName']}")
                elif 'title' in obj:
                    print(f"    Title: {obj['title']}")
            except:
                pass

# Show task details
if task_keys:
    print(f"\n🔸 Task Keys:")
    for key in task_keys[:5]:  # Show first 5
        ttl = client.ttl(key)
        ttl_status = "No expiry ✓" if ttl == -1 else f"{ttl/3600:.1f} hours"
        print(f"  - {key} (TTL: {ttl_status})")
        
        data = client.get(key)
        if data:
            try:
                task = json.loads(data)
                print(f"    Title: {task.get('title', 'Unknown')}")
                print(f"    Created by: {task.get('createdBy', 'Unknown')}")
            except:
                pass

print("\n✅ Cache check complete!") 