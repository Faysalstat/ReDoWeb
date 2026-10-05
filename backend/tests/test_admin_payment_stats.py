from datetime import datetime, timedelta, timezone

from app.models import Purchase, User
from app.services import admin_analytics_service


def _user(db, email):
    user = User(email=email, is_email_verified=True)
    db.add(user)
    db.commit()
    return user


def _purchase(db, user, *, status, source="paypal", created_days_ago=1, refunded_days_ago=None):
    now = datetime.now(timezone.utc)
    db.add(
        Purchase(
            user_id=user.id,
            amount_usd_cents=1000,
            credits_granted=10,
            status=status,
            source=source,
            created_at=now - timedelta(days=created_days_ago),
            refunded_at=now - timedelta(days=refunded_days_ago) if refunded_days_ago is not None else None,
        )
    )
    db.commit()


def test_payment_stats_counts_real_purchases_only(db_session):
    alice = _user(db_session, "alice@example.com")
    bob = _user(db_session, "bob@example.com")
    _purchase(db_session, alice, status="completed")
    _purchase(db_session, alice, status="completed")
    _purchase(db_session, bob, status="completed", created_days_ago=60)
    _purchase(db_session, bob, status="pending", created_days_ago=90)
    _purchase(db_session, bob, status="refunded", refunded_days_ago=2)
    _purchase(db_session, bob, status="refunded", refunded_days_ago=45)
    # Never counted: test payments and admin adjustments.
    _purchase(db_session, bob, status="completed", source="mock")
    _purchase(db_session, bob, status="pending", source="mock")
    _purchase(db_session, bob, status="completed", source="manual_admin")

    stats = admin_analytics_service.payment_stats(db_session, days=30)

    assert stats.purchases_in_range == 2
    assert stats.pending_purchases == 1
    assert stats.refunds_in_range == 1
    assert stats.paying_users == 2
