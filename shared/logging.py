import os
from logging import Formatter, getLogger, DEBUG, INFO, StreamHandler, FileHandler
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

    formatter = CustomFormatter('[%(asctime)s] (%(levelname)s) %(message)s')

    stream_handler = StreamHandler()
    stream_handler.setLevel(INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = FileHandler(log_file_path, mode='a')
    file_handler.setLevel(DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
