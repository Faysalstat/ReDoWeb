"""Correlation fields (trace_id, request_id, user_id, project_id, tier, ...)
attached to every log line without passing them through call sites -- see
docs/LOGGING.md.

The fields live in ONE mutable dict held by a ContextVar, not one ContextVar
per field, on purpose: FastAPI runs sync dependencies and endpoints in a
threadpool on a *copy* of the request's context, so a plain ContextVar.set()
made inside `get_current_user` would never be seen by the request middleware's
access line. Mutating the shared dict is seen everywhere that request runs.
`scope()` starts a fresh dict (layered on the parent's fields), so binds made
inside a scope never leak out of it.
"""

import contextvars
import uuid
from concurrent.futures import Executor, Future
from contextlib import contextmanager
from typing import Any, Callable, Iterator

_fields: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("log_fields", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def scope(**fields: Any) -> Iterator[dict[str, Any]]:
    """A new set of fields for the duration of the block (one HTTP request,
    one queued job), inheriting whatever the enclosing scope already had."""
    merged = {**(_fields.get() or {}), **_clean(fields)}
    token = _fields.set(merged)
    try:
        yield merged
    finally:
        _fields.reset(token)


def bind(**fields: Any) -> None:
    """Adds fields to the current scope. A no-op outside any scope (a test
    calling a dependency directly, a script) -- starting one there would
    leave the fields stuck on that context for good. Every HTTP request and
    every queued job already runs inside a scope."""
    current = _fields.get()
    if current is not None:
        current.update(_clean(fields))


def current() -> dict[str, Any]:
    return dict(_fields.get() or {})


def trace_id() -> str | None:
    return (_fields.get() or {}).get("trace_id")


def submit_with_context(executor: Executor, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future:
    """executor.submit() that keeps the caller's log fields -- worker threads
    otherwise start with an empty context. Each call takes its own context
    copy, since one Context can't be entered by two threads at once."""
    return executor.submit(contextvars.copy_context().run, fn, *args, **kwargs)


def _clean(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in fields.items() if value is not None}
