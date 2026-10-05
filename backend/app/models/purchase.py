import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class Purchase(Base):
    """Revenue record.

    `source='manual_admin'` rows are written by the admin dashboard's
    credit-adjustment tool (always `status='completed'`, no PayPal ids).
    `source='paypal'` rows are written by billing_service: created as
    `pending` when the PayPal order is created, with `credits_granted`/
    `amount_usd_cents` snapshotted from the CreditPack at that moment, then
    moved to `completed` (credits granted), `failed` (capture rejected or
    didn't match the snapshot) or `refunded` (marked only -- credits are not
    clawed back automatically, an admin adjusts manually). Revenue
    aggregation only ever counts `completed`.
    """

    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_usd_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_granted: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual_admin")
    credit_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("credit_packs.id"), nullable=True
    )
    paypal_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # Last admin action on this purchase (re-check, take back credits, mark
    # as failed) -- see services/admin_payments_service.py.
    resolved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set on every path that marks the purchase refunded (webhook, a capture
    # that comes back refunded, admin re-check).
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
