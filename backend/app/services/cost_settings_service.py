"""Admin-editable global cost-gate settings (see
docs/generation-cost-gate-plan.md): the USD threshold that triggers the
pre-generation cost-approval gate in tasks_blueprint.py, and the USD-per-
credit rate used to translate an estimated cost into a required wallet
balance. Same DB-wins-over-config.py-default shape as
model_config_service.get_vision_model / AIModelSetting, but for a float
value instead of a model id -- see models/cost_setting.py.
"""

import uuid

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.session import SessionLocal
from ..models import CostSetting

GENERATION_COST_ALERT_USD_KEY = "generation_cost_alert_usd"
USD_PER_CREDIT_KEY = "usd_per_credit"


def _with_session(db: Session | None, fn):
    if db is not None:
        return fn(db)
    session = SessionLocal()
    try:
        return fn(session)
    finally:
        session.close()


def _get_value(key: str, default: float, db: Session | None) -> float:
    def _query(session: Session) -> float | None:
        row = session.get(CostSetting, key)
        return row.value if row is not None else None

    override = _with_session(db, _query)
    return override if override is not None else default


def _set_value(key: str, value: float, admin_id: uuid.UUID, db: Session | None) -> CostSetting:
    """Admin write path -- upserts the cost_settings row keyed `key`. Unlike
    the read helpers above, a self-opened session (db=None) commits before
    closing, since a write must not be silently lost just because the
    caller didn't pass an existing session."""
    owns_session = db is None
    session = db if db is not None else SessionLocal()
    try:
        row = session.get(CostSetting, key)
        if row is None:
            row = CostSetting(key=key, value=value, updated_by_admin_id=admin_id)
            session.add(row)
        else:
            row.value = value
            row.updated_by_admin_id = admin_id
        session.flush()
        if owns_session:
            session.commit()
        return row
    finally:
        if owns_session:
            session.close()


def get_generation_cost_alert_usd(db: Session | None = None) -> float:
    return _get_value(GENERATION_COST_ALERT_USD_KEY, get_settings().generation_cost_alert_usd_default, db)


def set_generation_cost_alert_usd(value: float, admin_id: uuid.UUID, db: Session | None = None) -> CostSetting:
    return _set_value(GENERATION_COST_ALERT_USD_KEY, value, admin_id, db)


def get_usd_per_credit(db: Session | None = None) -> float:
    return _get_value(USD_PER_CREDIT_KEY, get_settings().usd_per_credit_default, db)


def set_usd_per_credit(value: float, admin_id: uuid.UUID, db: Session | None = None) -> CostSetting:
    return _set_value(USD_PER_CREDIT_KEY, value, admin_id, db)
