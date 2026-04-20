"""Unit tests for the Mini App REST API routes.

Uses FastAPI's TestClient to exercise endpoints without a running server.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from server.api.app import create_api_app
from server.api.auth import validate_init_data
from server.domain.enums import ActionType
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory

GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_orchestrator() -> GameOrchestrator:
    orch = GameOrchestrator(session_factory=create_test_session_factory())
    orch.load_scenario(GOBLIN_CAVES_PATH)
    return orch


def _make_client(
    orch: GameOrchestrator | None = None, user_id: int = 1000
) -> TestClient:
    if orch is None:
        orch = _make_orchestrator()
    app = create_api_app(orch, bot_token=BOT_TOKEN)
    init_data = _build_init_data(user_id, "TestUser", BOT_TOKEN)
    return TestClient(app, headers={"X-Init-Data": init_data})


def _add_players(orch: GameOrchestrator, count: int = 2) -> list[str]:
    """Add test players and return their player_ids."""
    ids = []
    for i in range(count):
        pid = f"player_{i}"
        orch.add_player(pid, f"Player {i}", telegram_user_id=1000 + i)
        ids.append(pid)
    return ids


def _build_init_data(user_id: int, first_name: str, bot_token: str) -> str:
    """Build a valid Telegram initData string with correct HMAC."""
    user_json = json.dumps({"id": user_id, "first_name": first_name})
    params = {"user": user_json, "auth_date": "1700000000"}
    # Build data-check string
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return urlencode(params)


# ------------------------------------------------------------------
# Auth tests
# ------------------------------------------------------------------


class TestAuth:
    def test_validate_auth_with_valid_initdata(self):
        init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
        result = validate_init_data(init_data, BOT_TOKEN)
        assert result.valid is True
        assert result.player_id == "12345"
        assert "Alice" in result.display_name

    def test_validate_auth_with_invalid_initdata(self):
        init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
        result = validate_init_data(init_data, "wrong_token")
        assert result.valid is False
        assert result.error

    def test_validate_auth_maps_to_player_id(self):
        init_data = _build_init_data(99999, "Bob", BOT_TOKEN)
        result = validate_init_data(init_data, BOT_TOKEN)
        assert result.valid is True
        assert result.player_id == "99999"
        assert result.display_name == "Bob"

    def test_validate_auth_missing_data(self):
        result = validate_init_data("", BOT_TOKEN)
        assert result.valid is False

    def test_validate_auth_no_hash(self):
        result = validate_init_data("user=%7B%22id%22%3A1%7D", BOT_TOKEN)
        assert result.valid is False
        assert "hash" in result.error.lower()

    def test_validate_auth_endpoint(self):
        client = _make_client()
        init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
        resp = client.post(
            "/api/auth/validate",
            json={"init_data": init_data},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["player_id"] == "12345"


# ------------------------------------------------------------------
# Character sheet tests
# ------------------------------------------------------------------


class TestCharacterSheet:
    def test_get_character_returns_full_state(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["character_id"] == char.character_id
        assert data["name"] == char.name
        assert "hp" in data["stats"]
        assert data["is_alive"] is True

    def test_get_character_not_found_returns_404(self):
        client = _make_client()
        resp = client.get("/api/character/nonexistent")
        assert resp.status_code == 404

    def test_get_character_includes_status_effects(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        char.status_effects = ["poisoned", "stunned"]
        with orch._session_scope() as session:
            from server.storage.repository import CharacterRepo

            CharacterRepo(session).save(char)
        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}")
        data = resp.json()
        assert "poisoned" in data["status_effects"]
        assert "stunned" in data["status_effects"]

    def test_get_character_shows_scene_id(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}")
        data = resp.json()
        assert data["scene_id"] != ""


# ------------------------------------------------------------------
# Inventory tests
# ------------------------------------------------------------------


class TestInventory:
    def test_get_inventory_returns_items(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        # Give the character an item
        from server.domain.entities import InventoryItem
        from datetime import datetime, timezone

        item = InventoryItem(
            item_id="test_item_1",
            campaign_id=orch.campaign_id,
            item_type="sword",
            name="Iron Sword",
            created_at=datetime.now(timezone.utc),
            owner_character_id=char.character_id,
            properties={"description": "A sturdy blade", "damage": "1d6"},
        )
        with orch._session_scope() as session:
            from server.storage.repository import InventoryItemRepo

            InventoryItemRepo(session).save(item)

        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}/inventory")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Iron Sword"
        assert data["items"][0]["description"] == "A sturdy blade"

    def test_get_inventory_empty_returns_empty_list(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        # Remove any default items owned by this character
        with orch._session_scope() as session:
            from server.storage.models import InventoryItemRow

            rows = (
                session.query(InventoryItemRow)
                .filter_by(owner_character_id=char.character_id)
                .all()
            )
            for row in rows:
                session.delete(row)
        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}/inventory")
        data = resp.json()
        assert data["items"] == []

    def test_get_inventory_includes_properties(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        char = orch.get_player_character(pids[0])
        from server.domain.entities import InventoryItem
        from datetime import datetime, timezone

        item = InventoryItem(
            item_id="test_prop_item",
            campaign_id=orch.campaign_id,
            item_type="key",
            name="Bronze Key",
            created_at=datetime.now(timezone.utc),
            owner_character_id=char.character_id,
            properties={"description": "An old key", "quest_item": True},
        )
        with orch._session_scope() as session:
            from server.storage.repository import InventoryItemRepo

            InventoryItemRepo(session).save(item)

        client = _make_client(orch)
        resp = client.get(f"/api/character/{char.character_id}/inventory")
        data = resp.json()
        assert len(data["items"]) >= 1
        key_item = [i for i in data["items"] if i["item_id"] == "test_prop_item"][0]
        assert key_item["properties"]["quest_item"] is True

    def test_get_inventory_not_found_returns_404(self):
        client = _make_client()
        resp = client.get("/api/character/nonexistent/inventory")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Scene tests
# ------------------------------------------------------------------


class TestScene:
    def test_get_scene_returns_description_and_exits(self):
        orch = _make_orchestrator()
        scene_id = orch._find_starting_scene_id()
        client = _make_client(orch)
        resp = client.get(f"/api/scene/{scene_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] != ""
        assert data["description"] != ""
        assert isinstance(data["exits"], dict)

    def test_get_scene_includes_present_players(self):
        orch = _make_orchestrator()
        _add_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        client = _make_client(orch)
        resp = client.get(f"/api/scene/{scene_id}")
        data = resp.json()
        assert len(data["players_present"]) == 2

    def test_get_scene_excludes_hidden_description(self):
        orch = _make_orchestrator()
        scene_id = orch._find_starting_scene_id()
        scene = orch.get_scene(scene_id)
        scene.hidden_description = "SECRET: There is a hidden trap here."
        with orch._session_scope() as session:
            from server.storage.repository import SceneRepo

            SceneRepo(session).save(scene)
        client = _make_client(orch)
        resp = client.get(f"/api/scene/{scene_id}")
        data = resp.json()
        # hidden_description should NOT be in the response
        assert "SECRET" not in data.get("description", "")
        assert "hidden_description" not in data

    def test_get_scene_not_found(self):
        client = _make_client()
        resp = client.get("/api/scene/nonexistent")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Recap tests
# ------------------------------------------------------------------


class TestRecap:
    def _setup_with_turns(self) -> tuple[GameOrchestrator, str]:
        """Setup orchestrator with a completed turn for recap testing."""
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        assert tw is not None
        # Submit actions for both players
        for pid in pids:
            orch.submit_action(pid, ActionType.hold, public_text="Wait")
        # Resolve the turn
        entry = orch.resolve_turn(tw.turn_window_id)
        assert entry is not None
        return orch, orch.campaign_id

    def test_get_recap_returns_recent_entries(self):
        orch, campaign_id = self._setup_with_turns()
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/recap")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entries"]) >= 1
        assert data["entries"][0]["turn_number"] == 1

    def test_get_recap_respects_limit_param(self):
        orch, campaign_id = self._setup_with_turns()
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/recap?limit=1")
        data = resp.json()
        assert len(data["entries"]) <= 1

    def test_get_recap_ordered_by_turn_number_desc(self):
        orch, campaign_id = self._setup_with_turns()
        # Play a second turn
        scene_id = orch._find_starting_scene_id()
        tw2 = orch.open_turn(scene_id, duration_seconds=90)
        pids = [p.player_id for p in orch.get_players()]
        for pid in pids:
            orch.submit_action(pid, ActionType.hold, public_text="Wait again")
        orch.resolve_turn(tw2.turn_window_id)

        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/recap")
        data = resp.json()
        entries = data["entries"]
        assert len(entries) >= 2
        # First entry should have higher turn number (descending)
        assert entries[0]["turn_number"] >= entries[1]["turn_number"]

    def test_get_recap_excludes_referee_facts(self):
        """Recap entries contain narration text, not referee-only facts."""
        orch, campaign_id = self._setup_with_turns()
        client = _make_client(orch)
        resp = client.get(f"/api/campaign/{campaign_id}/recap")
        data = resp.json()
        for entry in data["entries"]:
            # Narration should not contain referee markers
            assert "[referee_only]" not in entry["narration"]

    def test_get_recap_campaign_not_found(self):
        client = _make_client()
        resp = client.get("/api/campaign/nonexistent/recap")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Player endpoint tests
# ------------------------------------------------------------------


class TestPlayer:
    def test_get_player_returns_info(self):
        orch = _make_orchestrator()
        pids = _add_players(orch, 1)
        client = _make_client(orch)
        resp = client.get(f"/api/player/{pids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["player_id"] == pids[0]
        assert data["display_name"] == "Player 0"
        assert data["character_id"] != ""
        assert data["is_active"] is True

    def test_get_player_not_found(self):
        client = _make_client()
        resp = client.get("/api/player/nonexistent")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Integration: full hydration flow
# ------------------------------------------------------------------


class TestFullHydration:
    def test_full_hydration_flow(self):
        """Load scenario, add players, play a turn, then verify all API
        endpoints return consistent state."""
        orch = _make_orchestrator()
        pids = _add_players(orch, 2)

        # Play one turn
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        for pid in pids:
            orch.submit_action(pid, ActionType.inspect, public_text="Look around")
        orch.resolve_turn(tw.turn_window_id)

        client = _make_client(orch)

        # Player endpoint
        resp = client.get(f"/api/player/{pids[0]}")
        assert resp.status_code == 200
        player_data = resp.json()

        # Character endpoint
        char_id = player_data["character_id"]
        resp = client.get(f"/api/character/{char_id}")
        assert resp.status_code == 200
        char_data = resp.json()
        assert char_data["scene_id"] == player_data["current_scene_id"]

        # Inventory endpoint
        resp = client.get(f"/api/character/{char_id}/inventory")
        assert resp.status_code == 200

        # Scene endpoint
        resp = client.get(f"/api/scene/{player_data['current_scene_id']}")
        assert resp.status_code == 200
        scene_data = resp.json()
        assert player_data["display_name"] in scene_data["players_present"]

        # Recap endpoint
        campaign_id = orch.campaign_id
        resp = client.get(f"/api/campaign/{campaign_id}/recap")
        assert resp.status_code == 200
        recap_data = resp.json()
        assert len(recap_data["entries"]) >= 1
