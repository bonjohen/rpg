"""Unit tests for database startup recovery and multi-campaign support (Phase 6)."""

from __future__ import annotations

import os
from datetime import timedelta

from server.domain.helpers import utc_now
from server.orchestrator.game_loop import GameOrchestrator
from server.storage.repository import TurnWindowRepo
from tests.fixtures.db_helpers import create_test_session_factory

GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)

HAUNTED_MANOR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "haunted_manor.yaml"
)


def _make_orchestrator(session_factory=None):
    sf = session_factory or create_test_session_factory()
    orch = GameOrchestrator(session_factory=sf)
    return orch, sf


# ------------------------------------------------------------------
# 6.1 — startup() basic behaviour
# ------------------------------------------------------------------


class TestStartupBasic:
    def test_startup_no_campaigns_returns_empty(self):
        orch, _ = _make_orchestrator()
        notes = orch.startup()
        assert notes == []
        assert orch.campaign_id is None

    def test_startup_loads_active_campaign(self):
        sf = create_test_session_factory()
        # First orchestrator loads a scenario
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH)
        campaign_id = orch1.campaign_id
        assert campaign_id is not None

        # Second orchestrator recovers from the same DB
        orch2 = GameOrchestrator(session_factory=sf)
        orch2.startup()
        assert orch2.campaign_id == campaign_id

    def test_startup_creates_tables_idempotently(self):
        sf = create_test_session_factory()
        orch = GameOrchestrator(session_factory=sf)
        # Tables already exist from create_test_session_factory; startup should not fail
        notes = orch.startup()
        assert isinstance(notes, list)

    def test_startup_raises_without_session_factory(self):
        orch = GameOrchestrator()
        try:
            orch.startup()
            assert False, "Expected RuntimeError"
        except RuntimeError:
            pass


# ------------------------------------------------------------------
# 6.2 — Timer reconstruction
# ------------------------------------------------------------------


class TestTimerReconstruction:
    def test_timer_reconstructed_for_open_turn_window(self):
        sf = create_test_session_factory()
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH)
        orch1.add_player("p1", "Player 1")

        # Open a turn (creates a timer and an open turn window with expires_at)
        scenes = orch1.get_scenes()
        scene = scenes[0]
        tw = orch1.open_turn(scene.scene_id)
        assert tw is not None

        # Simulate crash: create new orchestrator from same DB
        orch2 = GameOrchestrator(session_factory=sf)
        notes = orch2.startup()

        # Timer should have been reconstructed
        assert len(orch2.timers) >= 1
        timer_notes = [n for n in notes if "Reconstructed timer" in n]
        assert len(timer_notes) >= 1

    def test_no_timer_for_expired_turn_window(self):
        sf = create_test_session_factory()
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH)
        orch1.add_player("p1", "Player 1")

        scenes = orch1.get_scenes()
        tw = orch1.open_turn(scenes[0].scene_id)
        assert tw is not None

        # Manually expire the turn window
        with orch1._session_scope() as session:
            tw_db = TurnWindowRepo(session).get(tw.turn_window_id)
            tw_db.expires_at = utc_now() - timedelta(seconds=60)
            TurnWindowRepo(session).save(tw_db)

        # New orchestrator should NOT create a timer for expired window
        orch2 = GameOrchestrator(session_factory=sf)
        notes = orch2.startup()
        timer_notes = [n for n in notes if "Reconstructed timer" in n]
        assert len(timer_notes) == 0


# ------------------------------------------------------------------
# 6.3 — Stuck turn recovery
# ------------------------------------------------------------------


class TestStuckTurnRecovery:
    def test_stuck_turn_recovered_on_startup(self):
        sf = create_test_session_factory()
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH)
        orch1.add_player("p1", "Player 1")

        scenes = orch1.get_scenes()
        tw = orch1.open_turn(scenes[0].scene_id)
        assert tw is not None

        # Make the turn window look stuck (opened long ago)
        with orch1._session_scope() as session:
            tw_db = TurnWindowRepo(session).get(tw.turn_window_id)
            tw_db.opened_at = utc_now() - timedelta(minutes=60)
            tw_db.expires_at = utc_now() - timedelta(minutes=30)
            TurnWindowRepo(session).save(tw_db)

        # New orchestrator should detect and recover the stuck turn
        orch2 = GameOrchestrator(session_factory=sf)
        notes = orch2.startup()
        recovery_notes = [n for n in notes if "Recovered stuck" in n]
        assert len(recovery_notes) >= 1


# ------------------------------------------------------------------
# 6.4 — load_scenario with telegram_group_id
# ------------------------------------------------------------------


class TestLoadScenarioGroupId:
    def test_telegram_group_id_persisted(self):
        orch, _ = _make_orchestrator()
        orch.load_scenario(GOBLIN_CAVES_PATH, telegram_group_id=12345)
        campaign = orch.get_campaign()
        assert campaign is not None
        assert campaign.telegram_group_id == 12345

    def test_default_group_id_is_zero(self):
        orch, _ = _make_orchestrator()
        orch.load_scenario(GOBLIN_CAVES_PATH)
        campaign = orch.get_campaign()
        assert campaign is not None
        assert campaign.telegram_group_id == 0


# ------------------------------------------------------------------
# 6.5 — Bot registry campaign mapping on startup
# ------------------------------------------------------------------


class TestBotRegistryCampaignMapping:
    def test_startup_registers_campaign_in_bot_registry(self):
        sf = create_test_session_factory()
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH, telegram_group_id=99999)
        campaign_id = orch1.campaign_id

        # New orchestrator picks up the campaign and registers it
        orch2 = GameOrchestrator(session_factory=sf)
        orch2.startup()
        assert orch2.bot_registry.is_known_chat(99999)
        assert orch2.bot_registry.campaign_id_for(99999) == campaign_id


# ------------------------------------------------------------------
# 6.6 — Full startup recovery integration test
# ------------------------------------------------------------------


class TestStartupRecoveryIntegration:
    def test_full_crash_recovery_cycle(self):
        sf = create_test_session_factory()

        # --- Phase 1: running game ---
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(GOBLIN_CAVES_PATH, telegram_group_id=42)
        orch1.add_player("p1", "Alice")
        orch1.add_player("p2", "Bob")
        scenes = orch1.get_scenes()
        tw = orch1.open_turn(scenes[0].scene_id)
        assert tw is not None
        original_campaign_id = orch1.campaign_id

        # --- Phase 2: simulate crash (discard orchestrator) ---
        del orch1

        # --- Phase 3: new orchestrator recovers ---
        orch2 = GameOrchestrator(session_factory=sf)
        orch2.startup()

        # Campaign recovered
        assert orch2.campaign_id == original_campaign_id

        # Bot registry mapping recovered
        assert orch2.bot_registry.is_known_chat(42)

        # Players still exist
        players = orch2.get_players()
        assert len(players) == 2
        names = {p.display_name for p in players}
        assert "Alice" in names
        assert "Bob" in names

        # Scenes still exist
        assert len(orch2.get_scenes()) == len(scenes)


# ------------------------------------------------------------------
# 6.7 — Multi-campaign isolation
# ------------------------------------------------------------------


class TestMultiCampaignIsolation:
    def test_two_campaigns_isolated(self):
        sf = create_test_session_factory()

        # Load first campaign
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(
            GOBLIN_CAVES_PATH, campaign_name="Campaign A", telegram_group_id=100
        )
        campaign_a = orch1.campaign_id
        orch1.add_player("pa1", "Alice")
        scenes_a = orch1.get_scenes()

        # Load second campaign (new orchestrator, same DB)
        orch2 = GameOrchestrator(session_factory=sf)
        orch2.load_scenario(
            HAUNTED_MANOR_PATH, campaign_name="Campaign B", telegram_group_id=200
        )
        campaign_b = orch2.campaign_id
        orch2.add_player("pb1", "Bob")
        scenes_b = orch2.get_scenes()

        # Campaign IDs are different
        assert campaign_a != campaign_b

        # Each orchestrator sees only its own campaign's state
        assert orch1.campaign_id == campaign_a
        assert orch2.campaign_id == campaign_b

        # Players are isolated
        players_a = orch1.get_players()
        players_b = orch2.get_players()
        assert len(players_a) == 1
        assert players_a[0].display_name == "Alice"
        assert len(players_b) == 1
        assert players_b[0].display_name == "Bob"

        # Scenes are isolated
        scene_ids_a = {s.scene_id for s in scenes_a}
        scene_ids_b = {s.scene_id for s in scenes_b}
        assert scene_ids_a.isdisjoint(scene_ids_b)

    def test_startup_picks_first_active_campaign(self):
        sf = create_test_session_factory()

        # Load two campaigns
        orch1 = GameOrchestrator(session_factory=sf)
        orch1.load_scenario(
            GOBLIN_CAVES_PATH, campaign_name="First", telegram_group_id=300
        )
        first_id = orch1.campaign_id

        orch2 = GameOrchestrator(session_factory=sf)
        orch2.load_scenario(
            HAUNTED_MANOR_PATH, campaign_name="Second", telegram_group_id=400
        )

        # New orchestrator startup picks the first active campaign
        orch3 = GameOrchestrator(session_factory=sf)
        orch3.startup()
        assert orch3.campaign_id is not None
        # Should pick one of the two campaigns
        assert orch3.campaign_id in {first_id, orch2.campaign_id}
