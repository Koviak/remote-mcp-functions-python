"""Global warning filters for Remote MCP Functions runtime."""

import warnings


# Uvicorn/embedding dependencies emit noisy SWIG deprecation warnings on import.
# Register the filters before any other module loads so they never hit the logs.
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

