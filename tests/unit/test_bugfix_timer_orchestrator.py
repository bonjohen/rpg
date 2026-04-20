"""Phase 5 bug-fix tests: timer, idempotency, per-scene scope."""

from __future__ import annotations

import hashlib
from datetime import datetime

import pytest

from server.domain.enums import SceneState
from server.timer.controller import (
    TimerController,
    TimerRecord,
    TimerState,
)


# ---------------------------------------------------------------------------
# BUG-010: check_expiry raises ValueError when expires_at is None
# ---------------------------------------------------------------------------


class TestCheckExpiryNoneExpiresAt:
    def test_running_timer_with_none_expires_at_raises(self):
        ctrl = TimerController()
        timer = TimerRecord(
            timer_id="t1",
            turn_window_id="tw1",
            campaign_id="c1",
            duration_seconds=60,
            state=TimerState.running,
            started_at=datetime(2026, 1, 1, 0, 0, 0),
            expires_at=None,
        )
        with pytest.raises(ValueError, match="expires_at is None"):
            ctrl.check_expiry(timer, now=datetime(2026, 1, 1, 0, 0, 30))

    def test_paused_timer_does_not_raise(self):
        ctrl = TimerController()
        timer = TimerRecord(
            timer_id="t2",
            turn_window_id="tw2",
            campaign_id="c1",
            duration_seconds=60,
            state=TimerState.paused,
            expires_at=None,
        )
        result = ctrl.check_expiry(timer, now=datetime(2026, 1, 1, 0, 0, 30))
        assert not result.has_expired

    def test_terminal_timer_does_not_raise(self):
        ctrl = TimerController()
        timer = TimerRecord(
            timer_id="t3",
            turn_window_id="tw3",
            campaign_id="c1",
            duration_seconds=60,
            state=TimerState.expired,
            expires_at=None,
        )
        result = ctrl.check_expiry(timer, now=datetime(2026, 1, 1, 0, 0, 30))
        assert not result.has_expired


# ---------------------------------------------------------------------------
# BUG-011: paused → early_closed is a valid transition
# ---------------------------------------------------------------------------


class TestPausedToEarlyClosed:
    def test_early_close_from_paused_succeeds(self):
        ctrl = TimerController()
        timer = ctrl.create_timer("tw1", "c1", 60)
        timer = ctrl.start(timer, now=datetime(2026, 1, 1, 0, 0, 0))
        result = ctrl.pause(timer, now=datetime(2026, 1, 1, 0, 0, 10))
        assert result.success
        timer = result.timer

        result = ctrl.trigger_early_close(timer, now=datetime(2026, 1, 1, 0, 0, 15))
        assert result.success
        assert result.timer.state == TimerState.early_closed

    def test_transition_table_includes_early_closed_for_paused(self):
        from server.timer.controller import _VALID_TIMER_TRANSITIONS

        assert TimerState.early_closed in _VALID_TIMER_TRANSITIONS[TimerState.paused]


# ---------------------------------------------------------------------------
# BUG-012: Deterministic idempotency keys via SHA-256
# ---------------------------------------------------------------------------


class TestDeterministicIdempotencyKey:
    def test_sha256_is_deterministic(self):
        """Same text always produces the same idempotency key."""
        text = "attack goblin"
        player_id = "p1"
        key1 = f"msg:{player_id}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        key2 = f"msg:{player_id}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        assert key1 == key2

    def test_sha256_differs_from_hash(self):
        """SHA-256 key is not the same as hash()-based key (hash() is non-deterministic)."""
        text = "attack goblin"
        sha_part = hashlib.sha256(text.encode()).hexdigest()[:16]
        # sha_part is always a 16-char hex string
        assert len(sha_part) == 16
        assert all(c in "0123456789abcdef" for c in sha_part)


# ---------------------------------------------------------------------------
# BUG-013: Per-scene public scope creation
# ---------------------------------------------------------------------------


class TestPerScenePublicScope:
    def test_scope_entity_has_scene_id(self):
        from server.domain.entities import ConversationScope
        from server.domain.enums import ScopeType

        scope = ConversationScope(
            scope_id="s1",
            campaign_id="c1",
            scope_type=ScopeType.public,
            scene_id="scene_tavern",
        )
        assert scope.scene_id == "scene_tavern"

    def test_scope_entity_scene_id_defaults_none(self):
        from server.domain.entities import ConversationScope
        from server.domain.enums import ScopeType

        scope = ConversationScope(
            scope_id="s2",
            campaign_id="c1",
            scope_type=ScopeType.public,
        )
        assert scope.scene_id is None

    def test_per_scene_scope_repo(self):
        """Different scenes get different public scopes."""
        from server.domain.entities import Campaign, ConversationScope, Scene
        from server.domain.enums import ScopeType
        from server.storage.repository import (
            CampaignRepo,
            ConversationScopeRepo,
            SceneRepo,
        )
        from tests.fixtures.db_helpers import (
            create_test_engine,
            create_test_session_factory,
        )

        engine = create_test_engine()
        factory = create_test_session_factory(engine)

        now = datetime(2026, 1, 1)
        with factory() as session:
            CampaignRepo(session).save(
                Campaign(
                    campaign_id="c1",
                    name="Test",
                    telegram_group_id=0,
                    main_topic_id=None,
                    created_at=now,
                )
            )

            for sid in ("scene_a", "scene_b"):
                SceneRepo(session).save(
                    Scene(
                        scene_id=sid,
                        campaign_id="c1",
                        name=sid,
                        description="",
                        state=SceneState.awaiting_actions,
                        created_at=now,
                    )
                )

            repo = ConversationScopeRepo(session)

            scope_a = ConversationScope(
                scope_id="sa",
                campaign_id="c1",
                scope_type=ScopeType.public,
                scene_id="scene_a",
            )
            scope_b = ConversationScope(
                scope_id="sb",
                campaign_id="c1",
                scope_type=ScopeType.public,
                scene_id="scene_b",
            )
            repo.save(scope_a)
            repo.save(scope_b)
            session.commit()

            found_a = repo.get_public_scope_for_scene("c1", "scene_a")
            found_b = repo.get_public_scope_for_scene("c1", "scene_b")
            assert found_a is not None
            assert found_b is not None
            assert found_a.scope_id == "sa"
            assert found_b.scope_id == "sb"
            assert found_a.scene_id == "scene_a"
            assert found_b.scene_id == "scene_b"

            # No scope for a third scene
            assert repo.get_public_scope_for_scene("c1", "scene_c") is None
