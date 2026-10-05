"""Local-testing stand-in for paypal_client: every payment succeeds.

Enabled with REDOWEBS_PAYMENTS_MODE=mock, and only honoured while
REDOWEBS_FRONTEND_URL points at localhost/127.0.0.1 (see is_active()) -- so
a deployed backend can never hand out free credits even if the variable is
left set by mistake.

It exposes the same create_order/capture_order/get_order functions as
paypal_client, so billing_service runs its real code path end to end (the
pending Purchase snapshot, the row lock, capture validation, the
`purchase:{id}` ledger grant) -- only the PayPal HTTP calls are replaced.
Stateless: the order id carries the purchase id and amount, so a capture
reports exactly what the order was created for.
"""

import logging
from urllib.parse import urlparse

from ..config import get_settings
from .paypal_client import CURRENCY, format_amount

logger = logging.getLogger(__name__)

SOURCE = "mock"
_ORDER_PREFIX = "MOCK-"
_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def is_requested() -> bool:
    return get_settings().payments_mode.lower() == "mock"


def is_active() -> bool:
    """Mock mode is requested AND we're clearly running locally."""
    if not is_requested():
        return False
    host = urlparse(get_settings().frontend_url).hostname or ""
    if host not in _LOCAL_HOSTS:
        logger.error(
            "REDOWEBS_PAYMENTS_MODE=mock ignored: REDOWEBS_FRONTEND_URL (%s) is not localhost. "
            "Mock payments are for local testing only.",
            get_settings().frontend_url,
        )
        return False
    return True


def create_order(*, purchase_id: str, amount_cents: int, description: str) -> str:
    logger.warning("MOCK payment: auto-approving order for purchase %s (%s)", purchase_id, description)
    return f"{_ORDER_PREFIX}{purchase_id}-{amount_cents}"


def _completed_order(order_id: str) -> dict:
    body = order_id[len(_ORDER_PREFIX):]
    purchase_id, _, cents = body.rpartition("-")
    return {
        "id": order_id,
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": f"MOCKCAP-{purchase_id}",
                            "status": "COMPLETED",
                            "amount": {"currency_code": CURRENCY, "value": format_amount(int(cents))},
                        }
                    ]
                }
            }
        ],
    }


def capture_order(order_id: str) -> dict:
    return _completed_order(order_id)


def get_order(order_id: str) -> dict:
    return _completed_order(order_id)
