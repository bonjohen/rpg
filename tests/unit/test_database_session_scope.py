"""Tests for GameOrchestrator._session_scope() and _run_in_session().

Phase 2: verifies commit/rollback semantics and the async executor wrapper.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session, sessionmaker

from server.orchestrator.game_loop import GameOrchestrator
from server.storage.models import CampaignRow
from tests.fixtures.db_helpers import create_test_session_factory

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture()
def session_factory():
    return create_test_session_factory()


@pytest.fixture()
def shared_session_factory():
    """Session factory using a named in-memory DB shared across threads."""
    from server.storage.db import get_engine, create_all_tables

    engine = get_engine(
        "sqlite:///file:test_session_scope?mode=memory&cache=shared&uri=true"
    )
    create_all_tables(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def orch(session_factory):
    return GameOrchestrator(session_factory=session_factory)


# ------------------------------------------------------------------
# _session_scope tests
# ------------------------------------------------------------------


class TestSessionScope:
    """Verify commit, rollback, and error-handling semantics."""

    def test_commits_on_clean_exit(self, orch, session_factory):
        with orch._session_scope() as session:
            row = CampaignRow(
                campaign_id="c1",
                name="Test",
                telegram_group_id=0,
                created_at=_NOW,
            )
            session.add(row)

        # Verify committed — readable in a new session
        with session_factory() as verify:
            found = verify.get(CampaignRow, "c1")
            assert found is not None
            assert found.name == "Test"

    def test_rolls_back_on_exception(self, orch, session_factory):
        with pytest.raises(ValueError, match="boom"):
            with orch._session_scope() as session:
                row = CampaignRow(
                    campaign_id="c2",
                    name="Rollback",
                    telegram_group_id=0,
                    created_at=_NOW,
                )
                session.add(row)
                raise ValueError("boom")

        # Verify NOT committed
        with session_factory() as verify:
            assert verify.get(CampaignRow, "c2") is None

    def test_raises_runtime_error_without_factory(self):
        orch = GameOrchestrator()  # no session_factory
        with pytest.raises(RuntimeError, match="No session_factory configured"):
            with orch._session_scope():
                pass

    def test_yields_a_session_object(self, orch):
        with orch._session_scope() as session:
            assert isinstance(session, Session)


# ------------------------------------------------------------------
# _run_in_session tests
# ------------------------------------------------------------------


class TestRunInSession:
    """Verify the async executor wrapper."""

    def test_runs_sync_fn_and_returns_result(self, shared_session_factory):
        orch = GameOrchestrator(session_factory=shared_session_factory)

        def _work(session: Session) -> str:
            return "done"

        result = asyncio.run(orch._run_in_session(_work))
        assert result == "done"

    def test_commits_after_sync_fn(self, shared_session_factory):
        orch = GameOrchestrator(session_factory=shared_session_factory)

        def _insert(session: Session) -> str:
            row = CampaignRow(
                campaign_id="c3",
                name="Async",
                telegram_group_id=0,
                created_at=_NOW,
            )
            session.add(row)
            return row.campaign_id

        cid = asyncio.run(orch._run_in_session(_insert))
        assert cid == "c3"

        with shared_session_factory() as verify:
            assert verify.get(CampaignRow, "c3") is not None

    def test_rolls_back_on_sync_fn_error(self, shared_session_factory):
        orch = GameOrchestrator(session_factory=shared_session_factory)

        def _fail(session: Session) -> None:
            session.add(
                CampaignRow(
                    campaign_id="c4",
                    name="Fail",
                    telegram_group_id=0,
                    created_at=_NOW,
                )
            )
            raise ValueError("async boom")

        with pytest.raises(ValueError, match="async boom"):
            asyncio.run(orch._run_in_session(_fail))

        with shared_session_factory() as verify:
            assert verify.get(CampaignRow, "c4") is None

    def test_raises_runtime_error_without_factory(self):
        orch = GameOrchestrator()

        async def _go():
            await orch._run_in_session(lambda s: None)

        with pytest.raises(RuntimeError, match="No session_factory configured"):
            asyncio.run(_go())
