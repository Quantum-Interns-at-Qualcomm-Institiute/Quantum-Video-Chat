"""Shared logging setup with file rotation and JSON output.

Log level is controlled by the ``QVC_LOG_LEVEL`` environment variable.

+-----------+--------------------------------------------------+
| Value     | Console shows                                    |
+-----------+--------------------------------------------------+
| ``DEBUG`` | Everything (verbose)                             |
| ``INFO``  | Lifecycle, REST hits, connections, state changes |
| ``WARN``  | Warnings and errors only                         |
| ``ERROR`` | Errors only                                      |
+-----------+--------------------------------------------------+

File handlers *always* capture DEBUG regardless of the env var so that
verbose logs are available on disk even when the console is quiet.
"""

import json
import os
from datetime import UTC, datetime
from logging import DEBUG, ERROR, INFO, WARNING, Formatter, StreamHandler, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LEVEL_MAP = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARN": WARNING,
    "WARNING": WARNING,
    "ERROR": ERROR,
}

_console_level = _LEVEL_MAP.get(
    os.environ.get("QVC_LOG_LEVEL", "DEBUG").upper(), DEBUG,
)


def get_logger(name: str, log_dir: str = "logs"):
    """Create and return a configured logger.

    Parameters
    ----------
    name : str
        Logger name, also used as the log file prefix.
    log_dir : str
        Directory to write log files into (relative to CWD or absolute).
    """
    now = datetime.now(tz=UTC)
    current_time = now.strftime("%m-%d_%H-%M-%S")
    log_file_path = Path(log_dir) / f"{current_time}-{name}.log"

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_file_path.exists():
        log_file_path.write_text("-" * 50 + "\n")

    logger = getLogger(name)
    logger.setLevel(DEBUG)
    # Store the log file path on the logger so callers can find it later.
    logger.log_file_path = log_file_path

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    class CustomFormatter(Formatter):
        def format(self, record):
            if hasattr(record, "funcName"):
                record.message = f"{record.module}.{record.funcName} - {record.getMessage()}"
            else:
                record.message = record.getMessage()
            return super().format(record)

    class JSONFormatter(Formatter):
        """Structured JSON log formatter for machine-readable output."""
        def format(self, record):
            entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": getattr(record, "funcName", ""),
                "message": record.getMessage(),
            }
            # Include extra fields if present (e.g. user_id, request_id)
            for key in ("user_id", "request_id", "peer_id", "qber", "event",
                        "sid", "client_id", "host", "port", "room_id"):
                if hasattr(record, key):
                    entry[key] = getattr(record, key)
            if record.exc_info and record.exc_info[1]:
                entry["exception"] = str(record.exc_info[1])
            return json.dumps(entry)

    formatter = CustomFormatter("[%(asctime)s] (%(levelname)s) %(message)s")
    json_formatter = JSONFormatter()

    # Console handler — level controlled by QVC_LOG_LEVEL
    stream_handler = StreamHandler()
    stream_handler.setLevel(_console_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Human-readable file handler — always DEBUG
    file_handler = RotatingFileHandler(
        log_file_path, mode="a",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Structured JSON log alongside the human-readable one — always DEBUG
    json_log_path = log_file_path.with_suffix(".json.log")
    json_handler = RotatingFileHandler(
        json_log_path, mode="a",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    json_handler.setLevel(DEBUG)
    json_handler.setFormatter(json_formatter)
    logger.addHandler(json_handler)

    return logger
