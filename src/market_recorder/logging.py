"""Minimal logging shim for the scaffolded package."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a named logger without imposing global logging configuration yet."""
    return logging.getLogger(name)