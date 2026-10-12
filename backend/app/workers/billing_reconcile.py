"""Runs billing_service.reconcile_pending_purchases() -- on a timer from the
queue worker (queue_worker.py, every billing_reconcile_interval_minutes),
or by hand:

    python -m app.workers.billing_reconcile

Re-checks PayPal purchases still `pending` after a few minutes, so a buyer
who approved and closed the tab gets their credits even when the webhook
never arrives (no webhook locally, or a misconfigured one in production).
Safe to run from several workers at once: each purchase is locked
FOR UPDATE SKIP LOCKED and credited under the same `purchase:{id}` ledger
key as the browser capture and the webhook."""

import logging
from datetime import timedelta

from ..config import get_settings
from ..db.session import SessionLocal
from ..logging_config import configure_logging
from ..payments import paypal_client
from ..services.billing_service import ReconcileReport, reconcile_pending_purchases

logger = logging.getLogger(__name__)


def run_reconcile_once() -> ReconcileReport | None:
    """Returns the report, or None when PayPal isn't configured (nothing to
    reconcile against -- e.g. local dev without sandbox credentials)."""
    if not paypal_client.is_configured():
        return None
    settings = get_settings()
    db = SessionLocal()
    try:
        report = reconcile_pending_purchases(
            db,
            min_age=timedelta(minutes=settings.billing_reconcile_min_age_minutes),
            max_age=timedelta(hours=settings.billing_reconcile_max_age_hours),
            limit=settings.billing_reconcile_batch_limit,
        )
    finally:
        db.close()

    if report.checked or report.errors:
        logger.info(
            "billing reconcile: checked %d, skipped %d, errors %d, outcomes %s",
            report.checked,
            report.skipped,
            report.errors,
            report.outcomes,
            extra={
                "event": "billing.reconcile_run",
                "checked": report.checked,
                "skipped": report.skipped,
                "errors": report.errors,
                "outcomes": report.outcomes,
            },
        )
    return report


if __name__ == "__main__":
    configure_logging(service="worker")
    logger.info("billing reconcile finished: %s", run_reconcile_once() or "PayPal not configured, nothing to do")
