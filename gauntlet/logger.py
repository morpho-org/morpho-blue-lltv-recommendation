import logging
import os

def get_logger(name):
    return Logger(name).logger

class Logger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

        # Set the log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        numeric_level = getattr(logging, log_level, None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {log_level}')
        self.logger.setLevel(numeric_level)

        # Create a console handler
        ch = logging.StreamHandler()
        ch.setLevel(numeric_level)

        # Log with the time, log level, file name, line number
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d] %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def get_logger(self) -> logging.Logger:
        return self.logger
