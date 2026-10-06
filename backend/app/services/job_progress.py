"""Live progress + activity log for a long-running GenerationJob (currently
the post-purchase SEO pass -- see workers/tasks_seo.py).

One tracker does both kinds of tracking at once:
- **progress** for the UI: current step, percent, a one-line detail, the
  step checklist and a capped activity log, stored as JSON on
  `generation_jobs.progress` (polled by the frontend through the project
  status response, and shown in full on the admin project page);
- **logs** for operators: every step change and activity entry is also
  written to the Python logger with the job/project/tier context, so the
  worker's stdout (Railway's log stream) tells the same story.

Writes go through their own short DB session (not the task's), so progress
lands immediately while the task's own transaction is still open, and the
task's later commit never overwrites it (SQLAlchemy only updates columns it
changed). Persisting is injectable, so the tracker is unit-testable without
a database. A failing progress write never fails the job itself.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import update

from ..db.session import SessionLocal
from ..models import GenerationJob

logger = logging.getLogger("app.jobs")

MAX_LOG_ENTRIES = 200
# Minimum seconds between DB writes for plain percent/detail updates --
# step changes, log entries at warning+ and the final state always write.
MIN_WRITE_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    # The share of the overall bar this step covers, as [start, end) percent.
    start: int
    end: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def persist_to_db(job_id: uuid.UUID, progress: dict) -> None:
    session = SessionLocal()
    try:
        session.execute(update(GenerationJob).where(GenerationJob.id == job_id).values(progress=progress))
        session.commit()
    finally:
        session.close()


class JobProgress:
    def __init__(
        self,
        job_id: uuid.UUID | str,
        steps: list[Step],
        *,
        context: str = "",
        persist: Callable[[uuid.UUID, dict], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.job_id = uuid.UUID(str(job_id))
        self.steps = steps
        self.context = context
        self._persist = persist or persist_to_db
        self._clock = clock
        self._started = clock()
        self._last_write = float("-inf")
        self._step_index = -1
        self._step_started = self._started
        self.state: dict = {
            "status": "running",
            "step": None,
            "label": "Starting…",
            "percent": 0,
            "detail": "",
            "steps": [{"key": s.key, "label": s.label, "status": "pending"} for s in steps],
            "log": [],
            "started_at": _now(),
            "updated_at": _now(),
        }

    # -- public API ---------------------------------------------------------

    def start_step(self, key: str, detail: str = "") -> None:
        index = next(i for i, step in enumerate(self.steps) if step.key == key)
        now = self._clock()
        if self._step_index >= 0:
            previous = self.steps[self._step_index]
            self.state["steps"][self._step_index]["status"] = "done"
            self.state["steps"][self._step_index]["seconds"] = round(now - self._step_started, 1)
            logger.info("%s step %s done in %.1fs", self.context, previous.key, now - self._step_started)
        self._step_index = index
        self._step_started = now
        step = self.steps[index]
        self.state["steps"][index]["status"] = "running"
        self.state.update(step=step.key, label=step.label, percent=step.start, detail=detail)
        logger.info("%s step %s started%s", self.context, step.key, f": {detail}" if detail else "")
        self._append_log("info", f"{step.label}{f' — {detail}' if detail else ''}", echo=False)
        self._write(force=True)

    def advance(self, fraction: float, detail: str | None = None) -> None:
        """Progress within the current step, 0.0-1.0 of that step's share."""
        if self._step_index < 0:
            return
        step = self.steps[self._step_index]
        fraction = min(max(fraction, 0.0), 1.0)
        percent = step.start + int((step.end - step.start) * fraction)
        self.state["percent"] = max(self.state["percent"], min(percent, step.end))
        if detail is not None:
            self.state["detail"] = detail
        self._write()

    def log(self, message: str, level: str = "info") -> None:
        self._append_log(level, message)
        self._write(force=level in ("warning", "error"))

    def succeed(self, detail: str = "") -> None:
        self._finish("succeeded", "Done", detail)

    def fail(self, reason: str) -> None:
        if self._step_index >= 0:
            self.state["steps"][self._step_index]["status"] = "failed"
        self._append_log("error", reason)
        self._finish("failed", "Failed", reason)

    # -- internals ----------------------------------------------------------

    def _finish(self, status: str, label: str, detail: str) -> None:
        now = self._clock()
        if status == "succeeded":
            for index, entry in enumerate(self.state["steps"]):
                if entry["status"] in ("pending", "running"):
                    entry["status"] = "done"
                    if index == self._step_index:
                        entry["seconds"] = round(now - self._step_started, 1)
        total = round(now - self._started, 1)
        self.state.update(status=status, label=label, detail=detail, seconds=total)
        if status == "succeeded":
            self.state["percent"] = 100
        logger.log(
            logging.INFO if status == "succeeded" else logging.WARNING,
            "%s %s in %.1fs%s",
            self.context,
            status,
            total,
            f": {detail}" if detail else "",
        )
        self._write(force=True)

    def _append_log(self, level: str, message: str, echo: bool = True) -> None:
        self.state["log"].append({"at": _now(), "level": level, "message": message})
        if len(self.state["log"]) > MAX_LOG_ENTRIES:
            # Keep the first entry (run start) and the most recent ones.
            self.state["log"] = self.state["log"][:1] + self.state["log"][-(MAX_LOG_ENTRIES - 1):]
        if echo:
            logger.log(getattr(logging, level.upper(), logging.INFO), "%s %s", self.context, message)

    def _write(self, force: bool = False) -> None:
        now = self._clock()
        if not force and now - self._last_write < MIN_WRITE_INTERVAL_SECONDS:
            return
        self._last_write = now
        self.state["updated_at"] = _now()
        try:
            self._persist(self.job_id, dict(self.state))
        except Exception:  # noqa: BLE001 -- progress is best-effort, never fails the job
            logger.exception("%s could not save progress", self.context)


def latest_activity(progress: dict | None, limit: int = 6, min_level: str = "info") -> list[dict]:
    """The last few user-facing activity entries (for the project status
    response -- the full log stays on the job for admins)."""
    if not progress:
        return []
    order = {"debug": 0, "info": 1, "warning": 2, "error": 3}
    floor = order.get(min_level, 1)
    entries = [e for e in progress.get("log", []) if order.get(e.get("level", "info"), 1) >= floor]
    return entries[-limit:]
