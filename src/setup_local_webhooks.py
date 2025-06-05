"""Setup Microsoft Graph webhooks for local development."""
import json
import logging
import os
from pathlib import Path
import asyncio
from typing import Optional

import httpx

# Import our managers
from graph_subscription_manager import GraphSubscriptionManager
from agent_auth_manager import get_agent_token
from azure.identity import ClientSecretCredential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_settings() -> dict:
    """Load settings from local.settings.json."""
    settings_path = Path(__file__).parent / "local.settings.json"
    if settings_path.exists():
        with open(settings_path) as f:
            data = json.load(f)
            return data.get("Values", {})
    return {}


async def check_function_app() -> bool:
    """Check if Function App is running."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:7071/api/metadata")
            return resp.status_code in (200, 401, 404)
    except Exception:
        return False


async def find_ngrok_tunnel() -> Optional[str]:
    """Find ngrok tunnel URL."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:4040/api/tunnels")
            data = resp.json()
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
    except Exception:
        pass
    return None


async def test_webhook_endpoint(webhook_url: str) -> bool:
    """Test webhook endpoint is accessible."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url,
                json={"test": "ping"},
                headers={"Content-Type": "application/json"},
            )
            return resp.status_code in (200, 202, 401)
    except Exception:
        return False


def get_app_only_token(settings: dict) -> Optional[str]:
    """Get app-only access token"""
    tenant_id = settings.get("AZURE_TENANT_ID")
    client_id = settings.get("AZURE_CLIENT_ID")
    client_secret = settings.get("AZURE_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        return None
    
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    scope = "https://graph.microsoft.com/.default"
    access_token = credential.get_token(scope)
    return access_token.token


async def main():
    """Set up webhooks for local development."""
    logger.info("🚀 Microsoft Graph Webhook Setup for Local Development")

    # Load settings from local.settings.json
    settings = load_settings()

    # Check Function App
    if not await check_function_app():
        logger.warning("⚠️  Function App not detected on port 7071")
        logger.info("Start it with: func start")
    else:
        logger.info("✅ Function App is running")

    # Get webhook URL
    webhook_url = settings.get("GRAPH_WEBHOOK_URL")
    if not webhook_url:
        # Try to find ngrok
        ngrok_url = await find_ngrok_tunnel()
        if ngrok_url:
            webhook_url = f"{ngrok_url}/api/graph_webhook"
            logger.info(f"✅ ngrok tunnel found: {ngrok_url}")
        else:
            # Check for custom domain in settings
            ngrok_domain = settings.get("NGROK_DOMAIN")
            if ngrok_domain:
                webhook_url = f"https://{ngrok_domain}/api/graph_webhook"
                logger.info(f"✅ Using custom domain: {ngrok_domain}")

    if not webhook_url:
        logger.error("❌ No webhook URL found")
        logger.info("Start ngrok with: ngrok http 7071")
        return

    # Check required settings
    required = [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AGENT_USER_NAME",
        "AGENT_PASSWORD",
    ]
    missing = [key for key in required if not settings.get(key)]
    if missing:
        logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
        logger.info("Set these in your local.settings.json")
        return

    # Test webhook endpoint
    logger.info(f"📡 Testing webhook endpoint: {webhook_url}")
    if not await test_webhook_endpoint(webhook_url):
        logger.warning("⚠️  Webhook endpoint not accessible")
        logger.info("Make sure ngrok is forwarding to port 7071")

    # Get tokens
    logger.info("🔑 Acquiring tokens...")
    try:
        # Set environment variables for the subscription manager
        os.environ["AZURE_TENANT_ID"] = settings["AZURE_TENANT_ID"]
        os.environ["AZURE_CLIENT_ID"] = settings["AZURE_CLIENT_ID"]
        os.environ["AZURE_CLIENT_SECRET"] = settings["AZURE_CLIENT_SECRET"]
        os.environ["AGENT_USER_NAME"] = settings["AGENT_USER_NAME"]
        os.environ["AGENT_PASSWORD"] = settings["AGENT_PASSWORD"]
        os.environ["GRAPH_WEBHOOK_URL"] = webhook_url
        os.environ["GRAPH_WEBHOOK_CLIENT_STATE"] = settings.get(
            "GRAPH_WEBHOOK_CLIENT_STATE", "annika-secret"
        )
        
        # Get app-only token for webhook subscriptions
        app_token = get_app_only_token(settings)
        if not app_token:
            logger.error("❌ Failed to get app-only token")
            return
            
        # Get delegated token to verify agent credentials
        user_token = await asyncio.to_thread(get_agent_token)
        if user_token:
            logger.info("✅ Agent token acquired")
        else:
            logger.warning("⚠️  Could not acquire agent token")
            
        logger.info("✅ Tokens acquired")
    except Exception as e:
        logger.error(f"❌ Failed to acquire tokens: {e}")
        return

    # Create subscription manager
    manager = GraphSubscriptionManager()

    # List current subscriptions
    logger.info("📋 Checking existing subscriptions...")
    existing = await asyncio.to_thread(manager.list_active_subscriptions)
    if existing:
        logger.info(f"Found {len(existing)} existing subscriptions")
        for sub in existing[:5]:  # Show first 5
            logger.info(f"  - {sub['resource']} ({sub['id'][:8]}...)")

    # Create new subscriptions
    logger.info("\n📋 Creating webhook subscriptions...")
    
    # User and event subscriptions
    created = 0
    
    user_sub_id = await asyncio.to_thread(manager.create_user_subscription)
    if user_sub_id:
        logger.info("✅ Created user message subscription")
        created += 1
    
    event_sub_id = await asyncio.to_thread(manager.create_event_subscription)
    if event_sub_id:
        logger.info("✅ Created calendar event subscription")
        created += 1
    
    # Group subscriptions (this will get groups automatically)
    logger.info("\n👥 Setting up group subscriptions...")
    await asyncio.to_thread(manager.setup_annika_subscriptions)
    
    logger.info("\n📊 Summary:")
    logger.info(f"  - Webhook URL: {webhook_url}")
    logger.info(f"  - New subscriptions created: {created}+")
    client_state = settings.get('GRAPH_WEBHOOK_CLIENT_STATE', 'annika-secret')
    logger.info(f"  - Client state: {client_state}")

    if created > 0:
        logger.info("\n🎉 Webhook setup complete!")
        logger.info("Notifications will be sent to your Function App")
        logger.info("\n💡 Next steps:")
        logger.info("1. Send an email to the agent user")
        logger.info("2. Create a calendar event")
        logger.info("3. Update a group the agent is member of")
        logger.info("4. Watch the Function App logs for notifications")
    else:
        logger.error("\n❌ No subscriptions created")
        logger.info("Check your permissions and network connectivity")

    logger.info("\n✨ Done!")


if __name__ == "__main__":
    asyncio.run(main()) 