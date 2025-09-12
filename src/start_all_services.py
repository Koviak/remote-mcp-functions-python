#!/usr/bin/env python3
"""
Comprehensive startup script for all services.
Starts ngrok, Function App, sets up webhooks, and runs Planner sync service.
"""
import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

# Load environment variables early so auth has credentials
import load_env  # noqa: F401  # side-effect: loads .env

# Add this import for token acquisition
from agent_auth_manager import get_agent_token
from chat_subscription_manager import (
    chat_subscription_manager,
    initialize_chat_subscription_manager,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceManager:
    def __init__(self):
        self.func_process = None
        self.ngrok_process = None
        self.sync_process = None
        self.base_dir = Path(__file__).parent
        self.shutdown_in_progress = False
        self.background_tasks = []  # Track background async tasks
        self.sync_service = None  # Track the sync service instance
        self.webhook_url = None
        self.chat_subscription_manager = chat_subscription_manager
        
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
    
    async def start_ngrok(self) -> bool:
        """Start ngrok in the background."""
        try:
            # Check if ngrok is already running
            existing_url = await self.find_ngrok_tunnel()
            if existing_url:
                logger.info(f"✅ ngrok already running: {existing_url}")
                self.webhook_url = f"{existing_url}/api/graph_webhook"
                # Update environment variable
                os.environ["GRAPH_WEBHOOK_URL"] = self.webhook_url
                return True
            
            # Start ngrok
            logger.info("🚀 Starting ngrok...")
            
            # Use the agency-swarm domain
            cmd = [
                "ngrok", "http", "--domain", "agency-swarm.ngrok.app", "7071"
            ]
            
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
            for i in range(15):  # Give it more time
                await asyncio.sleep(2)
                url = await self.find_ngrok_tunnel()
                if url:
                    logger.info(f"✅ ngrok started: {url}")
                    self.webhook_url = f"{url}/api/graph_webhook"
                    # Update environment variable
                    os.environ["GRAPH_WEBHOOK_URL"] = self.webhook_url
                    return True
                
                if i % 5 == 0:
                    logger.info(f"Still waiting for ngrok... ({i}/15)")
            
            logger.error("❌ ngrok failed to start")
            return False
            
        except Exception as e:
            logger.error(f"Error starting ngrok: {e}")
            return False
        
    async def wait_for_function_app(self, max_attempts=30):
        """Wait for Function App to be ready."""
        logger.info("⏳ Waiting for Function App to be ready...")

        # Prefer ultra-light readiness endpoint; fallback to /hello
        readiness_urls = [
            "http://localhost:7071/api/health/ready",
            "http://localhost:7071/api/hello",
        ]

        base_delay = 0.5
        for attempt in range(1, max_attempts + 1):
            for url in readiness_urls:
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        response = await client.get(url)
                        if 200 <= response.status_code < 300:
                            logger.info("✅ Function App is ready!")
                            return True
                except Exception as exc:
                    # Quietly retry with backoff; log occasionally
                    if attempt % 5 == 0:
                        logger.debug(
                            "Readiness probe failed (attempt %s) on %s: %s",
                            attempt,
                            url,
                            exc,
                        )

            # Exponential backoff with jitter
            delay = min(5.0, base_delay * (2 ** (attempt - 1)))
            delay += 0.1 * (attempt % 3)  # cheap jitter
            await asyncio.sleep(delay)
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
        logger.info("🔄 Starting Planner sync service V5...")
        
        # Initialize webhook handler first
        from webhook_handler import initialize_webhook_handler
        asyncio.create_task(initialize_webhook_handler())
        
        # Start V5 sync service
        from planner_sync_service_v5 import WebhookDrivenPlannerSync
        self.sync_service = WebhookDrivenPlannerSync()
        
        # Start sync service in background
        sync_task = asyncio.create_task(self.sync_service.start())
        self.background_tasks.append(sync_task)
        
        logger.info("✅ Planner sync service V5 started")
    
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
        
        # 1. Start ngrok first
        if not await self.start_ngrok():
            logger.error("❌ ngrok failed to start")
            logger.info("Continuing without ngrok - webhooks will not work")
        
        # 2. Start Function App
        self.start_function_app()
        
        # 3. Wait for it to be ready
        if not await self.wait_for_function_app():
            logger.error("❌ Function App failed to start")
            return False
        
        # 4. Setup webhooks
        await self.setup_webhooks()

        # 5. Initialize chat subscriptions for existing chats
        try:
            await initialize_chat_subscription_manager()
            await self.chat_subscription_manager.\
                subscribe_to_all_existing_chats()

            # Start periodic renewal task
            async def renew_loop():
                while True:
                    try:
                        await self.chat_subscription_manager.\
                            renew_expiring_subscriptions()
                    except Exception as e:
                        logger.error(f"Renewal error: {e}")
                    await asyncio.sleep(600)

            renew_task = asyncio.create_task(renew_loop())
            self.background_tasks.append(renew_task)
        except Exception as e:
            logger.error(f"Chat subscription setup failed: {e}")

        # 6. Wait a bit for token service to be ready
        logger.info("⏳ Waiting for token service to initialize...")
        await asyncio.sleep(5)

        # 7. Ensure token is available before starting sync
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
        
        # 8. Start sync service
        self.start_sync_service()
        
        logger.info("✅ All services started successfully!")
        logger.info("📡 Function App: http://localhost:7071")
        if self.webhook_url:
            logger.info(f"🌐 Webhook URL: {self.webhook_url}")
        logger.info("🔄 Planner sync service: Running")
        logger.info("📨 Webhooks: Configured")
        
        return True
    
    async def _get_pid_on_port(self, port: int) -> Optional[int]:
        """Return PID listening on a port, or None if free."""
        try:
            if sys.platform == "win32":
                # Use PowerShell to query the owning process
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        f"$c=Get-NetTCPConnection -State Listen -LocalPort {port} "
                        f"-ErrorAction SilentlyContinue; "
                        f"if($c){{ $c.OwningProcess | Select-Object -First 1 }}"
                    ),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                out = result.stdout.strip()
                if out.isdigit():
                    return int(out)
                return None
            else:
                # Best-effort using lsof
                result = subprocess.run(
                    ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
                    capture_output=True,
                    text=True,
                )
                out = result.stdout.strip().splitlines()
                return int(out[0]) if out and out[0].isdigit() else None
        except Exception:
            return None

    async def _ensure_port_closed(
        self,
        port: int,
        expected_pid: Optional[int] = None,
        timeout_seconds: float = 5.0,
    ):
        """Ensure the given port is closed.

        If the port remains busy and expected_pid is provided, attempt to stop
        that specific process only. Never kill an unrelated process.
        """
        import time

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            pid = await self._get_pid_on_port(port)
            if pid is None:
                return
            await asyncio.sleep(0.2)

        # If still in use, attempt to terminate the owning process (if it matches)
        pid = await self._get_pid_on_port(port)
        if pid is not None and expected_pid is not None and pid == expected_pid:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        [
                            "powershell",
                            "-NoProfile",
                            "-Command",
                            f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        elif pid is not None and expected_pid is not None and pid != expected_pid:
            logger.warning(
                "Port %s is held by PID %s, "
                "which does not match expected PID %s. Skipping force kill.",
                port,
                pid,
                expected_pid,
            )

    async def stop_all(self):
        """Stop all services gracefully and free occupied ports."""
        if self.shutdown_in_progress:
            return

        self.shutdown_in_progress = True
        logger.info("\nStopping all services...")

        # Stop V5 sync service first
        if self.sync_service:
            logger.info("Stopping Planner sync service V5...")
            try:
                await self.sync_service.stop()
                logger.info("Planner sync service V5 stopped.")
            except Exception as e:
                logger.error(f"Error stopping V5 sync service: {e}")

        # Cancel any remaining background tasks and wait for them
        for task in list(self.background_tasks):
            if not task.done():
                task.cancel()
        if self.background_tasks:
            await asyncio.gather(
                *self.background_tasks,
                return_exceptions=True,
            )

        # Stop ngrok
        if self.ngrok_process:
            logger.info("Stopping ngrok...")
            try:
                if sys.platform == "win32":
                    # CTRL_BREAK_EVENT targets the process group
                    # created with CREATE_NEW_PROCESS_GROUP
                    self.ngrok_process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.ngrok_process.terminate()

                try:
                    self.ngrok_process.wait(timeout=5)
                    logger.info("ngrok stopped.")
                except subprocess.TimeoutExpired:
                    logger.warning("ngrok did not stop in time; killing...")
                    self.ngrok_process.kill()
                    self.ngrok_process.wait()
            except Exception as e:
                logger.error(f"Error stopping ngrok: {e}")

        # Stop Function App
        if self.func_process:
            logger.info("Stopping Azure Function App...")
            try:
                if sys.platform == "win32":
                    # Prefer CTRL_BREAK_EVENT for child process group
                    self.func_process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.func_process.terminate()

                try:
                    self.func_process.wait(timeout=10)
                    logger.info("Function App stopped.")
                except subprocess.TimeoutExpired:
                    logger.warning("Function App did not stop in time; killing...")
                    self.func_process.kill()
                    self.func_process.wait()
            except Exception as e:
                logger.error(f"Error stopping Function App: {e}")

        # Ensure local ports are freed (Azure Functions default 7071; ngrok API 4040)
        try:
            await self._ensure_port_closed(
                7071,
                expected_pid=self.func_process.pid if self.func_process else None,
                timeout_seconds=6.0,
            )
            await self._ensure_port_closed(
                4040,
                expected_pid=self.ngrok_process.pid if self.ngrok_process else None,
                timeout_seconds=3.0,
            )
        except Exception:
            pass

        logger.info("All services stopped.")


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
            logger.info("\n" + "=" * 50)
            logger.info("All services are running.")
            logger.info("Press Ctrl+C to stop all services")
            logger.info("=" * 50 + "\n")

            # Keep running until shutdown signal
            await shutdown_event.wait()

        else:
            logger.error("Failed to start all services")
            sys.exit(1)

    except KeyboardInterrupt:
        # This might not be reached due to signal handlers, but just in case
        logger.info("\nKeyboard interrupt received...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always try to clean up
        logger.info("\nCleaning up...")
        await manager.stop_all()

        # Give a moment for cleanup to complete
        await asyncio.sleep(0.5)

        logger.info("\nGoodbye!")


if __name__ == "__main__":
    # On Windows, ensure proper signal handling for subprocesses
    if sys.platform == "win32":
        # This helps with subprocess signal handling on Windows
        os.environ['PYTHONUNBUFFERED'] = '1'
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle any final keyboard interrupt
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)