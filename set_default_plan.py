#!/usr/bin/env python3
"""
Set the default Planner plan ID for sync service.
"""
import redis
import sys

# The plan ID we found
PLAN_ID = "fcoksV9zl0yf4y-UIs589mUAE1_w"
PLAN_TITLE = "Annika_AGI"

try:
    # Connect to Redis
    r = redis.Redis(
        host='localhost',
        port=6379,
        password='password',
        decode_responses=True
    )
    
    # Set the default plan ID
    r.set("annika:config:default_plan_id", PLAN_ID)
    
    print(f"✅ Successfully set default plan to: {PLAN_TITLE}")
    print(f"   ID: {PLAN_ID}")
    print("\nThe sync service will now use this plan.")
    print("\nRestart the services for the change to take effect:")
    print("python src/start_all_services.py")
    
except Exception as e:
    print(f"❌ Error setting plan ID: {e}")
    print("\nAlternatively, add this to your local.settings.json:")
    print(f'"DEFAULT_PLANNER_PLAN_ID": "{PLAN_ID}"')
    sys.exit(1) 