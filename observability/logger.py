"""
Structured logging configuration using structlog.

Outputs JSON in production, human-readable in dev.
Compatible with Datadog, Splunk, and CloudWatch log ingestion.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_output: bool | None = None) -> None:
    """
    Configure structlog for the process.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: Force JSON output. Auto-detects TTY if None.
    """
    if json_output is None:
        # isatty() can raise on some Windows CI environments (no real TTY attached)
        try:
            json_output = not sys.stdout.isatty()
        except Exception:  # noqa: BLE001
            json_output = True  # default to JSON in unknown/CI environments

    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger with the given name."""
    return structlog.get_logger(name)
