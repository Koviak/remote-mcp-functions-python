"""
Startup script for local development services.
Automatically starts ngrok, sets up webhooks, and initializes monitoring.
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

# Import our managers
from graph_subscription_manager import GraphSubscriptionManager
from agent_auth_manager import get_agent_token
from azure.identity import ClientSecretCredential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalServicesManager:
    """Manages startup of all local services for development."""
    
    def __init__(self):
        self.ngrok_process = None
        self.webhook_url = None
        self.settings = self.load_settings()
        self.subscription_manager = None
        
    def load_settings(self) -> dict:
        """Load settings from local.settings.json."""
        settings_path = Path(__file__).parent / "local.settings.json"
        if settings_path.exists():
            with open(settings_path) as f:
                data = json.load(f)
                values = data.get("Values", {})
                # Set environment variables from settings
                for key, value in values.items():
                    if value and key not in os.environ:
                        os.environ[key] = value
                return values
        return {}
    
    async def start_ngrok(self) -> bool:
        """Start ngrok in the background."""
        try:
            # Check if ngrok is already running
            existing_url = await self.find_ngrok_tunnel()
            if existing_url:
                logger.info(f"✅ ngrok already running: {existing_url}")
                self.webhook_url = f"{existing_url}/api/graph_webhook"
                return True
            
            # Start ngrok
            logger.info("🚀 Starting ngrok...")
            
            # Check for custom domain
            ngrok_domain = self.settings.get("NGROK_DOMAIN")
            if ngrok_domain:
                cmd = ["ngrok", "http", "--domain", ngrok_domain, "7071"]
            else:
                cmd = ["ngrok", "http", "7071"]
            
            # Start ngrok process
            if sys.platform == "win32":
                self.ngrok_process = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                self.ngrok_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # Wait for ngrok to start
            for i in range(10):
                await asyncio.sleep(2)
                url = await self.find_ngrok_tunnel()
                if url:
                    logger.info(f"✅ ngrok started: {url}")
                    self.webhook_url = f"{url}/api/graph_webhook"
                    # Update environment variable
                    os.environ["GRAPH_WEBHOOK_URL"] = self.webhook_url
                    return True
            
            logger.error("❌ ngrok failed to start")
            return False
            
        except Exception as e:
            logger.error(f"Error starting ngrok: {e}")
            return False
    
    async def find_ngrok_tunnel(self) -> Optional[str]:
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
    
    async def setup_webhooks(self) -> bool:
        """Set up Microsoft Graph webhooks."""
        try:
            logger.info("📋 Setting up webhook subscriptions...")
            
            # Verify webhook URL is set
            webhook_url = os.environ.get("GRAPH_WEBHOOK_URL")
            if not self.webhook_url and not webhook_url:
                logger.error("❌ No webhook URL available")
                return False
            
            # Create subscription manager
            self.subscription_manager = GraphSubscriptionManager()
            
            # List existing subscriptions
            existing = await asyncio.to_thread(
                self.subscription_manager.list_active_subscriptions
            )
            logger.info(f"Found {len(existing)} existing subscriptions")
            
            # Create user and event subscriptions
            created = 0
            
            user_sub_id = await asyncio.to_thread(
                self.subscription_manager.create_user_subscription
            )
            if user_sub_id:
                logger.info("✅ Created user message subscription")
                created += 1
            
            event_sub_id = await asyncio.to_thread(
                self.subscription_manager.create_event_subscription
            )
            if event_sub_id:
                logger.info("✅ Created calendar event subscription")
                created += 1
            
            # Set up group subscriptions
            logger.info("👥 Setting up group subscriptions...")
            await asyncio.to_thread(
                self.subscription_manager.setup_annika_subscriptions
            )
            
            logger.info(f"✅ Webhook setup complete ({created}+ subscriptions)")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up webhooks: {e}")
            return False
    
    async def monitor_subscriptions(self):
        """Monitor and renew subscriptions periodically."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                if self.subscription_manager:
                    logger.info("🔄 Checking webhook subscriptions...")
                    
                    # Just renew all subscriptions periodically
                    # The manager will handle checking if they need renewal
                    result = await asyncio.to_thread(
                        self.subscription_manager.renew_all_subscriptions
                    )
                    logger.info(
                        f"Renewed {result.get('renewed', 0)} subscriptions"
                    )
                            
            except Exception as e:
                logger.error(f"Error in subscription monitor: {e}")
                await asyncio.sleep(60)
    
    async def verify_authentication(self) -> bool:
        """Verify authentication is working."""
        try:
            # Try to get app-only token
            tenant_id = self.settings.get("AZURE_TENANT_ID")
            client_id = self.settings.get("AZURE_CLIENT_ID")
            client_secret = self.settings.get("AZURE_CLIENT_SECRET")
            
            if not all([tenant_id, client_id, client_secret]):
                logger.error("❌ Missing Azure AD credentials")
                return False
            
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            scope = "https://graph.microsoft.com/.default"
            token = credential.get_token(scope)
            if token:
                logger.info("✅ App-only authentication verified")
            
            # Try to get delegated token
            agent_token = await asyncio.to_thread(get_agent_token)
            if agent_token:
                logger.info("✅ Agent authentication verified")
            else:
                logger.warning("⚠️  Agent authentication not available")
            
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    async def start_all_services(self):
        """Start all local development services."""
        logger.info("🚀 Starting local development services...")
        
        # Verify settings
        required = [
            "AZURE_TENANT_ID",
            "AZURE_CLIENT_ID", 
            "AZURE_CLIENT_SECRET",
            "AGENT_USER_NAME",
            "AGENT_PASSWORD"
        ]
        missing = [key for key in required if not self.settings.get(key)]
        if missing:
            logger.error(f"❌ Missing settings: {', '.join(missing)}")
            logger.info("Please update local.settings.json")
            return False
        
        # Verify authentication
        if not await self.verify_authentication():
            return False
        
        # Start ngrok
        if not await self.start_ngrok():
            logger.error("Failed to start ngrok")
            return False
        
        # Set up webhooks
        if not await self.setup_webhooks():
            logger.warning("Webhook setup failed - continuing anyway")
        
        # Start subscription monitoring
        asyncio.create_task(self.monitor_subscriptions())
        
        logger.info("✅ All services started successfully!")
        logger.info(f"📡 Webhook URL: {self.webhook_url}")
        logger.info("🔔 Ready to receive notifications")
        
        return True
    
    def stop(self):
        """Stop all services."""
        if self.ngrok_process:
            logger.info("Stopping ngrok...")
            self.ngrok_process.terminate()
            self.ngrok_process = None


# Global manager instance
_manager: Optional[LocalServicesManager] = None


async def start_local_services():
    """Start all local development services."""
    global _manager
    
    if _manager is None:
        _manager = LocalServicesManager()
        success = await _manager.start_all_services()
        if not success:
            logger.error("Failed to start some services")
        return success
    return True


def stop_local_services():
    """Stop all local development services."""
    global _manager
    
    if _manager:
        _manager.stop()
        _manager = None


# For testing
if __name__ == "__main__":
    async def test():
        await start_local_services()
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            stop_local_services()
    
    asyncio.run(test()) 