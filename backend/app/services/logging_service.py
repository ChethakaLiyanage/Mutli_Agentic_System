"""Logging service and PII masking filter for Agent 4."""

from __future__ import annotations

import logging
from .audit_service import mask_pii


class PIIMaskingFilter(logging.Filter):
    """Logging filter that automatically redacts sensitive PII from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)
        return True


def configure_agent_logging(log_level: int = logging.INFO) -> None:
    """Configure logger with standard formatting and PII filter."""
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(PIIMaskingFilter())

    logger = logging.getLogger("app.guidance")
    logger.setLevel(log_level)
    if not logger.handlers:
        logger.addHandler(handler)
