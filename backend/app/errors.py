"""Shared helper for turning a caught exception into text safe to store in
Project.rejection_reason / GenerationJob.failure_reason -- both are read
back verbatim by the frontend (ProjectStatusResponse.rejection_reason,
ProjectTierFailure.failure_reason) with no server-side filtering, so
whatever ends up in these fields is shown directly to the end user.

A handful of error types across the pipeline are deliberately hand-authored
to be short, plain-English, and safe to show as-is (CrawlError and its
subclasses, GenerationError, InsufficientCreditsError,
InsufficientDiskSpaceError). Everything else -- a bare OpenRouterError
(which embeds raw API response bodies/model output for debugging, never
meant for an end user), a DB error, or any other unexpected exception --
falls back to a short generic message instead of leaking internals. The
original exception is never actually lost: it's still re-raised, and
queue_worker.py separately records str(exc) on the queued_jobs row for
every failed task regardless of what this returns, so the real error stays
available for debugging."""

from .ai.errors import GenerationError
from .crawler.errors import CrawlError
from .services.storage_capacity_service import InsufficientDiskSpaceError
from .services.wallet_service import InsufficientCreditsError

_SAFE_TO_SHOW_AS_IS = (
    CrawlError,
    GenerationError,
    InsufficientCreditsError,
    InsufficientDiskSpaceError,
)


def user_facing_message(exc: Exception, fallback: str) -> str:
    if isinstance(exc, _SAFE_TO_SHOW_AS_IS):
        return str(exc)
    return fallback
