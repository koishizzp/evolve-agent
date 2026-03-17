import logging
from pathlib import Path

try:
    from loguru import logger as _loguru_logger
except Exception:  # noqa: BLE001
    _loguru_logger = None


class _CompatLogger:
    """Small subset of the loguru interface used in this project."""

    def __init__(self):
        self._logger = logging.getLogger("evolve-agent")
        self._logger.handlers.clear()
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    def remove(self):
        self._logger.handlers.clear()

    def add(self, sink, level="INFO", **kwargs):
        lvl = getattr(logging, level.upper(), logging.INFO)
        if callable(sink):
            class FuncHandler(logging.Handler):
                def emit(self, record):
                    sink(self.format(record) + "\n")

            handler = FuncHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        else:
            Path(sink).parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(sink, encoding=kwargs.get("encoding", "utf-8"))
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        handler.setLevel(lvl)
        self._logger.addHandler(handler)

    def debug(self, msg, *args):
        self._logger.debug(msg, *args)

    def info(self, msg, *args):
        self._logger.info(msg, *args)

    def error(self, msg, *args):
        self._logger.error(msg, *args)

    def exception(self, msg, *args):
        self._logger.exception(msg, *args)


logger = _loguru_logger if _loguru_logger is not None else _CompatLogger()


def setup_logger(verbose: bool = False, log_file: str | None = None) -> None:
    """Configure a loguru-compatible logger."""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(lambda msg: print(msg, end=""), level=level)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=level, rotation="10 MB", encoding="utf-8")
