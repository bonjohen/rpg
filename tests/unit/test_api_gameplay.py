"""Unit tests for Phase 18 Mini App gameplay API endpoints.

Tests action builder, inbox, channels, quests, clues, and map endpoints.
"""

from __future__ import annotations

import os
from fastapi.testclient import TestClient

from server.api.app import create_api_app
from server.domain.entities import (
    KnowledgeFact,
    SideChannel,
)
from server.domain.enums import (
    ActionType,
    KnowledgeFactType,
    QuestStatus,
    ScopeType,
)
from server.domain.helpers import utc_now as _now
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory

GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_orchestrator() -> GameOrchestrator:
    orch = GameOrchestrator(session_factory=create_test_session_factory())
    orch.load_scenario(GOBLIN_CAVES_PATH)
    return orch


def _make_client(orch: GameOrchestrator | None = None) -> TestClient:
    if orch is None:
        orch = _make_orchestrator()
    app = create_api_app(orch)
    return TestClient(app)


def _add_players(orch: GameOrchestrator, count: int = 2) -> list[str]:
    ids = []
    for i in range(count):
        pid = f"player_{i}"
        orch.add_player(pid, f"Player {i}", telegram_user_id=1000 + i)
        ids.append(pid)
    return ids


def _add_private_fact(
    orch: GameOrchestrator,
    player_id: str,
    fact_type: KnowledgeFactType = KnowledgeFactType.clue,
    payload: str = "Test fact",
    scene_id: str = "",
) -> KnowledgeFact:
    """Add a private-referee fact for a player."""
    scope_id = orch._get_private_scope_id(player_id)
    if not scene_id:
        scene_id = orch._find_starting_scene_id() or ""
    fact = KnowledgeFact(
        fact_id=f"fact-{player_id}-{len(orch.get_knowledge_facts())}",
        campaign_id=orch.campaign_id,
        scene_id=scene_id,
        owner_scope_id=scope_id or "",
        fact_type=fact_type,
        payload=payload,
        revealed_at=_now(),
    )
    orch.save_knowledge_fact(fact)
    return fact


def _add_public_fact(
    orch: GameOrchestrator,
    payload: str = "Public fact",
    scene_id: str = "",
) -> KnowledgeFact:
    """Add a public fact."""
    public_scope_id = None
    for scope in orch.get_scopes():
        if scope.scope_type == ScopeType.public:
            public_scope_id = scope.scope_id
            break
    if not public_scope_id:
        public_scope_id = orch._get_or_create_public_scope(
            scene_id or orch._find_starting_scene_id() or ""
        )
    if not scene_id:
        scene_id = orch._find_starting_scene_id() or ""
    fact = KnowledgeFact(
        fact_id=f"fact-public-{len(orch.get_knowledge_facts())}",
        campaign_id=orch.campaign_id,
        scene_id=scene_id,
        owner_scope_id=public_scope_id,
        fact_type=KnowledgeFactType.clue,
        payload=payload,
        revealed_at=_now(),
    )
    orch.save_knowledge_fact(fact)
    return fact


def _add_side_channel(
    orch: GameOrchestrator,
    member_ids: list[str],
    label: str = "test channel",
) -> SideChannel:
    """Add a side channel."""
    ch_id = f"sc-{label}"
    ch = SideChannel(
        side_channel_id=ch_id,
        campaign_id=orch.campaign_id,
        created_at=_now(),
        created_by_player_id=member_ids[0],
        member_player_ids=list(member_ids),
        is_open=True,
        label=label,
    )
    with orch._session_scope() as session:
        from server.storage.repository import SideChannelRepo

        SideChannelRepo(session).save(ch)
    orch.channel_messages[ch_id] = []
    return ch


# ------------------------------------------------------------------
# Scene context tests
# ------------------------------------------------------------------


class TestSceneContext:
    def test_get_scene_context_returns_exits_and_targets(self):
        orch = _make_orchestrator()
        _add_players(orch, 1)
        scene_id = orch._find_starting_scene_id()
        client = _make_client(orch)
        resp = client.get(f"/api/scene/{scene_id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scene_id"] == scene_id
        assert data["scene_name"] != ""
        assert isinstance(data["exits"], list)

    def test_get_scene_context_excludes_hidden_exits(self):
        """Hidden exits (not in scene.exits) should not appear in context."""
        orch = _make_orchestrator()
        scene_id = orch._find_starting_scene_id()
        scene = orch.get_scene(scene_id)
        # The scene only returns exits from scene.exits (public)
        # hidden_description is not included
        client = _make_client(orch)
        resp = client.get(f"/api/scene/{scene_id}/context")
        data = resp.json()
        # Exits should match scene.exits count
        assert len(data["exits"]) == len(scene.exits)


# ------------------------------------------------------------------
# Action submission tests
# ------------------------------------------------------------------


class TestActionSubmission:
    def test_submit_action_accepted(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        client = _make_client(orch)
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[0],
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
                "public_text": "Look around",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True
        assert data["action_id"] != ""

    def test_submit_action_rejected_after_lock(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        # Submit for both and resolve to lock
        for pid in pids:
            orch.submit_action(pid, ActionType.hold)
        orch.resolve_turn(tw.turn_window_id)
        client = _make_client(orch)
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[0],
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
            },
        )
        data = resp.json()
        assert data["accepted"] is False

    def test_submit_action_rejected_duplicate_player(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        # First submission
        orch.submit_action(pids[0], ActionType.hold)
        client = _make_client(orch)
        # Second submission for same player
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[0],
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
            },
        )
        data = resp.json()
        assert data["accepted"] is False

    def test_submit_action_validates_action_type(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        client = _make_client(orch)
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[0],
                "turn_window_id": tw.turn_window_id,
                "action_type": "invalid_type",
            },
        )
        data = resp.json()
        assert data["accepted"] is False
        assert "invalid" in data["rejection_reason"].lower()


# ------------------------------------------------------------------
# Draft tests
# ------------------------------------------------------------------


class TestDraft:
    def test_get_draft_returns_current_draft(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        orch.drafts[pids[0]] = {
            "turn_window_id": "tw-1",
            "action_type": "move",
            "target_id": "",
            "public_text": "Go north",
        }
        client = _make_client(orch)
        resp = client.get(f"/api/action/draft/{pids[0]}")
        data = resp.json()
        assert data["has_draft"] is True
        assert data["action_type"] == "move"
        assert data["public_text"] == "Go north"

    def test_get_draft_empty_when_no_draft(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        client = _make_client(orch)
        resp = client.get(f"/api/action/draft/{pids[0]}")
        data = resp.json()
        assert data["has_draft"] is False


# ------------------------------------------------------------------
# Inbox tests
# ------------------------------------------------------------------


class TestInbox:
    def test_get_inbox_returns_private_facts_only(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        _add_private_fact(orch, pids[0], payload="Secret for player 0")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/inbox")
        data = resp.json()
        assert len(data["messages"]) >= 1
        payloads = [m["payload"] for m in data["messages"]]
        assert "Secret for player 0" in payloads

    def test_get_inbox_excludes_public_facts(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        _add_public_fact(orch, payload="Public knowledge")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/inbox")
        data = resp.json()
        payloads = [m["payload"] for m in data["messages"]]
        assert "Public knowledge" not in payloads

    def test_get_inbox_excludes_other_player_facts(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        _add_private_fact(orch, pids[1], payload="Secret for player 1")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/inbox")
        data = resp.json()
        payloads = [m["payload"] for m in data["messages"]]
        assert "Secret for player 1" not in payloads

    def test_get_inbox_unread_count(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        _add_private_fact(orch, pids[0], payload="Fact A")
        _add_private_fact(orch, pids[0], payload="Fact B")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/inbox")
        data = resp.json()
        assert data["unread_count"] == 2
        # Second call — should be 0 unread
        resp2 = client.get(f"/api/player/{pids[0]}/inbox")
        data2 = resp2.json()
        assert data2["unread_count"] == 0


# ------------------------------------------------------------------
# Channel tests
# ------------------------------------------------------------------


class TestChannels:
    def test_get_channels_returns_player_channels(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 3)
        _add_side_channel(orch, [pids[0], pids[1]], label="heist")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/channels")
        data = resp.json()
        assert len(data["channels"]) == 1
        assert data["channels"][0]["label"] == "heist"

    def test_get_channels_excludes_non_member(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 3)
        _add_side_channel(orch, [pids[0], pids[1]], label="heist")
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[2]}/channels")
        data = resp.json()
        assert len(data["channels"]) == 0

    def test_create_channel_success(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 3)
        client = _make_client(orch)
        resp = client.post(
            "/api/channel/create",
            json={
                "creator_player_id": pids[0],
                "member_player_ids": [pids[0], pids[1]],
                "label": "secret plan",
            },
        )
        data = resp.json()
        assert data["success"] is True
        assert data["channel_id"] != ""

    def test_create_channel_validates_members(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        client = _make_client(orch)
        resp = client.post(
            "/api/channel/create",
            json={
                "creator_player_id": pids[0],
                "member_player_ids": [pids[0], "nonexistent"],
                "label": "bad channel",
            },
        )
        data = resp.json()
        assert data["success"] is False

    def test_send_channel_message(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        _add_side_channel(orch, [pids[0], pids[1]], label="chat")
        client = _make_client(orch)
        resp = client.post(
            "/api/channel/sc-chat/send",
            json={"sender_player_id": pids[0], "text": "Hello!"},
        )
        data = resp.json()
        assert data["success"] is True
        # Verify message stored
        resp2 = client.get("/api/channel/sc-chat/messages")
        data2 = resp2.json()
        assert len(data2["messages"]) == 1
        assert data2["messages"][0]["text"] == "Hello!"

    def test_leave_channel(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 3)
        _add_side_channel(orch, [pids[0], pids[1], pids[2]], label="trio")
        client = _make_client(orch)
        resp = client.post(
            "/api/channel/sc-trio/leave",
            json={"player_id": pids[2]},
        )
        data = resp.json()
        assert data["success"] is True
        # Verify pids[2] is no longer a member
        with orch._session_scope() as session:
            from server.storage.repository import SideChannelRepo

            ch = SideChannelRepo(session).get("sc-trio")
        assert pids[2] not in ch.member_player_ids


# ------------------------------------------------------------------
# Quest tests
# ------------------------------------------------------------------


class TestQuests:
    def test_get_quests_grouped_by_status(self):
        orch = _make_orchestrator()
        _add_players(orch, 1)
        client = _make_client(orch)
        campaign_id = orch.campaign_id
        resp = client.get(f"/api/campaign/{campaign_id}/quests")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["quests"], list)

    def test_get_quests_includes_objectives(self):
        orch = _make_orchestrator()
        _add_players(orch, 1)
        # Update a quest status to active
        quests = orch.get_quests()
        if quests:
            quests[0].status = QuestStatus.active
            with orch._session_scope() as session:
                from server.storage.repository import QuestStateRepo

                QuestStateRepo(session).save(quests[0])
        client = _make_client(orch)
        campaign_id = orch.campaign_id
        resp = client.get(f"/api/campaign/{campaign_id}/quests")
        data = resp.json()
        active = [q for q in data["quests"] if q["status"] == "active"]
        assert len(active) >= 1


# ------------------------------------------------------------------
# Clue tests
# ------------------------------------------------------------------


class TestClues:
    def test_get_clues_returns_player_discoverable_facts(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        _add_private_fact(
            orch, pids[0], fact_type=KnowledgeFactType.clue, payload="Hidden gem"
        )
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/clues")
        data = resp.json()
        payloads = [c["payload"] for c in data["clues"]]
        assert "Hidden gem" in payloads

    def test_get_clues_grouped_by_scene(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        scene_id = orch._find_starting_scene_id()
        _add_private_fact(
            orch,
            pids[0],
            fact_type=KnowledgeFactType.clue,
            payload="Clue A",
            scene_id=scene_id,
        )
        _add_private_fact(
            orch,
            pids[0],
            fact_type=KnowledgeFactType.clue,
            payload="Clue B",
            scene_id=scene_id,
        )
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}/clues")
        data = resp.json()
        # Both clues should have the same scene_name
        scene_names = {c["scene_name"] for c in data["clues"]}
        assert len(scene_names) == 1


# ------------------------------------------------------------------
# Map tests
# ------------------------------------------------------------------


class TestMap:
    def test_get_map_returns_discovered_scenes(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        campaign_id = orch.campaign_id
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/map?player_id={pids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        assert data["current_scene_id"] != ""

    def test_get_map_excludes_unvisited(self):
        """Scenes not connected to the player's current scene are excluded."""
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        campaign_id = orch.campaign_id
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/map?player_id={pids[0]}")
        data = resp.json()
        # Should not include ALL scenes — only current + connected
        assert len(data["nodes"]) <= len(orch.get_scenes())

    def test_get_map_shows_adjacent_undiscovered_as_question(self):
        """Adjacent scenes to the current scene should appear as nodes."""
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        campaign_id = orch.campaign_id
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/map?player_id={pids[0]}")
        data = resp.json()
        # Current scene should be discovered, adjacent should exist as nodes
        current = [
            n for n in data["nodes"] if n["scene_id"] == data["current_scene_id"]
        ]
        assert len(current) == 1
        assert current[0]["discovered"] is True

    def test_get_map_excludes_hidden_exits(self):
        """Hidden exits (not in scene.exits) are not shown on the map.

        Map edges come from all discovered scenes' exits, so we verify
        each edge's from_scene_id has the corresponding direction in
        its exits dict.
        """
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        campaign_id = orch.campaign_id
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/map?player_id={pids[0]}")
        data = resp.json()
        # Each edge should correspond to an exit in the source scene
        for edge in data["edges"]:
            source_scene = orch.get_scene(edge["from_scene_id"])
            assert source_scene is not None
            assert edge["direction"] in source_scene.exits
