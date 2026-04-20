"""Exception and gateway log file configuration.

Two independent log files (RotatingFileHandler):
  logs/gateway.log     — WARNING+ all structured logs
  logs/exceptions.log  — ERROR+ with traceback

Registered on the 'lccg.file' logger to integrate with structlog's
_file_and_console_processor which uses the same logger.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_DEFAULT_LOGS_DIR = Path(__file__).parent.parent / "logs"


def setup_exception_logger(log_dir: str | None = None) -> None:
    """Register rotating file handlers on the 'lccg.file' logger.

    Must be called AFTER _setup_logging() so structlog is already routing
    JSON lines through logging.getLogger("lccg.file").

    Args:
        log_dir: Configurable log directory. Defaults to _DEFAULT_LOGS_DIR (src/logs).
    """
    logs_dir = Path(log_dir).expanduser() if log_dir else _DEFAULT_LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_logger = logging.getLogger("lccg.file")

    # 1) Gateway log: WARNING+ (health transitions, fallback decisions, etc.)
    gateway_handler = RotatingFileHandler(
        logs_dir / "gateway.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
        encoding="utf-8",
    )
    gateway_handler.setLevel(logging.WARNING)
    gateway_handler.setFormatter(logging.Formatter("%(message)s"))

    # 2) Exceptions log: ERROR+ with traceback
    exc_handler = RotatingFileHandler(
        logs_dir / "exceptions.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    exc_handler.setLevel(logging.ERROR)
    exc_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    file_logger.addHandler(gateway_handler)
    file_logger.addHandler(exc_handler)
