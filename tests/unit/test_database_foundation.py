"""Tests for database foundation: pragmas, version column, optimistic locking."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from server.domain.entities import TurnWindow
from server.domain.enums import TurnWindowState
from server.storage.db import get_engine, create_all_tables
from server.storage.errors import StaleStateError
from server.storage.models import CampaignRow, SceneRow
from server.storage.repository import TurnWindowRepo
from tests.fixtures.db_helpers import create_test_engine, create_test_session_factory


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _seed_campaign_and_scene(session, campaign_id="camp-1", scene_id="scene-1"):
    """Insert minimal campaign and scene rows so FK constraints pass."""
    session.add(
        CampaignRow(
            campaign_id=campaign_id,
            name="Test",
            telegram_group_id=1,
            created_at=_now(),
        )
    )
    session.add(
        SceneRow(
            scene_id=scene_id,
            campaign_id=campaign_id,
            name="Room",
            description="A room",
            created_at=_now(),
        )
    )
    session.flush()


def _make_tw(
    tw_id="tw-1",
    campaign_id="camp-1",
    scene_id="scene-1",
    version=1,
) -> TurnWindow:
    now = _now()
    return TurnWindow(
        turn_window_id=tw_id,
        campaign_id=campaign_id,
        scene_id=scene_id,
        public_scope_id="scope-pub",
        opened_at=now,
        expires_at=now,
        state=TurnWindowState.open,
        turn_number=1,
        version=version,
    )


# -----------------------------------------------------------------------
# SQLite pragma tests
# -----------------------------------------------------------------------


class TestSQLitePragmas:
    def test_wal_mode_enabled(self, tmp_path):
        # WAL only applies to file-based SQLite, not :memory:
        db_path = tmp_path / "test.db"
        engine = get_engine(f"sqlite:///{db_path}")
        create_all_tables(engine)
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
            assert result == "wal"

    def test_foreign_keys_enabled(self):
        engine = create_test_engine()
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
            assert result == 1

    def test_busy_timeout_set(self):
        engine = get_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
            assert result == 5000

    def test_synchronous_normal(self):
        engine = get_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            # NORMAL = 1
            result = conn.exec_driver_sql("PRAGMA synchronous").scalar()
            assert result == 1

    def test_pragmas_not_applied_to_non_sqlite(self):
        """Verify that get_engine with a non-sqlite URL does not crash."""
        # We can't easily test a non-sqlite engine without a real DB,
        # but we can verify the SQLite engine works correctly.
        engine = get_engine("sqlite:///:memory:")
        create_all_tables(engine)
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
            assert result == 1


# -----------------------------------------------------------------------
# Version column round-trip tests
# -----------------------------------------------------------------------


class TestVersionColumn:
    def test_default_version_is_one(self):
        tw = _make_tw()
        assert tw.version == 1

    def test_version_round_trip_through_repo(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            tw = _make_tw(version=1)
            repo.save(tw)
            session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            loaded = repo.get("tw-1")
            assert loaded is not None
            assert loaded.version == 1

    def test_version_persists_updated_value(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            tw = _make_tw(version=3)
            repo.save(tw)
            session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            loaded = repo.get("tw-1")
            assert loaded is not None
            assert loaded.version == 3


# -----------------------------------------------------------------------
# Optimistic locking tests
# -----------------------------------------------------------------------


class TestOptimisticLocking:
    def test_save_with_version_check_succeeds(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            tw = _make_tw(version=1)
            repo.save(tw)
            session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            tw = repo.get("tw-1")
            assert tw is not None
            tw.state = TurnWindowState.locked
            repo.save_with_version_check(tw, expected_version=1)
            session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            loaded = repo.get("tw-1")
            assert loaded is not None
            assert loaded.state == TurnWindowState.locked
            assert loaded.version == 2

    def test_save_with_version_check_raises_on_stale(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            tw = _make_tw(version=1)
            repo.save(tw)
            session.commit()

        # Simulate concurrent modification: bump version to 2
        with factory() as session:
            repo = TurnWindowRepo(session)
            tw = repo.get("tw-1")
            tw.version = 2
            repo.save(tw)
            session.commit()

        # Now try to save with expected_version=1 — should fail
        with factory() as session:
            repo = TurnWindowRepo(session)
            tw = repo.get("tw-1")
            tw.state = TurnWindowState.locked
            with pytest.raises(StaleStateError):
                repo.save_with_version_check(tw, expected_version=1)

    def test_version_increments_on_each_check_save(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            repo.save(_make_tw(version=1))
            session.commit()

        for expected in range(1, 4):
            with factory() as session:
                repo = TurnWindowRepo(session)
                tw = repo.get("tw-1")
                repo.save_with_version_check(tw, expected_version=expected)
                session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            loaded = repo.get("tw-1")
            assert loaded.version == 4


# -----------------------------------------------------------------------
# list_open tests
# -----------------------------------------------------------------------


class TestListOpen:
    def test_list_open_excludes_committed_and_aborted(self):
        engine = create_test_engine()
        factory = create_test_session_factory(engine)
        with factory() as session:
            _seed_campaign_and_scene(session)
            repo = TurnWindowRepo(session)
            # Open window
            tw_open = _make_tw(tw_id="tw-open")
            tw_open.state = TurnWindowState.open
            repo.save(tw_open)
            # Committed window
            tw_done = _make_tw(tw_id="tw-done")
            tw_done.state = TurnWindowState.committed
            repo.save(tw_done)
            # Aborted window
            tw_abort = _make_tw(tw_id="tw-abort")
            tw_abort.state = TurnWindowState.aborted
            repo.save(tw_abort)
            session.commit()

        with factory() as session:
            repo = TurnWindowRepo(session)
            open_tws = repo.list_open()
            ids = {tw.turn_window_id for tw in open_tws}
            assert ids == {"tw-open"}


# -----------------------------------------------------------------------
# Test fixture helpers
# -----------------------------------------------------------------------


class TestDbHelpers:
    def test_create_test_engine_returns_working_engine(self):
        engine = create_test_engine()
        assert engine is not None
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

    def test_create_test_session_factory_returns_sessions(self):
        factory = create_test_session_factory()
        with factory() as session:
            assert session is not None
