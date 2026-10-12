"""One logging setup shared by the API (main.py) and the queue worker
(queue_worker.py) -- on Railway both run in one container via start.sh, so
their output lands in a single interleaved log stream and needs the same
shape to be readable/filterable there.

Everything goes to stdout: Railway tags every stderr line as error-level,
which made uvicorn's normal INFO startup/access lines show up as errors.

Every line carries the correlation fields from observability/context.py
(trace_id, project_id, tier, user_id, ...) plus any `extra=` fields the call
site passed (`event`, `duration_ms`, ...), and is redacted before it leaves
the process. With REDOWEBS_AXIOM_TOKEN set, the same events are also shipped
to Axiom (observability/axiom.py). Field reference: docs/LOGGING.md."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .config import get_settings
from .observability import context as log_context
from .observability.axiom import AxiomHandler
from .observability.redaction import redact_text, redact_value

# Attributes every LogRecord has -- anything else on a record came from
# `extra=` and is copied into the event.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "color_message",  # uvicorn's ANSI-coloured duplicate of the message
    "taskName",
}

# Chatty third-party loggers: their INFO lines are per-request noise
# ("HTTP Request: POST ...") that would also multiply log volume.
_QUIET_LOGGERS = ("httpx", "httpcore", "sqlalchemy.engine", "PIL", "urllib3", "multipart")

# Fields shown inline in the text format, in this order.
_TEXT_CONTEXT_KEYS = ("worker_id", "trace_id", "project_id", "tier", "job_id", "user_id")

_static_fields: dict[str, Any] = {}


def build_event(record: logging.LogRecord) -> dict[str, Any]:
    """The JSON-serialisable event for one record: standard fields, static
    process fields, correlation fields, then `extra=` fields -- redacted."""
    event: dict[str, Any] = {
        "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
        "level": record.levelname.lower(),
        "logger": record.name,
        "message": redact_text(record.getMessage()),
        **_static_fields,
    }
    event.update(getattr(record, "log_context", None) or {})
    for key, value in record.__dict__.items():
        if key not in _STANDARD_ATTRS and key != "log_context" and not key.startswith("_"):
            event[key] = value
    for key in list(event):
        if key not in ("timestamp", "level", "logger", "message"):
            event[key] = redact_value(key, event[key])
    if record.exc_info:
        event["traceback"] = redact_text(logging.Formatter().formatException(record.exc_info))
        event.setdefault("error_type", record.exc_info[0].__name__ if record.exc_info[0] else None)
    return event


class ContextFilter(logging.Filter):
    """Snapshots the correlation fields onto the record at emit time (a
    handler that formats later, like Axiom's, would otherwise read a context
    that has since changed)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "log_context"):
            record.log_context = log_context.current()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(build_event(record), ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = redact_text(super().format(record))
        fields = {**_static_fields, **(getattr(record, "log_context", None) or {})}
        tags = " ".join(f"{key}={str(fields[key])[:12]}" for key in _TEXT_CONTEXT_KEYS if key in fields)
        return f"{line} ({tags})" if tags else line


def resolve_environment() -> str:
    return get_settings().environment or os.environ.get("RAILWAY_ENVIRONMENT_NAME") or "development"


def configure_logging(service: str = "api", **static_fields: str) -> None:
    """`service` is "api" or "worker"; `static_fields` (e.g. worker_id) are
    added to every line this process writes."""
    settings = get_settings()

    _static_fields.clear()
    _static_fields.update(service=service, env=resolve_environment(), **static_fields)
    release = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "")[:12]
    if release:
        _static_fields["release"] = release

    context_filter = ContextFilter()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(context_filter)
    handler.setFormatter(JsonFormatter() if settings.log_format.lower() == "json" else TextFormatter())
    handlers: list[logging.Handler] = [handler]

    if settings.axiom_token:
        axiom = AxiomHandler(
            build_event,
            settings.axiom_ingest_url.format(dataset=settings.axiom_dataset),
            settings.axiom_token,
        )
        axiom.addFilter(context_filter)
        handlers.append(axiom)

    root = logging.getLogger()
    for old in root.handlers:
        if isinstance(old, AxiomHandler):
            old.close()
    root.handlers = handlers
    root.setLevel(settings.log_level.upper())

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # uvicorn installs its own stderr handlers before importing the app --
    # drop them so its startup lines go through the handlers above. Its
    # access log is replaced by observability/middleware.py's http.request
    # line (start.sh passes --no-access-log).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
