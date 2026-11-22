import logging
import os
from datetime import datetime
from typing import Union

VERBOSE_LEVEL = 15
logging.addLevelName(VERBOSE_LEVEL, "VERBOSE")

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "VERBOSE": VERBOSE_LEVEL,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def parse_log_level(level: Union[int, str]) -> int:
    """Convert a string or integer log level (including VERBOSE=15) to a logging int."""
    if isinstance(level, int):
        return level
    normalized = level.strip().upper()
    if normalized not in _LEVEL_MAP:
        allowed = ", ".join(_LEVEL_MAP.keys())
        raise ValueError(f"Unsupported log level {level!r}. Allowed: {allowed}")
    return _LEVEL_MAP[normalized]


class TestLogger:
    def __init__(
        self,
        test_name: str,
        log_dir: str = "results/logs",
        level: Union[int, str] = VERBOSE_LEVEL,
    ):
        self._test_name = test_name
        self._log_dir = log_dir
        self._level = parse_log_level(level)
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
        else:
            for handler in logger.handlers:
                handler.setLevel(self._level)

        return logger

    def set_level(self, level: Union[int, str]) -> None:
        """Dynamically adjust logger and handler levels."""
        resolved = parse_log_level(level)
        self._level = resolved
        self.logger.setLevel(resolved)
        for handler in self.logger.handlers:
            handler.setLevel(resolved)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def verbose(self, message: str) -> None:
        self.logger.log(VERBOSE_LEVEL, message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)
