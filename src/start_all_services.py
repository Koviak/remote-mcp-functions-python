#!/usr/bin/env python3
"""
Comprehensive startup script for all services.
Starts Function App, sets up webhooks, and runs Planner sync service.
"""
import asyncio
import subprocess
import sys
import logging
import httpx
import os
from pathlib import Path
import signal

# Add this import for token acquisition
from agent_auth_manager import get_agent_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceManager:
    def __init__(self):
        self.func_process = None
        self.sync_process = None
        self.base_dir = Path(__file__).parent
        self.shutdown_in_progress = False
        
    async def wait_for_function_app(self, max_attempts=30):
        """Wait for Function App to be ready."""
        logger.info("⏳ Waiting for Function App to be ready...")
        
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "http://localhost:7071/api/hello"
                    )
                    if response.status_code == 200:
                        logger.info("✅ Function App is ready!")
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(2)
            if attempt % 5 == 0:
                logger.info(f"Still waiting... ({attempt}/{max_attempts})")
        
        return False
    
    async def setup_webhooks(self):
        """Set up MS Graph webhooks."""
        logger.info("📋 Setting up MS Graph webhooks...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Trigger webhook setup via HTTP endpoint
                response = await client.post(
                    "http://localhost:7071/api/graph_webhook",
                    params={"validationToken": "setup"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info("✅ Webhooks setup complete")
                    return True
                else:
                    logger.warning(
                        f"⚠️  Webhook setup returned: {response.status_code}"
                    )
                    
        except Exception as e:
            logger.error(f"❌ Webhook setup failed: {e}")
        
        return False
    
    def start_function_app(self):
        """Start the Azure Function App."""
        logger.info("🚀 Starting Azure Function App...")
        
        # Change to src directory where host.json is located
        os.chdir(self.base_dir)
        
        # Start func host
        if sys.platform == "win32":
            # Use full path to func.cmd on Windows
            func_cmd = r"C:\Users\JoshuaKoviak\AppData\Roaming\npm\func.cmd"
            self.func_process = subprocess.Popen(
                [func_cmd, "start"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            self.func_process = subprocess.Popen(["func", "start"])
        
        logger.info("✅ Function App process started")
    
    def start_sync_service(self):
        """Start the Planner sync service."""
        logger.info("🔄 Starting Planner sync service V2...")
        
        # Start the NEW sync service with initial sync
        if sys.platform == "win32":
            self.sync_process = subprocess.Popen(
                [sys.executable, "planner_sync_service_v4.py"],
                cwd=self.base_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            self.sync_process = subprocess.Popen(
                [sys.executable, "planner_sync_service_v4.py"],
                cwd=self.base_dir
            )
        
        logger.info("✅ Planner sync service V2 started")
    
    async def ensure_token_available(self, max_attempts=10):
        """Ensure authentication token is available before starting sync."""
        logger.info(
            "🔐 Ensuring authentication tokens are available..."
        )
        
        for attempt in range(max_attempts):
            try:
                # Try to get agent token
                token = await asyncio.to_thread(get_agent_token)
                
                if token:
                    logger.info(
                        "✅ Authentication token acquired successfully!"
                    )
                    # Also verify it works with a simple API call
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://graph.microsoft.com/v1.0/me",
                            headers={
                                "Authorization": f"Bearer {token}"
                            },
                            timeout=10
                        )
                        if response.status_code == 200:
                            user_data = response.json()
                            logger.info(
                                f"✅ Token verified for user: "
                                f"{user_data.get('displayName', 'Unknown')}"
                            )
                            return True
                        else:
                            logger.warning(
                                f"Token validation failed: "
                                f"{response.status_code}"
                            )
                else:
                    logger.info(
                        f"Waiting for token... "
                        f"({attempt + 1}/{max_attempts})"
                    )
                    
            except Exception as e:
                logger.debug(
                    f"Token check attempt {attempt + 1} failed: {e}"
                )
            
            # Wait before retry
            await asyncio.sleep(3)
        
        logger.error("❌ Failed to acquire authentication token")
        logger.info("Please check:")
        logger.info(
            "  - AGENT_USER_NAME and AGENT_PASSWORD are set correctly"
        )
        logger.info(
            "  - Azure AD app has 'Allow public client flows' enabled"
        )
        logger.info("  - User has necessary permissions")
        return False
    
    async def start_all(self):
        """Start all services in the correct order."""
        logger.info("🎯 Starting all services...")
        
        # 1. Start Function App
        self.start_function_app()
        
        # 2. Wait for it to be ready
        if not await self.wait_for_function_app():
            logger.error("❌ Function App failed to start")
            return False
        
        # 3. Setup webhooks
        await self.setup_webhooks()
        
        # 4. Wait a bit for token service to be ready
        logger.info("⏳ Waiting for token service to initialize...")
        await asyncio.sleep(5)
        
        # 4.5. NEW: Ensure token is available before starting sync
        if not await self.ensure_token_available():
            logger.error(
                "❌ Cannot start sync service without "
                "authentication token"
            )
            logger.info(
                "Sync service will not be started. "
                "Other services will continue running."
            )
            # Don't fail completely, just skip sync service
            return True
        
        # 5. Start sync service
        self.start_sync_service()
        
        logger.info("✅ All services started successfully!")
        logger.info("📡 Function App: http://localhost:7071")
        logger.info("🔄 Planner sync service: Running")
        logger.info("📨 Webhooks: Configured")
        
        return True
    
    def stop_all(self):
        """Stop all services gracefully."""
        if self.shutdown_in_progress:
            return
            
        self.shutdown_in_progress = True
        logger.info("\n🛑 Stopping all services...")
        
        # Stop sync service first (it's less critical)
        if self.sync_process:
            logger.info("Stopping Planner sync service...")
            try:
                if sys.platform == "win32":
                    # On Windows, send CTRL_C_EVENT to the process group
                    self.sync_process.send_signal(signal.CTRL_C_EVENT)
                else:
                    self.sync_process.terminate()
                
                # Give it time to shut down gracefully
                try:
                    self.sync_process.wait(timeout=5)
                    logger.info(
                        "✅ Planner sync service stopped gracefully"
                    )
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "Sync service didn't stop gracefully, forcing..."
                    )
                    self.sync_process.kill()
                    self.sync_process.wait()
            except Exception as e:
                logger.error(f"Error stopping sync service: {e}")
        
        # Stop Function App
        if self.func_process:
            logger.info("Stopping Azure Function App...")
            try:
                if sys.platform == "win32":
                    # On Windows, send CTRL_C_EVENT to the process group
                    self.func_process.send_signal(signal.CTRL_C_EVENT)
                else:
                    self.func_process.terminate()
                
                # Give it more time as it has more cleanup to do
                try:
                    self.func_process.wait(timeout=10)
                    logger.info("✅ Function App stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "Function App didn't stop gracefully, forcing..."
                    )
                    self.func_process.kill()
                    self.func_process.wait()
            except Exception as e:
                logger.error(f"Error stopping Function App: {e}")
        
        logger.info("✅ All services stopped")


async def main():
    """Main entry point."""
    manager = ServiceManager()
    shutdown_event = asyncio.Event()
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        if not shutdown_event.is_set():
            logger.info("\n⚠️  Shutdown signal received...")
            shutdown_event.set()
    
    # Register signal handlers
    if sys.platform == "win32":
        # Windows signal handling
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGBREAK, signal_handler)
    else:
        # Unix signal handling
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start everything
        success = await manager.start_all()
        
        if success:
            logger.info("\n" + "="*50)
            logger.info("🎉 All services are running!")
            logger.info("Press Ctrl+C to stop all services")
            logger.info("="*50 + "\n")
            
            # Keep running until shutdown signal
            await shutdown_event.wait()
            
        else:
            logger.error("❌ Failed to start all services")
            sys.exit(1)
            
    except KeyboardInterrupt:
        # This might not be reached due to signal handlers, but just in case
        logger.info("\n⚠️  Keyboard interrupt received...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always try to clean up
        logger.info("\n🧹 Cleaning up...")
        manager.stop_all()
        
        # Give a moment for cleanup to complete
        await asyncio.sleep(1)
        
        logger.info("\n👋 Goodbye!")


if __name__ == "__main__":
    # On Windows, ensure proper signal handling for subprocesses
    if sys.platform == "win32":
        # This helps with subprocess signal handling on Windows
        os.environ['PYTHONUNBUFFERED'] = '1'
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle any final keyboard interrupt
        print("\n👋 Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1) 