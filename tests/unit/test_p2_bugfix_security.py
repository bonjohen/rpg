"""Tests for P2 Phase 1: API auth guards, action submitter verification, UUID masking."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from server.api.app import create_api_app
from server.orchestrator.game_loop import GameOrchestrator
from tests.fixtures.db_helpers import create_test_session_factory
from tests.fixtures.orchestrator_builder import add_test_players

GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _build_init_data(user_id: int, first_name: str, bot_token: str) -> str:
    user_json = json.dumps({"id": user_id, "first_name": first_name})
    params = {"user": user_json, "auth_date": "1700000000"}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return urlencode(params)


def _make_orchestrator() -> GameOrchestrator:
    orch = GameOrchestrator(session_factory=create_test_session_factory())
    orch.load_scenario(GOBLIN_CAVES_PATH)
    return orch


# -------------------------------------------------------------------
# BUG-055: Auth guard on data-returning endpoints
# -------------------------------------------------------------------


class TestBUG055AuthGuard:
    def test_get_player_requires_auth(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 1)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        client = TestClient(app, raise_server_exceptions=False)
        # No X-Init-Data header → 422 (missing required header)
        resp = client.get(f"/api/player/{pids[0]}")
        assert resp.status_code == 422

    def test_get_player_rejects_invalid_auth(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 1)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        bad_init = _build_init_data(1000, "TestUser", "wrong_token")
        client = TestClient(app, headers={"X-Init-Data": bad_init})
        resp = client.get(f"/api/player/{pids[0]}")
        assert resp.status_code == 401

    def test_get_player_succeeds_with_valid_auth(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 1)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        init_data = _build_init_data(1000, "TestUser", BOT_TOKEN)
        client = TestClient(app, headers={"X-Init-Data": init_data})
        resp = client.get(f"/api/player/{pids[0]}")
        assert resp.status_code == 200

    def test_get_scene_requires_auth(self):
        orch = _make_orchestrator()
        scene_id = orch._find_starting_scene_id()
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/scene/{scene_id}")
        assert resp.status_code == 422

    def test_get_character_requires_auth(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 1)
        char = orch.get_player_character(pids[0])
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/character/{char.character_id}")
        assert resp.status_code == 422

    def test_auth_validate_endpoint_does_not_require_header(self):
        """The /api/auth/validate endpoint itself should not require the header."""
        orch = _make_orchestrator()
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        client = TestClient(app)
        init_data = _build_init_data(1000, "TestUser", BOT_TOKEN)
        resp = client.post("/api/auth/validate", json={"init_data": init_data})
        assert resp.status_code == 200


# -------------------------------------------------------------------
# BUG-056: Action submitter verification
# -------------------------------------------------------------------


class TestBUG056ActionSubmitterVerification:
    def test_submit_action_for_own_player_accepted(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        # Auth as telegram user 1000 → maps to player_0
        init_data = _build_init_data(1000, "Player 0", BOT_TOKEN)
        client = TestClient(app, headers={"X-Init-Data": init_data})
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[0],  # player_0 → telegram_user_id=1000
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
                "public_text": "Look around",
            },
        )
        data = resp.json()
        assert data["accepted"] is True

    def test_submit_action_for_other_player_rejected(self):
        orch = _make_orchestrator()
        pids = add_test_players(orch, 2)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        # Auth as telegram user 1000 → maps to player_0
        init_data = _build_init_data(1000, "Player 0", BOT_TOKEN)
        client = TestClient(app, headers={"X-Init-Data": init_data})
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": pids[1],  # player_1 → telegram_user_id=1001
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
                "public_text": "Look around",
            },
        )
        data = resp.json()
        assert data["accepted"] is False
        assert "not authorized" in data["rejection_reason"].lower()

    def test_submit_action_for_nonexistent_player_rejected(self):
        orch = _make_orchestrator()
        add_test_players(orch, 1)
        scene_id = orch._find_starting_scene_id()
        tw = orch.open_turn(scene_id, duration_seconds=90)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        init_data = _build_init_data(1000, "Player 0", BOT_TOKEN)
        client = TestClient(app, headers={"X-Init-Data": init_data})
        resp = client.post(
            "/api/action/submit",
            json={
                "player_id": "nonexistent_player",
                "turn_window_id": tw.turn_window_id,
                "action_type": "inspect",
            },
        )
        data = resp.json()
        assert data["accepted"] is False
        assert "not authorized" in data["rejection_reason"].lower()


# -------------------------------------------------------------------
# BUG-065: Bot UUID masking in /status
# -------------------------------------------------------------------


class TestBUG065UUIDMasking:
    def _make_update(self, user_id: int = 12345, first_name: str = "Alice"):
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
        update.effective_user.first_name = first_name
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        return update

    def _make_context(self, registry=None, orchestrator=None):
        context = MagicMock()
        bot_data = {}
        if registry is not None:
            bot_data["registry"] = registry
        if orchestrator is not None:
            bot_data["orchestrator"] = orchestrator
        context.application.bot_data = bot_data
        return context

    @pytest.mark.asyncio
    async def test_status_no_orchestrator_hides_uuid(self):
        from bot.commands import cmd_status
        from bot.mapping import BotRegistry

        registry = BotRegistry()
        registry.register_player(12345, "uuid-abc-123")
        update = self._make_update()
        context = self._make_context(registry=registry)
        await cmd_status(update, context)
        reply_text = update.message.reply_text.call_args[0][0]
        assert "uuid-abc-123" not in reply_text
        assert "Alice" in reply_text

    @pytest.mark.asyncio
    async def test_status_with_orchestrator_hides_uuid(self):
        from bot.commands import cmd_status
        from bot.mapping import BotRegistry

        player_id = "uuid-xyz-789"
        registry = BotRegistry()
        registry.register_player(12345, player_id)

        # Mock orchestrator
        mock_orch = MagicMock()
        mock_player = MagicMock()
        mock_player.display_name = "Alice Adventurer"
        mock_orch.get_player.return_value = mock_player
        mock_scene = MagicMock()
        mock_scene.name = "Goblin Cave"
        mock_scene.state.value = "awaiting_actions"
        mock_orch.get_player_scene.return_value = mock_scene
        mock_char = MagicMock()
        mock_char.name = "Eldrin"
        mock_orch.get_player_character.return_value = mock_char

        update = self._make_update()
        context = self._make_context(registry=registry, orchestrator=mock_orch)
        await cmd_status(update, context)
        reply_text = update.message.reply_text.call_args[0][0]
        assert "uuid-xyz-789" not in reply_text
        assert "Alice Adventurer" in reply_text
        assert "Eldrin" in reply_text

    @pytest.mark.asyncio
    async def test_status_not_in_scene_hides_uuid(self):
        from bot.commands import cmd_status
        from bot.mapping import BotRegistry

        player_id = "uuid-not-in-scene"
        registry = BotRegistry()
        registry.register_player(12345, player_id)

        mock_orch = MagicMock()
        mock_player = MagicMock()
        mock_player.display_name = "Bob"
        mock_orch.get_player.return_value = mock_player
        mock_orch.get_player_scene.return_value = None

        update = self._make_update()
        context = self._make_context(registry=registry, orchestrator=mock_orch)
        await cmd_status(update, context)
        reply_text = update.message.reply_text.call_args[0][0]
        assert "uuid-not-in-scene" not in reply_text
        assert "Bob" in reply_text
