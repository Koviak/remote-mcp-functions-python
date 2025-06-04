"""Update local.settings.json with environment variables"""

import os
import json
from pathlib import Path

# First load environment variables from .env
exec(open('load_env.py').read())

# Now update local.settings.json
settings_path = Path('local.settings.json')

with open(settings_path, 'r') as f:
    settings = json.load(f)

# Update Values section
updates = {
    'AZURE_CLIENT_ID': os.getenv('AZURE_CLIENT_ID', ''),
    'AZURE_CLIENT_SECRET': os.getenv('AZURE_CLIENT_SECRET', ''),
    'AZURE_TENANT_ID': os.getenv('AZURE_TENANT_ID', ''),
    'DOWNSTREAM_API_SCOPE': os.getenv('DOWNSTREAM_API_SCOPE', 'https://graph.microsoft.com/.default'),
    'AGENT_USER_NAME': os.getenv('AGENT_USER_NAME', ''),
    'AGENT_PASSWORD': os.getenv('AGENT_PASSWORD', ''),
    'REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379')
}

print("\nUpdating local.settings.json:")
for key, value in updates.items():
    if value:
        settings['Values'][key] = value
        if 'PASSWORD' in key or 'SECRET' in key:
            print(f"  ✓ {key}: {'*' * 10}")
        else:
            print(f"  ✓ {key}: {value[:30]}...")

# Write back
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print(f"\n✓ Successfully updated {settings_path}") 