import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(log_file: str = 'polarise.log', level: str = 'INFO'):
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Setup file handler
    file_handler = RotatingFileHandler(
        f'logs/{log_file}',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger