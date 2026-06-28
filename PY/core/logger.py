import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_file: str = "app.log", level: str = "INFO", qt_handler: logging.Handler = None, max_log_size_mb: float = 1.0) -> logging.Logger:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not log_file:
        log_file = "app.log"

    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    max_bytes = int(max_log_size_mb * 1024 * 1024)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    if qt_handler is not None:
        qt_handler.setFormatter(formatter)
        root_logger.addHandler(qt_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


logger = get_logger(__name__)
