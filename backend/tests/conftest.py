"""Pytest fixtures for the GRC backend.

Must set DATABASE_URL before importing anything under app.* -- app/database.py
creates its engine from settings.database_url at import time, so this has to
happen before that module (or anything that imports it, e.g. app.main) is
ever loaded. Pytest always loads conftest.py before collecting test modules,
so this ordering is reliable.
"""

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://saibdroubi@localhost:5432/grc_test"

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import make_url

from app import models  # noqa: F401  -- registers tables on Base.metadata
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.main import app

# Never let a real ANTHROPIC_API_KEY (e.g. picked up from a developer's .env)
# make these tests call out to Claude -- propose_remediation and friends fall
# back to a deterministic heuristic when this is empty, which is what every
# test in this suite relies on for repeatable results.
settings.anthropic_api_key = ""

_url = make_url(os.environ["DATABASE_URL"])
_TEST_DB_NAME = _url.database


def _admin_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=_url.host,
        port=_url.port,
        user=_url.username,
        password=_url.password,
        dbname="postgres",
        autocommit=True,
    )


def _ensure_test_database_exists() -> None:
    with _admin_connection() as conn:
        try:
            conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
        except psycopg.errors.DuplicateDatabase:
            pass


def _ensure_pgvector_extension() -> None:
    conn = psycopg.connect(
        host=_url.host,
        port=_url.port,
        user=_url.username,
        password=_url.password,
        dbname=_TEST_DB_NAME,
        autocommit=True,
    )
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Fresh schema on grc_test for the whole test run -- bypasses Alembic on
    purpose: these tests start from an empty schema, not an upgrade path, so
    migration history isn't what's under test here."""
    _ensure_test_database_exists()
    _ensure_pgvector_extension()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture
def db_session(_test_database):
    """One DB session per test, isolated via the standard SQLAlchemy
    SAVEPOINT pattern. Service-layer code calls db.commit() internally (it
    has to -- routers and the chat agent share it), so a plain outer
    transaction would get committed out from under us; instead we nest a
    SAVEPOINT and transparently restart it every time an inner commit ends
    it, then roll back the real outer transaction once the test is done."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = SessionLocal(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # base_url must be https: the session cookie is Secure, and httpx's
    # cookie jar silently drops Secure cookies on http:// requests, which
    # would make every authenticated request after login look like a
    # missing-cookie 401 instead of actually exercising auth.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
