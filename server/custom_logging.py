import os
from logging import Formatter, getLogger, DEBUG, INFO, StreamHandler, FileHandler
from datetime import datetime


now = datetime.now()
current_time = now.strftime("%m-%d")
log_file_path = os.path.join('logs', f"{current_time}-server.log")

# Create necessary directories if they don't exist
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Check if log file exists, if not create it and add separator line
if not os.path.exists(log_file_path):
    with open(log_file_path, 'w') as f:   # write mode
        f.write('-' * 50 + '\n')  # separator line
# else:
#     with open(log_file_path, 'a') as f:   # append mode
#         f.write('-' * 50 + '\n')  # separator line

logger = getLogger(__name__)
logger.setLevel(DEBUG)

# TODO: make it so this works and we get class and method trace in logs
class CustomFormatter(Formatter):
    def format(self, record):
        if hasattr(record, 'funcName'):
            record.message = f"{record.module}.{
                record.funcName} - {record.getMessage()}"
        else:
            record.message = record.getMessage()
        return super().format(record)


# Define formatter for console and file handlers, using custom formatter
formatter = CustomFormatter('[%(asctime)s] (%(levelname)s) %(message)s')

# formatter = Formatter('[%(asctime)s] (%(levelname)s) %(name)s.%(funcName)s: %(message)s')

# Create stream handler and set level to INFO
stream_handler = StreamHandler()
stream_handler.setLevel(INFO)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(stream_handler)

# Create file handler which logs debug messages and set formatter
file_handler = FileHandler(log_file_path, mode='a')  # append mode
file_handler.setLevel(DEBUG)
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)
