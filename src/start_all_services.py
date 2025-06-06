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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceManager:
    def __init__(self):
        self.func_process = None
        self.sync_process = None
        self.base_dir = Path(__file__).parent
        
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
        logger.info("🔄 Starting Planner sync service...")
        
        # Start the sync service
        if sys.platform == "win32":
            self.sync_process = subprocess.Popen(
                [sys.executable, "planner_sync_service.py"],
                cwd=self.base_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            self.sync_process = subprocess.Popen(
                [sys.executable, "planner_sync_service.py"],
                cwd=self.base_dir
            )
        
        logger.info("✅ Planner sync service started")
    
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
        
        # 4. Start sync service
        self.start_sync_service()
        
        logger.info("✅ All services started successfully!")
        logger.info("📡 Function App: http://localhost:7071")
        logger.info("🔄 Planner sync service: Running")
        logger.info("📨 Webhooks: Configured")
        
        return True
    
    def stop_all(self):
        """Stop all services."""
        logger.info("🛑 Stopping all services...")
        
        if self.func_process:
            self.func_process.terminate()
            logger.info("Stopped Function App")
        
        if self.sync_process:
            self.sync_process.terminate()  
            logger.info("Stopped sync service")


async def main():
    """Main entry point."""
    manager = ServiceManager()
    
    try:
        # Start everything
        success = await manager.start_all()
        
        if success:
            logger.info("\n" + "="*50)
            logger.info("🎉 All services are running!")
            logger.info("Press Ctrl+C to stop all services")
            logger.info("="*50 + "\n")
            
            # Keep running
            await asyncio.Event().wait()
        else:
            logger.error("❌ Failed to start all services")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")
        manager.stop_all()
        logger.info("Goodbye!")


if __name__ == "__main__":
    asyncio.run(main()) 