"""
Helper script to sync .env file values to local.settings.json
"""

import json
from pathlib import Path


def find_env_file():
    """Find .env file in current or parent directories"""
    current = Path.cwd()
    
    # Check current directory
    if (current / '.env').exists():
        return current / '.env'
    
    # Check parent directory
    if (current.parent / '.env').exists():
        return current.parent / '.env'
    
    # Check one more level up
    if (current.parent.parent / '.env').exists():
        return current.parent.parent / '.env'
    
    return None


def read_env_file(env_path):
    """Read and parse .env file"""
    env_vars = {}
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_vars[key] = value
    
    return env_vars


def update_local_settings(env_vars):
    """Update local.settings.json with environment variables"""
    settings_path = Path('local.settings.json')
    
    # Read existing settings
    with open(settings_path, 'r') as f:
        settings = json.load(f)
    
    # Update with env vars
    azure_vars = {
        'AZURE_CLIENT_ID': env_vars.get('AZURE_CLIENT_ID', ''),
        'AZURE_CLIENT_SECRET': env_vars.get('AZURE_CLIENT_SECRET', ''),
        'AZURE_TENANT_ID': env_vars.get('AZURE_TENANT_ID', ''),
        'DOWNSTREAM_API_SCOPE': env_vars.get(
            'DOWNSTREAM_API_SCOPE', 
            'https://graph.microsoft.com/.default'),
        'AGENT_USER_NAME': env_vars.get('AGENT_USER_NAME', ''),
        'AGENT_PASSWORD': env_vars.get('AGENT_PASSWORD', ''),
        'AGENT_CERTIFICATE_PATH': env_vars.get('AGENT_CERTIFICATE_PATH', ''),
        'REDIS_URL': env_vars.get('REDIS_URL', '')
    }
    
    # Update settings
    for key, value in azure_vars.items():
        if value:
            settings['Values'][key] = value
            print(f"✓ Updated {key}")
        else:
            print(f"⚠️  No value found for {key}")
    
    # Write back
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    
    print(f"\n✓ Updated {settings_path}")


def main():
    """Main function"""
    print("Syncing .env to local.settings.json")
    print("=" * 40)
    
    # Find .env file
    env_path = find_env_file()
    if not env_path:
        print("❌ No .env file found")
        print("Please create a .env file with your Azure AD settings:")
        print("  AZURE_CLIENT_ID=your-client-id")
        print("  AZURE_CLIENT_SECRET=your-client-secret")
        print("  AZURE_TENANT_ID=your-tenant-id")
        print("  DOWNSTREAM_API_SCOPE=https://graph.microsoft.com/.default")
        print("\nFor autonomous agent authentication:")
        print("  AGENT_USER_NAME=agent@yourdomain.com")
        print("  AGENT_PASSWORD=agent-password")
        return
    
    print(f"✓ Found .env file: {env_path}")
    
    # Read env vars
    env_vars = read_env_file(env_path)
    print(f"✓ Read {len(env_vars)} environment variables")
    
    # Update local.settings.json
    update_local_settings(env_vars)
    
    print("\nYou can now run 'func start' to test the function app")


if __name__ == "__main__":
    main() 