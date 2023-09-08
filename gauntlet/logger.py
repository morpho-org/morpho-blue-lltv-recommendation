import logging
import os


def setup_logger():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(
        level=numeric_level,
        format="[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d] %(message)s",
        handlers=[logging.StreamHandler()],
    )


def get_logger(name):
    return logging.getLogger(name)


# Call setup_logger upon module import
setup_logger()
