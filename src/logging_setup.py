import logging
import os
from typing import Optional


DEFAULT_LOG_DIR = os.environ.get("MCP_LOG_DIR", os.path.join(os.path.dirname(__file__), "logs"))
DEFAULT_LOG_FILE = os.environ.get("MCP_LOG_FILE", "mcp_server.log")
DEFAULT_LEVEL = os.environ.get("MCP_LOG_LEVEL", "INFO").upper()
MAX_BYTES = int(os.environ.get("MCP_LOG_MAX_BYTES", str(1_000_000)))  # 1 MB cap
KEEP_FRACTION = float(os.environ.get("MCP_LOG_KEEP_FRACTION", "0.9"))


class CappedFileHandler(logging.FileHandler):
    """A single-file log handler that caps the file size.

    When the file exceeds MAX_BYTES, it trims to the last KEEP_FRACTION of bytes
    in-place and continues appending. No rotation files are created.
    """

    def __init__(self, filename: str, mode: str = "a", encoding: Optional[str] = "utf-8"):
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, mode=mode, encoding=encoding, delay=False)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
            self._enforce_cap()
        except Exception:  # Do not raise from logging
            try:
                self.handleError(record)
            except Exception:
                pass

    def _enforce_cap(self) -> None:
        try:
            # Flush to ensure size is accurate
            if self.stream and hasattr(self.stream, "flush"):
                try:
                    self.stream.flush()
                except Exception:
                    pass

            path = self.baseFilename
            size = os.path.getsize(path) if os.path.exists(path) else 0
            if size <= MAX_BYTES:
                return

            keep_bytes = max(1, int(MAX_BYTES * KEEP_FRACTION))
            # Read last keep_bytes and rewrite file atomically
            with open(path, "rb") as f:
                if size > keep_bytes:
                    f.seek(size - keep_bytes)
                data = f.read()
            # Rewrite file with kept tail
            with open(path, "wb") as f:
                f.write(data)
            # Re-open stream in append mode for continued logging
            self.acquire()
            try:
                if self.stream:
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                self.stream = self._open()
            finally:
                self.release()
        except Exception:
            # Silently ignore errors to avoid logging recursion
            pass


def setup_logging(
    log_dir: Optional[str] = None,
    file_name: Optional[str] = None,
    level: Optional[str] = None,
    add_console: bool = True,
) -> None:
    """Configure root logger with a capped single-file handler and optional console.

    Safe to call multiple times; it will not duplicate handlers.
    """
    log_dir = log_dir or DEFAULT_LOG_DIR
    file_name = file_name or DEFAULT_LOG_FILE
    level_name = (level or DEFAULT_LEVEL).upper()
    try:
        log_level = getattr(logging, level_name, logging.INFO)
    except Exception:
        log_level = logging.INFO

    file_path = os.path.join(log_dir, file_name)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Idempotency: avoid duplicate handlers
    for h in list(root.handlers):
        if isinstance(h, CappedFileHandler) and getattr(h, "baseFilename", None) == file_path:
            # Already configured
            if add_console:
                _ensure_console_handler(root, log_level)
            return

    # File handler
    file_handler = CappedFileHandler(file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(log_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if add_console:
        _ensure_console_handler(root, log_level)


def _ensure_console_handler(root: logging.Logger, level: int) -> None:
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "name", "") == "console":
            h.setLevel(level)
            return
    ch = logging.StreamHandler()
    ch.name = "console"
    ch.setLevel(level)
    ch.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%H:%M:%S")
    )
    root.addHandler(ch)


