#!/usr/bin/env python3
"""Check active webhook subscriptions."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from graph_subscription_manager import GraphSubscriptionManager

def main():
    mgr = GraphSubscriptionManager()
    subs = mgr.list_active_subscriptions()
    
    print(f"Active subscriptions: {len(subs)}")
    print()
    
    for i, sub in enumerate(subs, 1):
        resource = sub.get("resource", "unknown")
        client_state = sub.get("clientState", "none")
        expires = sub.get("expirationDateTime", "unknown")
        sub_id = sub.get("id", "unknown")
        
        print(f"{i}. Resource: {resource}")
        print(f"   ID: {sub_id}")
        print(f"   Client State: {client_state}")
        print(f"   Expires: {expires}")
        print()

if __name__ == "__main__":
    main() 