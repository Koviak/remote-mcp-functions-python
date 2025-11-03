"""Ensure SWIG warning filters load when Azure Functions boot from src/ directory."""

from importlib import util as _import_util
from pathlib import Path as _Path


def _load_repo_filters() -> None:
    repo_sitecustomize = _Path(__file__).resolve().parent.parent / "sitecustomize.py"
    if not repo_sitecustomize.exists():
        return

    spec = _import_util.spec_from_file_location("repo_sitecustomize", repo_sitecustomize)
    if spec and spec.loader:  # pragma: no branch - defensive
        module = _import_util.module_from_spec(spec)
        spec.loader.exec_module(module)


def _fallback_filters() -> None:
    import warnings

    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"^builtin type SwigPy[A-Za-z0-9_]* has no __module__ attribute$",
    )
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"^builtin type swigvarlink has no __module__ attribute$",
    )


try:
    _load_repo_filters()
except Exception:  # pragma: no cover - last resort to keep startup healthy
    _fallback_filters()
else:
    _fallback_filters()


