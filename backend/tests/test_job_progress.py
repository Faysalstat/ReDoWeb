"""services/job_progress.JobProgress -- step/percent/activity tracking,
tested with an in-memory persist function and a fake clock (no DB)."""

import logging
import uuid

from app.services.job_progress import MAX_LOG_ENTRIES, JobProgress, Step, latest_activity
from app.services.tier_actions_service import public_progress

STEPS = [Step("prepare", "Copying", 0, 10), Step("agent", "Optimizing", 10, 90), Step("save", "Saving", 90, 100)]


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _tracker():
    writes: list[dict] = []
    clock = _Clock()
    tracker = JobProgress(
        uuid.uuid4(),
        STEPS,
        context="[seo test]",
        persist=lambda job_id, state: writes.append(state),
        clock=clock,
    )
    return tracker, writes, clock


def test_steps_percent_and_checklist_progress_in_order():
    tracker, writes, clock = _tracker()

    tracker.start_step("prepare")
    clock.now = 2.0
    tracker.start_step("agent", "3 pages")
    clock.now = 3.5
    tracker.advance(0.5, "Edited about.html: page title")

    state = tracker.state
    assert state["step"] == "agent" and state["label"] == "Optimizing"
    assert state["percent"] == 50  # 10 + (90-10) * 0.5
    assert state["detail"] == "Edited about.html: page title"
    assert [s["status"] for s in state["steps"]] == ["done", "running", "pending"]
    assert state["steps"][0]["seconds"] == 2.0
    assert writes  # persisted


def test_percent_never_goes_backwards_or_past_the_step():
    tracker, _, clock = _tracker()
    tracker.start_step("agent")
    clock.now = 5
    tracker.advance(0.8)
    clock.now = 10
    tracker.advance(0.2)
    assert tracker.state["percent"] == 74
    clock.now = 15
    tracker.advance(5.0)
    assert tracker.state["percent"] == 90


def test_plain_updates_are_throttled_but_steps_and_warnings_always_write():
    tracker, writes, clock = _tracker()
    tracker.start_step("agent")  # forced write
    count = len(writes)
    tracker.advance(0.1)  # same instant -> throttled
    tracker.log("info line")  # throttled too
    assert len(writes) == count
    tracker.log("careful", "warning")  # forced
    assert len(writes) == count + 1
    clock.now = 5
    tracker.advance(0.2)  # interval passed
    assert len(writes) == count + 2


def test_succeed_completes_every_step_and_hits_100():
    tracker, writes, clock = _tracker()
    tracker.start_step("prepare")
    clock.now = 4
    tracker.succeed("12 edits")

    assert tracker.state["status"] == "succeeded"
    assert tracker.state["percent"] == 100
    assert all(s["status"] == "done" for s in tracker.state["steps"])
    assert tracker.state["seconds"] == 4.0
    assert writes[-1]["status"] == "succeeded"


def test_fail_marks_running_step_failed_and_logs_reason(caplog):
    tracker, _, _ = _tracker()
    tracker.start_step("agent")
    with caplog.at_level(logging.WARNING, logger="app.jobs"):
        tracker.fail("The AI service timed out")

    assert tracker.state["status"] == "failed"
    assert tracker.state["steps"][1]["status"] == "failed"
    last = tracker.state["log"][-1]
    assert last["level"] == "error" and last["message"] == "The AI service timed out"
    assert any("[seo test] failed" in r.getMessage() for r in caplog.records)


def test_activity_log_is_capped_keeping_first_entry():
    tracker, _, _ = _tracker()
    tracker.start_step("agent")
    for i in range(MAX_LOG_ENTRIES + 50):
        tracker.log(f"edit {i}")
    log = tracker.state["log"]
    assert len(log) == MAX_LOG_ENTRIES
    assert log[0]["message"].startswith("Optimizing")
    assert log[-1]["message"] == f"edit {MAX_LOG_ENTRIES + 49}"


def test_persist_failure_never_raises(caplog):
    def broken(job_id, state):
        raise RuntimeError("db down")

    tracker = JobProgress(uuid.uuid4(), STEPS, persist=broken)
    with caplog.at_level(logging.ERROR, logger="app.jobs"):
        tracker.start_step("prepare")
    assert any("could not save progress" in r.getMessage() for r in caplog.records)


def test_public_progress_hides_debug_entries_and_limits_activity():
    tracker, _, _ = _tracker()
    tracker.start_step("agent")
    tracker.log("Error: OpenRouter 502 body ...", "debug")
    for i in range(10):
        tracker.log(f"Edited page-{i}.html: page title")

    public = public_progress(tracker.state)

    messages = [e["message"] for e in public["activity"]]
    assert len(messages) == 6
    assert not any("OpenRouter" in m for m in messages)
    assert public["percent"] == tracker.state["percent"]
    assert "log" not in public
    assert latest_activity(None) == [] and public_progress(None) is None
