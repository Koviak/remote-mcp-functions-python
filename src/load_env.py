"""Load environment variables from .env file into environment"""

import os
from pathlib import Path

# Try to find .env file
possible_paths = [
    Path('.env'),
    Path('../.env'),
    Path('../../.env'),
    Path(r'C:\Users\JoshuaKoviak\OneDrive - Koviak Built\Documents\GitHub\remote-mcp-functions-python\.env')
]

env_file = None
for path in possible_paths:
    if path.exists():
        env_file = path
        print(f"Found .env file at: {path}")
        break

if env_file:
    # Load environment variables
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
                if 'PASSWORD' in key or 'SECRET' in key:
                    print(f"Loaded {key}: {'*' * 10}")
                else:
                    print(f"Loaded {key}: {value[:30]}...")
else:
    print("No .env file found!")
    print("Checked locations:")
    for path in possible_paths:
        print(f"  - {path}") 