"""Ships log events to Axiom's HTTP ingest API from a background thread.

Built so the log archive can never hurt the app: emit() only puts the event
on a bounded in-memory queue (never blocks, drops when full), and a daemon
thread posts batches every few seconds. If Axiom is slow or down, batches are
dropped and counted, nothing retries forever, and nothing is logged through
the logging system from the shipper thread (that would feed itself).
Each process (API, worker) ships its own lines; Railway's stdout log stays
the primary, complete copy.
"""

import atexit
import json
import logging
import queue
import sys
import threading
import time
from typing import Any, Callable

import httpx

MAX_QUEUE = 10_000
BATCH_SIZE = 500
FLUSH_INTERVAL_SECONDS = 5.0
POST_TIMEOUT_SECONDS = 10.0


Transport = Callable[[list[dict[str, Any]]], None]


class AxiomHandler(logging.Handler):
    def __init__(
        self,
        to_event: Callable[[logging.LogRecord], dict[str, Any]],
        url: str,
        token: str,
        *,
        transport: Transport | None = None,
        max_queue: int = MAX_QUEUE,
        flush_interval: float = FLUSH_INTERVAL_SECONDS,
        start_thread: bool = True,
    ):
        super().__init__()
        self._to_event = to_event
        self._url = url
        self._token = token
        self._transport = transport or self._post
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=max_queue)
        self._flush_interval = flush_interval
        self._stop = threading.Event()
        self.dropped = 0
        self._last_complaint = 0.0
        self._thread: threading.Thread | None = None
        if start_thread:
            self._thread = threading.Thread(target=self._run, name="axiom-shipper", daemon=True)
            self._thread.start()
            atexit.register(self.close)

    # -- logging.Handler ------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        if self._thread is not None and threading.get_ident() == self._thread.ident:
            return  # never ship the shipper's own (e.g. httpx) records
        try:
            event = self._to_event(record)
            event["_time"] = event.get("timestamp")
            self._queue.put_nowait(event)
        except queue.Full:
            self.dropped += 1
        except Exception:  # noqa: BLE001 -- a log line must never raise into app code
            self.dropped += 1

    def close(self) -> None:
        if not self._stop.is_set():
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=FLUSH_INTERVAL_SECONDS + POST_TIMEOUT_SECONDS)
            self.flush()
        super().close()

    def flush(self) -> None:
        while self._ship_one_batch():
            pass

    # -- internals ------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.wait(self._flush_interval):
            while self._ship_one_batch():
                pass

    def _ship_one_batch(self) -> bool:
        """Sends up to BATCH_SIZE queued events; False when the queue was empty."""
        batch: list[dict[str, Any]] = []
        while len(batch) < BATCH_SIZE:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not batch:
            return False
        try:
            self._transport(batch)
        except Exception as exc:  # noqa: BLE001
            self.dropped += len(batch)
            self._complain(f"axiom: dropped {len(batch)} log events ({type(exc).__name__}: {exc})")
            return False
        if self.dropped:
            self._complain(f"axiom: {self.dropped} log events dropped so far (queue full or send failed)")
        return len(batch) == BATCH_SIZE

    def _post(self, batch: list[dict[str, Any]]) -> None:
        response = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            content=json.dumps(batch, ensure_ascii=False, default=str),
            timeout=POST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    def _complain(self, message: str) -> None:
        # At most once a minute, straight to stdout (bypassing logging).
        now = time.monotonic()
        if now - self._last_complaint >= 60:
            self._last_complaint = now
            print(json.dumps({"level": "warning", "logger": "app.observability.axiom", "message": message}),
                  file=sys.__stdout__, flush=True)
