import logging
import os

class Logger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Set the log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        numeric_level = getattr(logging, log_level, None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {log_level}')
        self.logger.setLevel(numeric_level)

        # Create a console handler
        ch = logging.StreamHandler()
        ch.setLevel(numeric_level)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d] %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def get_logger(self):
        return self.logger
