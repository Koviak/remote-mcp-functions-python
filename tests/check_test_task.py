"""Quick check for test task mapping."""
import asyncio
import redis.asyncio as redis

async def check():
    r = redis.Redis(host='localhost', port=6379, password='password', decode_responses=True)
    result = await r.get('annika:planner:id_map:Task-SUBTEST-585936')
    await r.aclose()
    if result:
        print(f"✅ Task synced! Planner ID: {result}")
    else:
        print("⏳ Task not yet synced or mapping not found")

asyncio.run(check())



