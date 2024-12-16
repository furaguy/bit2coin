# File: src/monitoring/logging_config.py

import logging
import logging.handlers
import os
from datetime import datetime

class LogConfig:
    def __init__(
        self,
        log_dir: str = "logs",
        max_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.log_dir = log_dir
        self.max_size = max_size
        self.backup_count = backup_count
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def setup_logging(self):
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        # Set up file handler
        log_file = os.path.join(
            self.log_dir,
            f'bit2coin_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_size,
            backupCount=self.backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)

        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)