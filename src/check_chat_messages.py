#!/usr/bin/env python3
"""Check Teams chat messages stored in Redis."""

import redis
import json
from datetime import datetime

def main():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, password='password', decode_responses=True)
    
    # Get chat messages
    messages = r.lrange('annika:teams:chat_messages:history', 0, 9)
    
    print(f"Found {len(messages)} Teams chat messages:")
    print()
    
    for i, msg_json in enumerate(messages, 1):
        try:
            msg = json.loads(msg_json)
            timestamp = msg.get("timestamp", "unknown")
            change_type = msg.get("change_type", "unknown")
            chat_id = msg.get("chat_id", "unknown")
            message_id = msg.get("message_id", "unknown")
            msg_type = msg.get("type", "unknown")
            
            # Parse timestamp for better display
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = timestamp
            
            print(f"{i}. {time_str} - {change_type} {msg_type}")
            print(f"   Chat: {chat_id[:12]}...")
            print(f"   Message: {message_id[:12]}...")
            print()
            
        except json.JSONDecodeError:
            print(f"{i}. Invalid JSON: {msg_json[:50]}...")
            print()

if __name__ == "__main__":
    main() 