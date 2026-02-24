import os
import sys
import importlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

start_all_services = importlib.import_module("start_all_services")
build_function_host_env = start_all_services.build_function_host_env
python_can_import_modules = start_all_services.python_can_import_modules


def test_build_function_host_env_defaults_to_current_interpreter() -> None:
    base_env = {"EXISTING_KEY": "existing-value"}
    env = build_function_host_env(base_env=base_env)

    assert env["EXISTING_KEY"] == "existing-value"
    assert env["ASPNETCORE_URLS"] == "http://0.0.0.0:7071"
    assert (
        env["languageWorkers__python__defaultExecutablePath"]
        == sys.executable
    )
    assert (
        env["languageWorkers:python:defaultExecutablePath"]
        == sys.executable
    )
    assert env["PYTHONEXECUTABLE"] == sys.executable


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
