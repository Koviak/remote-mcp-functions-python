import os
import sys
import importlib
import json
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

start_all_services = importlib.import_module("start_all_services")
build_function_host_env = start_all_services.build_function_host_env
python_can_import_modules = start_all_services.python_can_import_modules


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
    assert env["PYTHONEXECUTABLE"] == sys.executable


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
    assert pinned_path.lower().endswith("python.exe")
    assert values["languageWorkers:python:defaultExecutablePath"] == pinned_path
    assert values["PYTHONEXECUTABLE"] == pinned_path


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
