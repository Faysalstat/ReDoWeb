"""Per-request correlation + one `http.request` log line per request
(replaces uvicorn's access log -- start.sh runs uvicorn with --no-access-log).

Pure ASGI rather than BaseHTTPMiddleware so streamed responses (/preview
static files, ZIP downloads) pass through untouched.

- Takes the browser's X-Request-ID (the Angular interceptor sends one) or
  makes one, uses it as both request_id and trace_id, and echoes it back.
  queue.enqueue() copies trace_id into the job, so the worker's lines for the
  pipeline this request started carry the same id.
- Status polling (GET /projects/{id} every 3s), /health and /preview assets
  only log at DEBUG when they succeed -- at INFO they'd be most of the volume.
"""

import logging
import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import context as log_context

logger = logging.getLogger("app.http")

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

_QUIET_PREFIXES = ("/health", "/preview/", "/favicon.ico")
_QUIET_ROUTES = {"/api/v1/projects/{project_id}"}


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or log_context.new_trace_id()
        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        with log_context.scope(request_id=request_id, trace_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            except Exception:
                logger.exception(
                    "unhandled error on %s %s",
                    scope["method"],
                    scope["path"],
                    extra=_fields(scope, 500, started, event="http.unhandled_exception"),
                )
                raise
            _log_request(scope, status_code, started)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


def _route_template(scope: Scope) -> str:
    # FastAPI's APIRoute puts itself on the scope once matched, so lines group
    # by "/api/v1/projects/{project_id}" rather than one path per project.
    route = scope.get("route")
    return getattr(route, "path", None) or scope["path"]


def _fields(scope: Scope, status_code: int, started: float, event: str = "http.request") -> dict:
    return {
        "event": event,
        "method": scope["method"],
        "route": _route_template(scope),
        "path": scope["path"],
        "status": status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _log_request(scope: Scope, status_code: int, started: float) -> None:
    fields = _fields(scope, status_code, started)
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING if status_code not in (401, 404) else logging.INFO
    elif scope["path"].startswith(_QUIET_PREFIXES) or (
        scope["method"] == "GET" and fields["route"] in _QUIET_ROUTES
    ):
        level = logging.DEBUG
    else:
        level = logging.INFO
    if logger.isEnabledFor(level):
        logger.log(
            level,
            "%s %s -> %s (%.0f ms)",
            fields["method"],
            fields["route"],
            status_code,
            fields["duration_ms"],
            extra=fields,
        )
