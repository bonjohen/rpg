"""Database test helpers.

Provides in-memory SQLite engine and session factory for tests that
need database persistence without touching the filesystem.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from server.storage.db import get_engine, create_all_tables


def create_test_engine() -> Engine:
    """Return an in-memory SQLite engine with all tables created."""
    engine = get_engine("sqlite:///:memory:")
    create_all_tables(engine)
    return engine


def create_test_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    """Return a session factory bound to an in-memory test database."""
    if engine is None:
        engine = create_test_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
