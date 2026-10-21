"""Structured logging with sensitive-value redaction.

Never log credentials, authorization headers, API keys, or personal data.
Every log record carries a request/correlation ID so operators can trace a
single request across middleware, services, and the database.
"""

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Correlation ID for the in-flight request.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Query params / headers that must never reach the log stream.
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "auth",
    "cookie",
    "set-cookie",
    "session",
    "sessionid",
    "x-api-key",
    "admin_api_key",
    "csrf",
    "credit_card",
    "aadhaar",
    "phone",
    "email",
}

_SENSITIVE_VALUE_PATTERNS = [
    # Bearer tokens / basic auth
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/=]{8,}"),
    # key=value / "key": "value" style secrets
    re.compile(
        r"(?i)\b(" + "|".join(sorted(_SENSITIVE_KEYS)) + r")\b\s*[=:]\s*[\"']?([^\s\"',;&}]+)",
    ),
]


def redact_text(value: str) -> str:
    """Remove obvious secret material from a free-text string."""
    if not value:
        return value
    redacted = _SENSITIVE_VALUE_PATTERNS[0].sub("[REDACTED]", value)
    for pattern in _SENSITIVE_VALUE_PATTERNS[1:]:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", redacted)
    return redacted


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive keys in a mapping."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


class RequestIdFilter(logging.Filter):
    """Inject the current request correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for machine ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = redact_text(str(value)) if isinstance(value, str) else value
        if record.exc_info:
            # Exception type only - never the traceback/paths in structured mode.
            payload["exception_type"] = getattr(record.exc_info[0], "__name__", "Exception")
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable output for local development."""

    def format(self, record: logging.LogRecord) -> str:
        rid = getattr(record, "request_id", "-")
        base = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} {record.levelname:<8} [{rid}] {record.name}: {redact_text(record.getMessage())}"
        fields = getattr(record, "extra_fields", None)
        if fields:
            base += " " + " ".join(f"{k}={redact_text(str(v))}" for k, v in fields.items())
        return base


def configure_logging() -> None:
    """Install the structured logging handlers. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.LOG_JSON else TextFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    # Replace only our own handler to avoid duplicating output on reload.
    for existing in list(root.handlers):
        if getattr(existing, "_garuda_handler", False):
            root.removeHandler(existing)
    handler._garuda_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL)

    # Uvicorn's own loggers would otherwise bypass our formatter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger that supports the ``extra_fields`` structured attribute."""
    logger = logging.getLogger(name)
    if not hasattr(logger, "garuda_extra"):
        logger.garuda_extra = True  # type: ignore[attr-defined]
    return logger


def new_request_id() -> str:
    """Generate a short correlation ID for a new request."""
    return uuid.uuid4().hex[:16]
