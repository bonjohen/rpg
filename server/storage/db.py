"""Database engine and session factory.

Usage:
    from server.storage.db import get_engine, get_session_factory, create_all_tables

    engine = get_engine("sqlite:///game.db")
    create_all_tables(engine)
    SessionLocal = get_session_factory(engine)

    with SessionLocal() as session:
        ...
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from server.storage.models import Base


def _set_sqlite_pragmas(dbapi_conn, connection_record):  # noqa: ARG001
    """Set production-ready SQLite pragmas on every connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_engine(database_url: str | None = None) -> Engine:
    """Return a SQLAlchemy engine.

    Falls back to DATABASE_URL env var, then to a local SQLite file.
    """
    url = database_url or os.environ.get("DATABASE_URL", "sqlite:///rpg.db")
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args, echo=False)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_all_tables(engine: Engine) -> None:
    """Create all tables defined in the ORM models (idempotent)."""
    Base.metadata.create_all(engine)


def drop_all_tables(engine: Engine) -> None:
    """Drop all tables. Used only in tests."""
    Base.metadata.drop_all(engine)
