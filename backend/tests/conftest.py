import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import Base
from app.models import (
    AIModelSetting,
    AuthIdentity,
    CreditTransaction,
    CreditWallet,
    Purchase,
    PromptTemplate,
    Tier,
    User,
)


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    """Every test gets a deterministic JWT secret / short token lifetimes,
    bypassing the real .env -- and get_settings' lru_cache is cleared before
    and after so tests never see a stale or leaked-into-prod cached Settings
    instance."""
    monkeypatch.setenv("REDOWEBS_JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("REDOWEBS_GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("REDOWEBS_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("REDOWEBS_JWT_EXPIRE_DAYS", "7")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    """An isolated in-memory SQLite DB with only the auth-related tables
    created -- Project/SubmissionLog use Postgres-only column types (INET)
    that SQLite can't compile, and auth logic doesn't need them."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            AuthIdentity.__table__,
            CreditWallet.__table__,
            CreditTransaction.__table__,
            Purchase.__table__,
            Tier.__table__,
            AIModelSetting.__table__,
            PromptTemplate.__table__,
        ],
    )
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
