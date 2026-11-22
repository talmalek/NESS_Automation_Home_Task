import logging
import os
from datetime import datetime


class TestLogger:
    def __init__(self, test_name: str, log_dir: str = "results/logs", level: int = logging.INFO):
        self._test_name = test_name
        self._log_dir = log_dir
        self._level = level
        self.log_file = ""
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Configure logger with file and console handlers."""
        os.makedirs(self._log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self._log_dir, f"{timestamp}_{self._test_name}.log")

        logger = logging.getLogger(f"test_{self._test_name}")
        logger.setLevel(self._level)
        logger.propagate = False

        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(self._level)
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(self._level)
            stream_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

        return logger

    def info(self, message: str) -> None:
        self.logger.info(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)
