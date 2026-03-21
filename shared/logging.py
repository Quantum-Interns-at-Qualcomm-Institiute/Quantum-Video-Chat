import json
import os
from logging import Formatter, getLogger, DEBUG, INFO, StreamHandler
from logging.handlers import RotatingFileHandler
from datetime import datetime


def get_logger(name: str, log_dir: str = 'logs'):
    """
    Create and return a configured logger.

    Parameters
    ----------
    name : str
        Logger name, also used as the log file prefix.
    log_dir : str
        Directory to write log files into (relative to CWD or absolute).
    """
    now = datetime.now()
    current_time = now.strftime("%m-%d_%H-%M-%S")
    log_file_path = os.path.join(log_dir, f"{current_time}-{name}.log")

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w') as f:
            f.write('-' * 50 + '\n')

    logger = getLogger(name)
    logger.setLevel(DEBUG)
    # Store the log file path on the logger so callers can find it later.
    logger.log_file_path = log_file_path

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    class CustomFormatter(Formatter):
        def format(self, record):
            if hasattr(record, 'funcName'):
                record.message = f"{record.module}.{record.funcName} - {record.getMessage()}"
            else:
                record.message = record.getMessage()
            return super().format(record)

    class JSONFormatter(Formatter):
        """Structured JSON log formatter for machine-readable output."""
        def format(self, record):
            entry = {
                'timestamp': self.formatTime(record, self.datefmt),
                'level': record.levelname,
                'logger': record.name,
                'module': record.module,
                'function': getattr(record, 'funcName', ''),
                'message': record.getMessage(),
            }
            # Include extra fields if present (e.g. user_id, request_id)
            for key in ('user_id', 'request_id', 'peer_id', 'qber', 'event'):
                if hasattr(record, key):
                    entry[key] = getattr(record, key)
            if record.exc_info and record.exc_info[1]:
                entry['exception'] = str(record.exc_info[1])
            return json.dumps(entry)

    formatter = CustomFormatter('[%(asctime)s] (%(levelname)s) %(message)s')
    json_formatter = JSONFormatter()

    stream_handler = StreamHandler()
    stream_handler.setLevel(INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        log_file_path, mode='a',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Structured JSON log alongside the human-readable one
    json_log_path = log_file_path.replace('.log', '.json.log')
    json_handler = RotatingFileHandler(
        json_log_path, mode='a',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    json_handler.setLevel(DEBUG)
    json_handler.setFormatter(json_formatter)
    logger.addHandler(json_handler)

    return logger
