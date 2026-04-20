"""Database test helpers.

Provides in-memory SQLite engine and session factory for tests that
need database persistence without touching the filesystem.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.storage.db import create_all_tables


def _set_sqlite_pragmas(dbapi_conn, connection_record):  # noqa: ARG001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_test_engine() -> Engine:
    """Return an in-memory SQLite engine with all tables created.

    Uses StaticPool so all sessions share the same underlying connection,
    which is required for in-memory SQLite across threads (e.g. FastAPI
    TestClient uses anyio threads for async handlers).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    create_all_tables(engine)
    return engine


def create_test_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    """Return a session factory bound to an in-memory test database."""
    if engine is None:
        engine = create_test_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
