"""Production logging plumbing (docs/LOGGING.md): redaction, correlation
fields, the JSON event shape, trace propagation through the queue, the
request middleware, and the Axiom shipper's never-block guarantee. No DB, no
network."""

import contextvars
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.logging_config import ContextFilter, JsonFormatter, TextFormatter, build_event
from app.observability import context as log_context
from app.observability.axiom import AxiomHandler
from app.observability.middleware import RequestContextMiddleware
from app.observability.redaction import MASK, redact_text, redact_value
from app.workers.queue import TRACE_KEY, enqueue

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"


def _record(msg="hello", level=logging.INFO, **extra) -> logging.LogRecord:
    record = logging.getLogger("test").makeRecord("test", level, __file__, 1, msg, (), None, extra=extra)
    ContextFilter().filter(record)
    return record


# -- redaction ---------------------------------------------------------------


def test_redact_text_masks_jwts_bearer_and_openrouter_keys():
    text = f"token {JWT} header Bearer abcdefghijklmnop key sk-or-v1-1234567890abcdef"
    redacted = redact_text(text)
    assert JWT not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "sk-or-v1-1234567890abcdef" not in redacted


def test_redact_text_masks_secret_pairs_in_free_text():
    redacted = redact_text('{"access_token": "A21AAF-secret", "status": "ok"} ?refresh_token=xyz123&x=1')
    assert "A21AAF-secret" not in redacted
    assert "xyz123" not in redacted
    assert '"status": "ok"' in redacted
    assert "x=1" in redacted


def test_redact_value_masks_sensitive_keys_but_keeps_token_counts():
    assert redact_value("refresh_token", "abc") == MASK
    assert redact_value("Authorization", "Basic x") == MASK
    assert redact_value("openrouter_api_key", "k") == MASK
    assert redact_value("prompt_tokens", 1234) == 1234
    assert redact_value("max_tokens", 16000) == 16000
    assert redact_value("headers", {"cookie": "sid=1", "accept": "json"}) == {"cookie": MASK, "accept": "json"}


# -- context + event shape -----------------------------------------------------


def test_event_includes_context_extras_and_is_redacted():
    with log_context.scope(trace_id="t1", project_id="p1"):
        record = _record(f"auth {JWT}", event="wallet.spend", duration_ms=12, token="secret-value")
    event = build_event(record)
    assert event["trace_id"] == "t1"
    assert event["project_id"] == "p1"
    assert event["event"] == "wallet.spend"
    assert event["duration_ms"] == 12
    assert event["token"] == MASK
    assert JWT not in event["message"]
    assert "log_context" not in event
    json.loads(JsonFormatter().format(record))  # one valid JSON line


def test_context_is_snapshotted_when_the_record_is_created():
    with log_context.scope(project_id="p1"):
        record = _record()
    # The scope has ended; a handler formatting later must still see p1.
    assert build_event(record)["project_id"] == "p1"


def test_scope_does_not_leak_binds_to_the_parent():
    with log_context.scope(trace_id="outer"):
        with log_context.scope(task="inner"):
            log_context.bind(tier="pro")
            assert log_context.current() == {"trace_id": "outer", "task": "inner", "tier": "pro"}
        assert log_context.current() == {"trace_id": "outer"}
    assert log_context.current() == {}


def test_bind_inside_a_copied_context_is_seen_by_the_request():
    # FastAPI runs sync dependencies on a *copy* of the request context --
    # the shared dict is what makes get_current_user's bind visible outside.
    with log_context.scope(request_id="r1"):
        contextvars.copy_context().run(log_context.bind, user_id="u1")
        assert log_context.current()["user_id"] == "u1"


def test_submit_with_context_keeps_fields_in_pool_threads():
    with log_context.scope(project_id="p9"), ThreadPoolExecutor(max_workers=2) as executor:
        futures = [log_context.submit_with_context(executor, log_context.current) for _ in range(4)]
        assert all(f.result()["project_id"] == "p9" for f in futures)


def test_text_format_appends_correlation_tags():
    with log_context.scope(trace_id="abcdef1234567890", tier="pro"):
        line = TextFormatter().format(_record("done"))
    assert line.endswith("(trace_id=abcdef123456 tier=pro)")


# -- trace propagation through the queue --------------------------------------


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_enqueue_carries_the_current_trace_id():
    db = _FakeSession()
    with log_context.scope(trace_id="trace-1"):
        job = enqueue(db, "run_crawl", {"project_id": "p1"})
    assert job.payload == {"project_id": "p1", TRACE_KEY: "trace-1"}


def test_enqueue_without_a_trace_leaves_the_payload_alone():
    payload = {"project_id": "p1"}
    job = enqueue(_FakeSession(), "run_crawl", payload)
    assert job.payload == {"project_id": "p1"}
    assert payload == {"project_id": "p1"}  # caller's dict never mutated


# -- request middleware ---------------------------------------------------------


def _app():
    app = FastAPI()

    def fake_user():
        log_context.bind(user_id="user-42")

    @app.get("/things/{thing_id}")
    def get_thing(thing_id: str, _=Depends(fake_user)):
        logging.getLogger("app.test").info("inside")
        return {"trace": log_context.trace_id()}

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    app.add_middleware(RequestContextMiddleware)
    return app


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self.addFilter(ContextFilter())

    def emit(self, record):
        self.records.append(record)


def _capturing():
    handler = _Capture()
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    return handler, lambda: (root.removeHandler(handler), root.setLevel(old_level))


def test_middleware_echoes_request_id_and_logs_route_status_and_user():
    handler, restore = _capturing()
    try:
        response = TestClient(_app()).get("/things/7", headers={"X-Request-ID": "req-abcdef12"})
    finally:
        restore()
    assert response.headers["x-request-id"] == "req-abcdef12"
    assert response.json() == {"trace": "req-abcdef12"}
    access = [r for r in handler.records if getattr(r, "event", None) == "http.request"]
    assert len(access) == 1
    event = build_event(access[0])
    assert event["route"] == "/things/{thing_id}"
    assert event["status"] == 200
    assert event["user_id"] == "user-42"
    assert event["trace_id"] == "req-abcdef12"
    inside = next(r for r in handler.records if r.getMessage() == "inside")
    assert build_event(inside)["request_id"] == "req-abcdef12"


def test_middleware_replaces_an_invalid_incoming_request_id():
    response = TestClient(_app()).get("/things/7", headers={"X-Request-ID": "bad id\nwith newline"})
    assert response.headers["x-request-id"] != "bad id\nwith newline"
    assert len(response.headers["x-request-id"]) == 32


def test_middleware_logs_unhandled_errors_with_the_request_id():
    handler, restore = _capturing()
    try:
        response = TestClient(_app(), raise_server_exceptions=False).get("/boom")
    finally:
        restore()
    assert response.status_code == 500
    errors = [r for r in handler.records if getattr(r, "event", None) == "http.unhandled_exception"]
    assert len(errors) == 1
    event = build_event(errors[0])
    assert event["error_type"] == "RuntimeError"
    assert event["request_id"]


# -- Axiom shipper ---------------------------------------------------------------


def test_axiom_handler_drops_instead_of_blocking_when_full():
    sent: list[list[dict]] = []
    handler = AxiomHandler(build_event, "http://x", "t", transport=sent.append, max_queue=2, start_thread=False)
    for i in range(5):
        handler.emit(_record(f"line {i}"))
    assert handler.dropped == 3
    handler.flush()
    assert [e["message"] for e in sent[0]] == ["line 0", "line 1"]
    assert sent[0][0]["_time"] == sent[0][0]["timestamp"]


def test_axiom_handler_survives_a_failing_transport():
    def broken(batch):
        raise ConnectionError("axiom down")

    handler = AxiomHandler(build_event, "http://x", "t", transport=broken, start_thread=False)
    handler.emit(_record())
    handler.flush()  # must not raise
    assert handler.dropped == 1
