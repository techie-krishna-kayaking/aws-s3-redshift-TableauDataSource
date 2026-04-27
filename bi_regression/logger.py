"""
logger.py — Centralised Rich-powered console + optional file logger.
"""
import logging
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

_console = Console()

# We keep a registry of loggers so we can add file handlers to existing ones later
_logger_registry: dict = {}


def get_logger(name: str, log_file: Path = None) -> logging.Logger:
    """
    Return (or create) a named logger with Rich console output.
    Pass log_file to also write to a file (e.g., after the run directory is created).
    """
    if name not in _logger_registry:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        rich_handler = RichHandler(
            console=_console,
            rich_tracebacks=True,
            markup=True,
            show_path=False,
            log_time_format="[%H:%M:%S]",
        )
        rich_handler.setLevel(logging.DEBUG)
        logger.addHandler(rich_handler)
        _logger_registry[name] = logger
    else:
        logger = _logger_registry[name]

    # Optionally add a file handler (idempotent — checks for existing FileHandlers)
    if log_file is not None:
        already_has_file = any(
            isinstance(h, logging.FileHandler) for h in logger.handlers
        )
        if not already_has_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(fh)

    return logger
