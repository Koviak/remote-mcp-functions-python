import os
import signal
import sys
import importlib
import json
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

    assert popen_call["cmd"] == ["/usr/bin/func", "start", "--port", "7071"]
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
