import asyncio
import importlib
import json
import os
import signal
import sys
from pathlib import Path

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

start_all_services = importlib.import_module("start_all_services")
build_function_host_env = start_all_services.build_function_host_env
python_can_import_modules = start_all_services.python_can_import_modules
sync_function_host_local_settings = (
    start_all_services.sync_function_host_local_settings
)


def test_build_function_host_env_defaults_to_current_interpreter(monkeypatch) -> None:
    monkeypatch.delenv("FUNCTIONS_PYTHON_EXE", raising=False)
    base_env = {"EXISTING_KEY": "existing-value"}
    env = build_function_host_env(base_env=base_env)

    assert env["EXISTING_KEY"] == "existing-value"
    assert env["ASPNETCORE_URLS"] == "http://0.0.0.0:7071"
    assert env["GRAPH_RENEW_LOOP_OWNER"] == "start_all_services"
    assert (
        env["languageWorkers__python__defaultExecutablePath"]
        == sys.executable
    )
    assert (
        env["languageWorkers:python:defaultExecutablePath"]
        == sys.executable
    )
    assert env["FUNCTIONS_WORKER_RUNTIME"] == "python"
    assert (
        env[
            "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
        ]
        == sys.executable
    )
    assert env["PYTHONEXECUTABLE"] == sys.executable
    assert env["GRAPH_RENEW_LOOP_OWNER"] == "start_all_services"


def test_build_function_host_env_honors_explicit_override() -> None:
    custom_python = r"C:\custom\python.exe"
    env = build_function_host_env(
        base_env={},
        python_executable=custom_python,
    )

    assert (
        env["languageWorkers__python__defaultExecutablePath"]
        == custom_python
    )
    assert (
        env["languageWorkers:python:defaultExecutablePath"]
        == custom_python
    )
    assert (
        env[
            "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
        ]
        == custom_python
    )
    assert env["FUNCTIONS_WORKER_RUNTIME"] == "python"
    assert env["PYTHONEXECUTABLE"] == custom_python
    assert env["ASPNETCORE_URLS"] == "http://0.0.0.0:7071"


def test_build_function_host_env_falls_back_from_unusable_env_path() -> None:
    env = build_function_host_env(
        base_env={
            "FUNCTIONS_PYTHON_EXE": "__missing_python_for_start_all_services__",
        },
    )

    assert env["FUNCTIONS_PYTHON_EXE"] == sys.executable
    assert (
        env["languageWorkers__python__defaultExecutablePath"]
        == sys.executable
    )
    assert (
        env["languageWorkers:python:defaultExecutablePath"]
        == sys.executable
    )
    assert (
        env[
            "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
        ]
        == sys.executable
    )
    assert env["FUNCTIONS_WORKER_RUNTIME"] == "python"
    assert env["PYTHONEXECUTABLE"] == sys.executable


def test_build_function_host_env_prepends_worker_python_dir_to_path(
    tmp_path: Path,
) -> None:
    python_dir = tmp_path / "env" / "bin"
    python_dir.mkdir(parents=True)
    python_executable = python_dir / "python"
    python_executable.write_text("#!/bin/sh\n", encoding="utf-8")

    env = build_function_host_env(
        base_env={"PATH": "/usr/bin"},
        python_executable=str(python_executable),
    )

    assert env["FUNCTIONS_PYTHON_EXE"] == str(python_executable)
    assert env["PATH"].split(os.pathsep)[0] == str(python_dir)


def test_build_function_host_env_defaults_storage_to_azurite() -> None:
    env = build_function_host_env(base_env={"AzureWebJobsStorage": ""})

    assert env["AzureWebJobsStorage"] == "UseDevelopmentStorage=true"


def test_python_can_import_modules_reports_missing_module() -> None:
    ok, details = python_can_import_modules(sys.executable, ["json"])
    assert ok is True
    assert details == ""

    ok, details = python_can_import_modules(
        sys.executable,
        ["module_that_should_not_exist_annika"],
    )
    assert ok is False
    assert "No module named" in details or "ModuleNotFoundError" in details


def test_local_settings_pins_python_worker_path() -> None:
    settings_path = Path(__file__).resolve().parents[1] / "local.settings.json"
    with settings_path.open(encoding="utf-8") as handle:
        values = json.load(handle)["Values"]

    pinned_path = values["languageWorkers__python__defaultExecutablePath"]
    assert pinned_path
    assert values["languageWorkers:python:defaultExecutablePath"] == pinned_path
    assert values["PYTHONEXECUTABLE"] == pinned_path


def test_sync_function_host_local_settings_updates_only_runtime_keys(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "local.settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "IsEncrypted": False,
                "Values": {
                    "AZURE_CLIENT_SECRET": "keep-secret",
                    "AzureWebJobsStorage": "",
                    "FUNCTIONS_WORKER_RUNTIME": "",
                    "FUNCTIONS_PYTHON_EXE": r"C:\old\python.exe",
                    "languageWorkers:python:defaultExecutablePath": (
                        r"C:\old\python.exe"
                    ),
                    "languageWorkers__python__defaultExecutablePath": (
                        r"C:\old\python.exe"
                    ),
                    "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath": (
                        r"C:\old\python.exe"
                    ),
                    "PYTHONEXECUTABLE": r"C:\old\python.exe",
                },
            }
        ),
        encoding="utf-8",
    )

    python_path = "/opt/annika/bin/python"
    child_env = build_function_host_env(
        base_env={"AzureWebJobsStorage": ""},
        python_executable=python_path,
    )

    assert sync_function_host_local_settings(tmp_path, child_env) is True

    values = json.loads(settings_path.read_text(encoding="utf-8"))["Values"]
    assert values["AZURE_CLIENT_SECRET"] == "keep-secret"
    assert values["AzureWebJobsStorage"] == "UseDevelopmentStorage=true"
    assert values["FUNCTIONS_WORKER_RUNTIME"] == "python"
    assert values["FUNCTIONS_PYTHON_EXE"] == python_path
    assert values["languageWorkers:python:defaultExecutablePath"] == python_path
    assert (
        values["languageWorkers__python__defaultExecutablePath"]
        == python_path
    )
    assert (
        values[
            "AzureFunctionsJobHost__languageWorkers__python__defaultExecutablePath"
        ]
        == python_path
    )
    assert values["PYTHONEXECUTABLE"] == python_path

    assert sync_function_host_local_settings(tmp_path, child_env) is False


def test_resolve_func_prefers_native_path_binary_on_non_windows(
    monkeypatch, tmp_path: Path
) -> None:
    if sys.platform == "win32":
        return

    manager = start_all_services.ServiceManager()
    manager.base_dir = tmp_path

    repo_tools = tmp_path / "tools" / "func"
    repo_tools.mkdir(parents=True)
    (repo_tools / "func.exe").write_text("windows-only", encoding="utf-8")

    native_func = tmp_path / "bin" / "func"
    native_func.parent.mkdir(parents=True)
    native_func.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    native_func.chmod(0o755)

    monkeypatch.setattr(start_all_services.shutil, "which", lambda name: str(native_func) if name == "func" else None)

    resolved = manager._resolve_func()

    assert resolved == str(native_func)


def test_start_function_app_owns_posix_process_group(
    monkeypatch,
    tmp_path: Path,
) -> None:
    if sys.platform == "win32":
        return

    manager = start_all_services.ServiceManager()
    manager.base_dir = tmp_path
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(manager, "_resolve_func", lambda: "/usr/bin/func")
    monkeypatch.setattr(
        start_all_services,
        "sync_function_host_local_settings",
        lambda base_dir, child_env: False,
    )
    monkeypatch.setattr(
        start_all_services,
        "python_can_import_modules",
        lambda python_executable, modules: (True, ""),
    )

    popen_call = {}

    class FakePopen:
        pid = 2468

        def __init__(self, cmd, **kwargs):
            popen_call["cmd"] = cmd
            popen_call["kwargs"] = kwargs

    monkeypatch.setattr(start_all_services.subprocess, "Popen", FakePopen)

    manager.start_function_app()

    assert popen_call["cmd"] == [
        "/usr/bin/func",
        "start",
        "--python",
        "--port",
        "7071",
    ]
    assert popen_call["kwargs"]["start_new_session"] is True
    assert manager.func_process_group_id == 2468


@pytest.mark.asyncio
async def test_ensure_port_closed_signals_owned_child_process_group(
    monkeypatch,
) -> None:
    if sys.platform == "win32":
        return

    manager = start_all_services.ServiceManager()

    async def fake_get_pid_on_port(port: int) -> int:
        return 2469

    calls = []
    monkeypatch.setattr(manager, "_get_pid_on_port", fake_get_pid_on_port)
    monkeypatch.setattr(manager, "_get_process_group_id", lambda pid: 1357)
    monkeypatch.setattr(
        manager,
        "_signal_process_group",
        lambda process_group_id, signal_number: (
            calls.append((process_group_id, signal_number)) or True
        ),
    )

    await manager._ensure_port_closed(
        7071,
        expected_pid=2468,
        expected_process_group_id=1357,
        timeout_seconds=0.0,
    )

    assert calls == [(1357, signal.SIGTERM)]


@pytest.mark.asyncio
async def test_ensure_port_closed_skips_unowned_child_process_group(
    monkeypatch,
) -> None:
    if sys.platform == "win32":
        return

    manager = start_all_services.ServiceManager()

    async def fake_get_pid_on_port(port: int) -> int:
        return 2469

    calls = []
    monkeypatch.setattr(manager, "_get_pid_on_port", fake_get_pid_on_port)
    monkeypatch.setattr(manager, "_get_process_group_id", lambda pid: 9999)
    monkeypatch.setattr(
        manager,
        "_signal_process_group",
        lambda process_group_id, signal_number: (
            calls.append((process_group_id, signal_number)) or True
        ),
    )

    await manager._ensure_port_closed(
        7071,
        expected_pid=2468,
        expected_process_group_id=1357,
        timeout_seconds=0.0,
    )

    assert calls == []


@pytest.mark.asyncio
async def test_function_host_supervisor_recovers_unexpected_child_exit(
    monkeypatch,
    caplog,
) -> None:
    manager = start_all_services.ServiceManager()
    shutdown_event = asyncio.Event()
    recovery_calls = []

    class FailedProcess:
        pid = 2468

        def wait(self):
            return 17

    failed_process = FailedProcess()
    manager.func_process = failed_process
    manager.func_process_group_id = 2468

    async def fake_recover(**kwargs):
        recovery_calls.append(kwargs)
        shutdown_event.set()
        return True

    monkeypatch.setattr(manager, "_recover_function_app", fake_recover)

    await manager.supervise_function_app(shutdown_event)

    assert recovery_calls == [
        {
            "failed_process": failed_process,
            "failed_process_group_id": 2468,
            "exit_code": 17,
            "shutdown_event": shutdown_event,
        }
    ]
    assert "remote_mcp.function_host_exit_supervisor.v1" in caplog.text
    assert "parent_alive_required_child_dead" in caplog.text
    assert "function_host_unexpected_exit" in caplog.text


@pytest.mark.asyncio
async def test_function_host_recovery_reaps_and_retries_until_ready(
    monkeypatch,
) -> None:
    manager = start_all_services.ServiceManager()
    shutdown_event = asyncio.Event()
    cleanup_calls = []
    started_pids = iter((3001, 3002))
    readiness = iter((False, True))

    class Process:
        def __init__(self, pid, returncode=None):
            self.pid = pid
            self.returncode = returncode

        def poll(self):
            return self.returncode

    failed_process = Process(2468, returncode=17)

    async def fake_cleanup(process, process_group_id):
        cleanup_calls.append((process.pid, process_group_id))

    def fake_start():
        pid = next(started_pids)
        manager.func_process = Process(pid)
        manager.func_process_group_id = pid

    async def fake_wait_for_ready():
        return next(readiness)

    async def no_backoff(_seconds, _shutdown_event):
        return False

    monkeypatch.setattr(manager, "_cleanup_function_app_generation", fake_cleanup)
    monkeypatch.setattr(manager, "start_function_app", fake_start)
    monkeypatch.setattr(manager, "wait_for_function_app", fake_wait_for_ready)
    monkeypatch.setattr(manager, "_wait_for_recovery_backoff", no_backoff)

    recovered = await manager._recover_function_app(
        failed_process=failed_process,
        failed_process_group_id=2468,
        exit_code=17,
        shutdown_event=shutdown_event,
    )

    assert recovered is True
    assert cleanup_calls == [(2468, 2468), (3001, 3001)]
    assert manager.func_process.pid == 3002


@pytest.mark.asyncio
async def test_function_host_cleanup_force_kills_surviving_owned_group(
    monkeypatch,
) -> None:
    manager = start_all_services.ServiceManager()
    signal_calls = []
    port_close_calls = []

    class FailedProcess:
        pid = 2468

        def poll(self):
            return 17

    failed_process = FailedProcess()
    manager.func_process = failed_process
    manager.func_process_group_id = 2468
    manager._active_function_host_recovery_operation_id = "recovery:test"

    def fake_signal(process_group_id, signal_number):
        signal_calls.append((process_group_id, signal_number))
        return True

    async def fake_ensure_port_closed(*args, **kwargs):
        port_close_calls.append((args, kwargs))

    async def fake_get_pid_on_port(port):
        assert port == 7071
        return 2470

    monkeypatch.setattr(manager, "_signal_process_group", fake_signal)
    monkeypatch.setattr(manager, "_ensure_port_closed", fake_ensure_port_closed)
    monkeypatch.setattr(manager, "_get_pid_on_port", fake_get_pid_on_port)
    monkeypatch.setattr(manager, "_get_process_group_id", lambda _pid: 2468)

    await manager._cleanup_function_app_generation(failed_process, 2468)

    assert signal_calls == [
        (2468, signal.SIGTERM),
        (2468, signal.SIGKILL),
    ]
    assert len(port_close_calls) == 2
    assert manager.func_process is None
    assert manager.func_process_group_id is None


@pytest.mark.asyncio
async def test_function_host_cleanup_does_not_force_kill_unrelated_listener(
    monkeypatch,
) -> None:
    manager = start_all_services.ServiceManager()
    signal_calls = []

    class FailedProcess:
        pid = 2468

        def poll(self):
            return 17

    failed_process = FailedProcess()

    def fake_signal(process_group_id, signal_number):
        signal_calls.append((process_group_id, signal_number))
        return True

    async def fake_ensure_port_closed(*_args, **_kwargs):
        return None

    async def fake_get_pid_on_port(_port):
        return 9001

    monkeypatch.setattr(manager, "_signal_process_group", fake_signal)
    monkeypatch.setattr(manager, "_ensure_port_closed", fake_ensure_port_closed)
    monkeypatch.setattr(manager, "_get_pid_on_port", fake_get_pid_on_port)
    monkeypatch.setattr(manager, "_get_process_group_id", lambda _pid: 9001)

    await manager._cleanup_function_app_generation(failed_process, 2468)

    assert signal_calls == [(2468, signal.SIGTERM)]
