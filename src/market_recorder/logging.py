"""Recorder logging configuration helpers."""

from __future__ import annotations

import logging
import time


class UtcFormatter(logging.Formatter):
    """A logging formatter that emits UTC timestamps."""

    converter = time.gmtime


def configure_logging(level: str, *, structured: bool = False) -> None:
    """Configure root logging for recorder commands and runtime checks."""
    normalized_level = level.upper()
    if not hasattr(logging, normalized_level):
        raise ValueError(f"Unsupported log level: {level!r}")

    log_format = (
        "ts=%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s"
        if structured
        else "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(UtcFormatter(log_format, datefmt="%Y-%m-%dT%H:%M:%SZ"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, normalized_level))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger after logging has been configured."""
    return logging.getLogger(name)