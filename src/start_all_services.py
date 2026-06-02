#!/usr/bin/env python3
"""
Comprehensive startup script for all services.
Starts ngrok, Function App, sets up webhooks, and runs Planner sync service.
"""
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional
import shutil

import httpx

# Load environment variables early so auth has credentials
import load_env  # noqa: F401  # side-effect: loads .env

# Add this import for token acquisition
from agent_auth_manager import get_agent_token
from chat_subscription_manager import (
    chat_subscription_manager,
    initialize_chat_subscription_manager,
)
from graph_subscription_manager import GraphSubscriptionManager
from logging_setup import setup_logging

setup_logging(add_console=True)
logger = logging.getLogger(__name__)

GRAPH_RENEW_LOOP_OWNER_DEFAULT = "start_all_services"
FUNCTION_HOST_RUNTIME_SETTING_KEYS = (
    "FUNCTIONS_WORKER_RUNTIME",
    "FUNCTIONS_PYTHON_EXE",
    "languageWorkers:python:defaultExecutablePath",
    "languageWorkers__python__defaultExecutablePath",
    "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath",
    "PYTHONEXECUTABLE",
    "AzureWebJobsStorage",
)


def python_can_import_modules(
    python_executable: str,
    modules: list[str],
) -> tuple[bool, str]:
    """Return whether a Python executable can import all modules."""
    import_code = "; ".join(f"import {module}" for module in modules)
    cmd = [python_executable, "-c", import_code]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return False, str(exc)

    if result.returncode == 0:
        return True, ""

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    details = stderr or stdout or "Unknown import failure"
    return False, details


def resolve_functions_python_executable(
    configured_python: Optional[str],
) -> str:
    """Return a usable Functions worker interpreter for this host."""
    if not configured_python:
        return sys.executable

    candidate = configured_python.strip()
    if not candidate:
        return sys.executable

    candidate_path = Path(candidate)
    if candidate_path.exists():
        return str(candidate_path)

    resolved_command = shutil.which(candidate)
    if resolved_command:
        return resolved_command

    logger.warning(
        "Ignoring unusable FUNCTIONS_PYTHON_EXE=%s; "
        "falling back to current interpreter %s",
        configured_python,
        sys.executable,
    )
    return sys.executable


def build_function_host_env(
    base_env: Optional[dict[str, str]] = None,
    python_executable: Optional[str] = None,
) -> dict[str, str]:
    """Build child environment for Azure Functions host process."""
    env = dict(base_env or os.environ)
    resolved_python = (
        python_executable
        or resolve_functions_python_executable(
            env.get("FUNCTIONS_PYTHON_EXE")
        )
    )
    env.setdefault("ASPNETCORE_URLS", "http://0.0.0.0:7071")
    env["FUNCTIONS_WORKER_RUNTIME"] = "python"
    # Core Tools resolves Python using this exact key name first.
    # Keep both forms for compatibility across config readers.
    env["FUNCTIONS_PYTHON_EXE"] = resolved_python
    env["languageWorkers:python:defaultExecutablePath"] = resolved_python
    env["languageWorkers__python__defaultExecutablePath"] = resolved_python
    env[
        "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
    ] = resolved_python
    env["PYTHONEXECUTABLE"] = resolved_python
    resolved_python_path = Path(resolved_python)
    if resolved_python_path.exists():
        python_dir = str(resolved_python_path.parent)
        current_path = env.get("PATH", "")
        path_parts = current_path.split(os.pathsep) if current_path else []
        if python_dir not in path_parts:
            env["PATH"] = (
                python_dir + os.pathsep + current_path
                if current_path
                else python_dir
            )
    if not str(env.get("AzureWebJobsStorage", "")).strip():
        env["AzureWebJobsStorage"] = "UseDevelopmentStorage=true"
    env.setdefault("GRAPH_RENEW_LOOP_OWNER", GRAPH_RENEW_LOOP_OWNER_DEFAULT)
    return env


def sync_function_host_local_settings(
    base_dir: Path,
    child_env: dict[str, str],
) -> bool:
    """Sync host-local runtime keys into local.settings.json.

    Azure Functions Core Tools reads local.settings.json during startup and can
    reintroduce a stale Windows Python path after the child environment has
    already been normalized. Only non-secret runtime bootstrap keys are updated;
    existing credentials and service settings are preserved.
    """
    settings_path = base_dir / "local.settings.json"
    if not settings_path.exists():
        return False

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "Could not read local.settings.json for runtime sync: %s",
            exc,
        )
        return False

    values = data.setdefault("Values", {})
    desired_values = {
        "FUNCTIONS_WORKER_RUNTIME": child_env["FUNCTIONS_WORKER_RUNTIME"],
        "FUNCTIONS_PYTHON_EXE": child_env["FUNCTIONS_PYTHON_EXE"],
        "languageWorkers:python:defaultExecutablePath": child_env[
            "languageWorkers:python:defaultExecutablePath"
        ],
        "languageWorkers__python__defaultExecutablePath": child_env[
            "languageWorkers__python__defaultExecutablePath"
        ],
        "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath": (
            child_env[
                "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
            ]
        ),
        "PYTHONEXECUTABLE": child_env["PYTHONEXECUTABLE"],
        "AzureWebJobsStorage": child_env.get(
            "AzureWebJobsStorage",
            "UseDevelopmentStorage=true",
        ),
    }

    changed = False
    for key, desired_value in desired_values.items():
        if values.get(key) != desired_value:
            values[key] = desired_value
            changed = True

    if not changed:
        return False

    temp_path = settings_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(settings_path)
    logger.info(
        "Updated local.settings.json runtime keys for current host: %s",
        ", ".join(FUNCTION_HOST_RUNTIME_SETTING_KEYS),
    )
    return True


class ServiceManager:
    def __init__(self):
        self.func_process = None
        self.ngrok_process = None
        self.sync_process = None
        self.base_dir = Path(__file__).parent
        self.shutdown_in_progress = False
        self.background_tasks = []  # Track background async tasks
        self.sync_service = None  # Track the sync service instance
        self.contact_sync_service = None
        self.webhook_url = None
        self.chat_subscription_manager = chat_subscription_manager
        self.graph_subscription_manager = GraphSubscriptionManager()
        self.func_process_group_id = None
        self.ngrok_process_group_id = None

    def _append_dir_to_path(self, directory: Path) -> None:
        """Ensure the given directory is on PATH for child processes."""
        try:
            directory_str = str(directory)
            current_path = os.environ.get("PATH", "")
            path_parts = current_path.split(os.pathsep) if current_path else []
            if directory_str not in path_parts:
                if current_path:
                    os.environ["PATH"] = (
                        directory_str + os.pathsep + current_path
                    )
                else:
                    os.environ["PATH"] = directory_str
        except Exception:
            # Non-fatal: if we cannot mutate PATH, we'll still
            # try absolute invocation
            pass

    def _resolve_ngrok(self) -> Optional[str]:
        """Resolve path to ngrok executable and ensure its directory
        is on PATH.

        Returns full path or command name if discoverable,
        else None.
        """
        # 1) Environment-driven hints (explicit override)
        env_vars = ["NGROK_EXE", "NGROK_PATH", "NGROK_DIR"]
        for var in env_vars:
            val = os.environ.get(var)
            if not val:
                continue
            candidate = Path(val)
            # If directory provided, look for executable inside
            if candidate.is_dir():
                for name in ("ngrok.exe", "ngrok"):
                    inner = candidate / name
                    if inner.exists():
                        self._append_dir_to_path(candidate)
                        return str(inner)
            # If direct file path
            if candidate.is_file():
                self._append_dir_to_path(candidate.parent)
                return str(candidate)

        # 2) Repository-local tools folder (no absolute paths hard-coded)
        for name in ("ngrok.exe", "ngrok"):
            local = self.base_dir / "tools" / name
            if local.exists():
                self._append_dir_to_path(local.parent)
                return str(local)

        # 3) System PATH last
        which_path = shutil.which("ngrok")
        if which_path:
            self._append_dir_to_path(Path(which_path).parent)
            return which_path

        return None

    def _resolve_func(self) -> Optional[str]:
        """Resolve path to Azure Functions Core Tools (func) and
        ensure on PATH.

        Returns full path or command name if discoverable,
        else None.
        """
        binary_names = ("func.cmd", "func.exe", "func") if sys.platform == "win32" else ("func",)

        # 1) Environment-driven hints (explicit override)
        env_vars = [
            "FUNC_PATH",
            "FUNCTIONS_CORE_TOOLS_PATH",
            "AZURE_FUNCTIONS_CORE_TOOLS_PATH",
        ]
        for var in env_vars:
            val = os.environ.get(var)
            if not val:
                continue
            candidate = Path(val)
            if candidate.is_dir():
                # Common filenames
                for name in binary_names:
                    inner = candidate / name
                    if inner.exists():
                        self._append_dir_to_path(candidate)
                        return str(inner)
            if candidate.is_file():
                self._append_dir_to_path(candidate.parent)
                return str(candidate)

        # 2) Typical Windows locations via environment expansion
        #    (no hard-coded literals)
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                npm_cmd = Path(appdata) / "npm" / "func.cmd"
                if npm_cmd.exists():
                    self._append_dir_to_path(npm_cmd.parent)
                    return str(npm_cmd)
            # Program Files (x64) and (x86)
            program_files = os.environ.get("ProgramFiles")
            program_files_x86 = os.environ.get("ProgramFiles(x86)")
            local_app = os.environ.get("LOCALAPPDATA")

            def first_existing(paths: list[Path]) -> Optional[Path]:
                for p in paths:
                    if p and p.exists():
                        return p
                return None

            candidate_paths: list[Path] = []
            # Common vendor folder names and potential version subfolders
            vendor_folders = [
                "Azure Functions Core Tools",
                str(Path("Microsoft") / "Azure Functions Core Tools"),
            ]
            version_subfolders = ["", "4"]

            for base in [program_files, program_files_x86]:
                if not base:
                    continue
                base_path = Path(base)
                for vendor in vendor_folders:
                    for version in version_subfolders:
                        sub = base_path / vendor
                        if version:
                            sub = sub / version
                        candidate_paths.append(sub / "func.exe")

            if local_app:
                la_base = Path(local_app) / "Programs" / "Azure Functions Core Tools"
                for version in version_subfolders:
                    sub = la_base
                    if version:
                        sub = sub / version
                    candidate_paths.append(sub / "func.exe")

            found = first_existing([Path(c) for c in candidate_paths])
            if found:
                self._append_dir_to_path(found.parent)
                return str(found)

        # 3) On non-Windows, prefer a native func already on PATH over any
        # bundled Windows portable artifacts that may exist in the repository.
        which_path = shutil.which("func")
        if which_path:
            self._append_dir_to_path(Path(which_path).parent)
            return which_path

        # 4) Repository-local tools folder
        if sys.platform == "win32":
            # Prefer nested portable layout: tools/func/func.exe
            nested_portable = self.base_dir / "tools" / "func" / "func.exe"
            if nested_portable.exists():
                self._append_dir_to_path(nested_portable.parent)
                return str(nested_portable)
        for name in binary_names:
            local = self.base_dir / "tools" / name
            if local.exists():
                self._append_dir_to_path(local.parent)
                return str(local)

        return None

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
                logger.info("ngrok already running: %s", existing_url)
                self.webhook_url = f"{existing_url}/api/graph_webhook"
                # Update environment variable
                os.environ["GRAPH_WEBHOOK_URL"] = self.webhook_url
                return True
            
            # Start ngrok
            logger.info("Starting ngrok...")

            ngrok_path = self._resolve_ngrok()
            if not ngrok_path:
                logger.error(
                    "ngrok not found. Ensure it is installed and "
                    "available on PATH, or set "
                    "NGROK_EXE/NGROK_PATH/NGROK_DIR."
                )
                return False
            
            # Use the agency-swarm domain; include authtoken if available
            cmd = [
                ngrok_path,
                "http",
                "--domain",
                "agency-swarm.ngrok.app",
                "7071",
            ]
            ngrok_token = os.environ.get("NGROK_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")
            if ngrok_token:
                cmd.insert(2, "--authtoken")
                cmd.insert(3, ngrok_token)
            
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
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                self.ngrok_process_group_id = self.ngrok_process.pid
            
            # Wait for ngrok to start
            for i in range(15):  # Give it more time
                await asyncio.sleep(2)
                url = await self.find_ngrok_tunnel()
                if url:
                    logger.info("ngrok started: %s", url)
                    self.webhook_url = f"{url}/api/graph_webhook"
                    # Update environment variable
                    os.environ["GRAPH_WEBHOOK_URL"] = self.webhook_url
                    return True
                
                if i % 5 == 0:
                    logger.info("Still waiting for ngrok... (%s/15)", i)
            
            logger.error("ngrok failed to start")
            return False
            
        except Exception as e:
            logger.error("Error starting ngrok: %s", e)
            return False
        
    async def wait_for_function_app(self, max_attempts=30):
        """Wait for Function App to be ready."""
        logger.info("Waiting for Function App to be ready...")

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
                            logger.info("Function App is ready")
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
                logger.info(
                    "Still waiting... (%s/%s)",
                    attempt,
                    max_attempts,
                )

        return False

    async def setup_webhooks(self):
        """Set up MS Graph webhooks."""
        logger.info("Setting up MS Graph webhooks...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Trigger webhook setup via HTTP endpoint
                response = await client.post(
                    "http://localhost:7071/api/graph_webhook",
                    params={"validationToken": "setup"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info("Webhooks setup complete")
                    return True
                else:
                    logger.warning(
                        "Webhook setup returned: %s",
                        response.status_code,
                    )
                    
        except Exception as e:
            logger.error("Webhook setup failed: %s", e)
        
        return False

    def start_function_app(self):
        """Start the Azure Function App."""
        logger.info("Starting Azure Function App...")
        
        # Change to src directory where host.json is located
        os.chdir(self.base_dir)
        
        # Start func host
        func_path = self._resolve_func()
        if not func_path:
            raise FileNotFoundError(
                "Azure Functions Core Tools (func) not found. Ensure it is "
                "installed and on PATH, or set FUNC_PATH / "
                "FUNCTIONS_CORE_TOOLS_PATH / AZURE_FUNCTIONS_CORE_TOOLS_PATH."
            )
        # Run from the function app directory where host.json resides
        func_cwd = str(self.base_dir)
        # Ensure host uses current interpreter and binds to all interfaces.
        child_env = build_function_host_env()
        sync_function_host_local_settings(self.base_dir, child_env)
        worker_python = child_env.get(
            "languageWorkers__python__defaultExecutablePath",
            sys.executable,
        )

        ok, details = python_can_import_modules(
            worker_python,
            ["azure.identity", "azure.functions"],
        )
        if not ok:
            raise RuntimeError(
                "Selected Functions Python interpreter cannot import required "
                f"Azure modules: {worker_python}. Details: {details}"
            )
        logger.info("Using Functions Python worker: %s", worker_python)

        cmd = [func_path, "start", "--python", "--port", "7071"]
        if sys.platform == "win32":
            self.func_process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                cwd=func_cwd,
                env=child_env,
            )
        else:
            self.func_process = subprocess.Popen(
                cmd,
                cwd=func_cwd,
                env=child_env,
                start_new_session=True,
            )
            self.func_process_group_id = self.func_process.pid
        
        logger.info("Function App process started")

    def start_sync_service(self):
        """Start the Planner sync service."""
        logger.info("Starting Planner sync service V5...")
        
        # Initialize webhook handler first
        from webhook_handler import initialize_webhook_handler
        asyncio.create_task(initialize_webhook_handler())
        
        # Start V5 sync service
        from planner_sync_service_v5 import WebhookDrivenPlannerSync
        self.sync_service = WebhookDrivenPlannerSync()
        
        # Start sync service in background
        sync_task = asyncio.create_task(self.sync_service.start())
        self.background_tasks.append(sync_task)
        
        # Start contact sync service in background
        try:
            from contact_sync_service import ContactSyncService

            self.contact_sync_service = ContactSyncService()
            contact_task = asyncio.create_task(self.contact_sync_service.start())
            self.background_tasks.append(contact_task)
            logger.info("Contact sync service started")
        except Exception as exc:
            logger.error("Failed to start contact sync service: %s", exc)

        renew_owner = os.getenv(
            "GRAPH_RENEW_LOOP_OWNER",
            GRAPH_RENEW_LOOP_OWNER_DEFAULT,
        )
        if renew_owner == "start_all_services":
            logger.info(
                "Graph renewal loop owner=%s (loop enabled in start_all_services)",
                renew_owner,
            )

            async def renew_graph_subscriptions_loop():
                while True:
                    try:
                        await asyncio.to_thread(
                            self.graph_subscription_manager.renew_all_subscriptions
                        )
                    except Exception as exc:
                        logger.error(
                            "Graph subscription renewal loop failed: %s",
                            exc,
                        )
                    await asyncio.sleep(1800)

            graph_renew_task = asyncio.create_task(
                renew_graph_subscriptions_loop()
            )
            self.background_tasks.append(graph_renew_task)
        else:
            logger.info(
                "Graph renewal loop owner=%s (start_all_services loop skipped)",
                renew_owner,
            )

        logger.info("Planner sync service V5 started")

    async def ensure_token_available(self, max_attempts=10):
        """Ensure authentication token is available before starting sync."""
        logger.info(
            "Ensuring authentication tokens are available..."
        )
        
        for attempt in range(max_attempts):
            try:
                # Try to get agent token
                token = await asyncio.to_thread(get_agent_token)
                
                if token:
                    logger.info(
                        "Authentication token acquired successfully"
                    )
                    # Also verify it works with a simple API call
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://graph.microsoft.com/v1.0/me",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10,
                        )
                        if response.status_code == 200:
                            user_data = response.json()
                            logger.info(
                                "Token verified for user: %s",
                                user_data.get("displayName", "Unknown"),
                            )
                            return True
                        else:
                            logger.warning(
                                "Token validation failed: %s",
                                response.status_code,
                            )
                else:
                    logger.info(
                        "Waiting for token... (%s/%s)",
                        attempt + 1,
                        max_attempts,
                    )
                    
            except Exception as e:
                logger.debug(
                    "Token check attempt %s failed: %s",
                    attempt + 1,
                    e,
                )
            
            # Wait before retry
            await asyncio.sleep(3)
        
        logger.error("Failed to acquire authentication token")
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
        logger.info("Starting all services...")
        
        # 1. Start ngrok first
        if not await self.start_ngrok():
            logger.error("ngrok failed to start")
            logger.info("Continuing without ngrok - webhooks will not work")
        
        # 2. Start Function App
        self.start_function_app()
        
        # 3. Wait for it to be ready
        if not await self.wait_for_function_app():
            logger.error("Function App failed to start")
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
                        logger.error("Renewal error: %s", e)
                    await asyncio.sleep(600)

            renew_task = asyncio.create_task(renew_loop())
            self.background_tasks.append(renew_task)
        except Exception as e:
            logger.error("Chat subscription setup failed: %s", e)

        # 6. Wait a bit for token service to be ready
        logger.info("Waiting for token service to initialize...")
        await asyncio.sleep(5)

        # 7. Ensure token is available before starting sync
        if not await self.ensure_token_available():
            logger.error(
                "Cannot start sync service without authentication token"
            )
            logger.info(
                "Sync service will not be started. "
                "Other services will continue running."
            )
            # Don't fail completely, just skip sync service
            return True
        
        # 8. Start sync service
        self.start_sync_service()
        
        logger.info("All services started successfully")
        logger.info("Function App: http://0.0.0.0:7071")
        if self.webhook_url:
            logger.info("Webhook URL: %s", self.webhook_url)
        logger.info("Planner sync service: Running")
        logger.info("Contact sync service: Running")
        logger.info("Webhooks: Configured")
        
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
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
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
                    check=False,
                )
                out = result.stdout.strip().splitlines()
                return int(out[0]) if out and out[0].isdigit() else None
        except Exception:
            return None

    def _get_process_group_id(self, pid: int) -> Optional[int]:
        """Return the process group ID for a local process on POSIX."""
        if sys.platform == "win32":
            return None
        try:
            return os.getpgid(pid)
        except Exception:
            return None

    def _signal_process_group(
        self,
        process_group_id: Optional[int],
        signal_number: int,
    ) -> bool:
        """Signal an owned POSIX process group."""
        if sys.platform == "win32" or process_group_id is None:
            return False
        try:
            os.killpg(process_group_id, signal_number)
            return True
        except ProcessLookupError:
            return True
        except Exception:
            return False

    async def _ensure_port_closed(
        self,
        port: int,
        expected_pid: Optional[int] = None,
        expected_process_group_id: Optional[int] = None,
        timeout_seconds: float = 5.0,
    ):
        """Ensure the given port is closed.

        If the port remains busy and expected_pid is provided, attempt to stop
        that specific process, or an owned child in the expected process group.
        Never kill an unrelated process.
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
        elif (
            pid is not None
            and expected_process_group_id is not None
            and self._get_process_group_id(pid) == expected_process_group_id
        ):
            if self._signal_process_group(
                expected_process_group_id,
                signal.SIGTERM,
            ):
                logger.info(
                    "Closed port %s by signaling owned process group %s.",
                    port,
                    expected_process_group_id,
                )
        elif pid is not None and expected_pid is not None and pid != expected_pid:
            logger.warning(
                "Port %s is held by PID %s, "
                "which does not match expected PID %s. Skipping force kill.",
                port,
                pid,
                expected_pid,
            )
        elif pid is not None:
            logger.warning(
                "Port %s is held by PID %s with no owned process match. "
                "Skipping force kill.",
                port,
                pid,
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
                logger.error("Error stopping V5 sync service: %s", e)

        if self.contact_sync_service:
            logger.info("Stopping contact sync service...")
            try:
                await self.contact_sync_service.stop()
                logger.info("Contact sync service stopped.")
            except Exception as e:
                logger.error("Error stopping contact sync service: %s", e)

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
                    if not self._signal_process_group(
                        self.ngrok_process_group_id,
                        signal.SIGTERM,
                    ):
                        self.ngrok_process.terminate()

                try:
                    self.ngrok_process.wait(timeout=5)
                    logger.info("ngrok stopped.")
                except subprocess.TimeoutExpired:
                    logger.warning("ngrok did not stop in time; killing...")
                    if not self._signal_process_group(
                        self.ngrok_process_group_id,
                        signal.SIGKILL,
                    ):
                        self.ngrok_process.kill()
                    self.ngrok_process.wait()
            except Exception as e:
                logger.error("Error stopping ngrok: %s", e)

        # Stop Function App
        if self.func_process:
            logger.info("Stopping Azure Function App...")
            try:
                if sys.platform == "win32":
                    # Prefer CTRL_BREAK_EVENT for child process group
                    self.func_process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    if not self._signal_process_group(
                        self.func_process_group_id,
                        signal.SIGTERM,
                    ):
                        self.func_process.terminate()

                try:
                    self.func_process.wait(timeout=10)
                    logger.info("Function App stopped.")
                except subprocess.TimeoutExpired:
                    logger.warning("Function App did not stop in time; killing...")
                    if not self._signal_process_group(
                        self.func_process_group_id,
                        signal.SIGKILL,
                    ):
                        self.func_process.kill()
                    self.func_process.wait()
            except Exception as e:
                logger.error("Error stopping Function App: %s", e)

        # Ensure local ports are freed (Azure Functions default 7071; ngrok API 4040)
        try:
            await self._ensure_port_closed(
                7071,
                expected_pid=self.func_process.pid if self.func_process else None,
                expected_process_group_id=self.func_process_group_id,
                timeout_seconds=6.0,
            )
            await self._ensure_port_closed(
                4040,
                expected_pid=self.ngrok_process.pid if self.ngrok_process else None,
                expected_process_group_id=self.ngrok_process_group_id,
                timeout_seconds=3.0,
            )
        except Exception:
            pass

        logger.info("All services stopped.")


async def main() -> int:
    """Main entry point."""
    manager = ServiceManager()
    shutdown_event = asyncio.Event()
    exit_code = 0
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        if not shutdown_event.is_set():
            logger.info("\nShutdown signal received...")
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
            exit_code = 1

    except KeyboardInterrupt:
        # This might not be reached due to signal handlers, but just in case
        logger.info("\nKeyboard interrupt received...")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        # Always try to clean up
        logger.info("\nCleaning up...")
        await manager.stop_all()

        # Give a moment for cleanup to complete
        await asyncio.sleep(0.5)

        logger.info("\nGoodbye!")
    return exit_code


if __name__ == "__main__":
    # On Windows, ensure proper signal handling for subprocesses
    if sys.platform == "win32":
        # This helps with subprocess signal handling on Windows
        os.environ['PYTHONUNBUFFERED'] = '1'
    
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        # Handle any final keyboard interrupt
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
