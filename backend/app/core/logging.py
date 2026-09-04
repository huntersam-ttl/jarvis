"""Logging setup for Jarvis.

A redacting logger that never emits secret values. Any field whose name looks
like a credential is masked in log output.
"""
from __future__ import annotations

import logging
import re
from typing import Any

_SECRET_NAME_RE = re.compile(r"(key|secret|token|password|credential)", re.IGNORECASE)
_MASK = "***REDACTED***"


class SecretRedactingFilter(logging.Filter):
    """Mask values whose key names look like secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Redact common secret patterns in free-text messages.
        record.msg = re.sub(
            r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+",
            lambda m: m.group(0).split("=")[0].split(":")[0] + "=" + _MASK,
            msg,
        )
        return True


def get_logger(name: str = "jarvis") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        handler.addFilter(SecretRedactingFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def safe_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of d with secret-looking values masked (for logging)."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if _SECRET_NAME_RE.search(str(k)):
            out[k] = _MASK if v else "(empty)"
        else:
            out[k] = v
    return out
