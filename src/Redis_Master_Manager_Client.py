"""Shim for the Annika 2.0 Redis master manager.

This repository must always use the single source of truth located in the
Annika 2.0 project (`Annika_2.0/Redis_Master_Manager_Client.py`). Azure
Functions, however, executes from the isolated `src/` directory and cannot
resolve sibling repositories automatically.  This shim locates the canonical
module, loads it once, and then exposes its public surface so the rest of the
code can continue importing ``Redis_Master_Manager_Client`` without change.

If the Annika repository cannot be located, the ImportError explains how to
provide the path explicitly.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


_PROXY_MODULE_NAME = "annika_redis_master_manager_client"


def _resolve_annika_manager_path() -> Path:
    """Return the filesystem path to the canonical manager module.

    Resolution order:
    1. ``ANNIKA_REDIS_MANAGER_PATH`` environment variable (file or directory)
    2. ``ANNIKA_REPO_ROOT`` environment variable pointing at the Annika repo
    3. Walk up the directory hierarchy looking for a sibling ``Annika_2.0``

    Raises:
        ImportError: if the file cannot be found.
    """

    env_path = os.environ.get("ANNIKA_REDIS_MANAGER_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_dir():
            candidate = candidate / "Redis_Master_Manager_Client.py"
        if candidate.exists():
            return candidate

    env_repo_root = os.environ.get("ANNIKA_REPO_ROOT")
    if env_repo_root:
        repo_candidate = Path(env_repo_root)
        if repo_candidate.is_dir():
            candidate = repo_candidate / "Redis_Master_Manager_Client.py"
            if candidate.exists():
                return candidate

    current = Path(__file__).resolve()
    for parent in current.parents:
        sibling = parent / "Annika_2.0"
        candidate = sibling / "Redis_Master_Manager_Client.py"
        if candidate.exists():
            return candidate

    raise ImportError(
        "Unable to locate Annika_2.0/Redis_Master_Manager_Client.py. "
        "Set ANNIKA_REDIS_MANAGER_PATH or ANNIKA_REPO_ROOT to point at the "
        "canonical module."
    )


def _load_canonical_module() -> ModuleType:
    """Load and return the canonical Redis manager module."""

    if _PROXY_MODULE_NAME in sys.modules:
        return sys.modules[_PROXY_MODULE_NAME]

    module_path = _resolve_annika_manager_path()
    spec = importlib.util.spec_from_file_location(_PROXY_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Redis manager from {module_path}")

    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)  # type: ignore[assignment]
    sys.modules[_PROXY_MODULE_NAME] = module
    return module


def _hydrate_current_module(source: ModuleType) -> None:
    """Populate the current module namespace with attributes from *source*."""

    current_module = sys.modules[__name__]
    for key, value in source.__dict__.items():
        if key in {"__name__", "__loader__", "__spec__"}:
            continue
        current_module.__dict__[key] = value

    __all__ = getattr(source, "__all__", None)
    if __all__ is not None:
        current_module.__dict__["__all__"] = __all__


_canonical_module = _load_canonical_module()
_hydrate_current_module(_canonical_module)

del importlib  # type: ignore[name-defined]
del ModuleType
del Path
del _canonical_module
del _hydrate_current_module
del _load_canonical_module
del _resolve_annika_manager_path
del _PROXY_MODULE_NAME

