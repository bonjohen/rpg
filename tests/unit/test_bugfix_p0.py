"""Tests for P0 bug fixes: auth bypass, path traversal, scope leakage."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from server.api.app import create_api_app
from server.api.routes import set_bot_token
from server.domain.entities import (
    KnowledgeFact,
    VisibilityGrant,
)
from server.domain.enums import KnowledgeFactType, ScopeType
from server.domain.helpers import new_id as _uid, utc_now as _now
from tests.fixtures.builders import make_conversation_scope
from server.orchestrator.game_loop import GameOrchestrator
from server.scope.engine import ScopeEngine
from tests.fixtures.db_helpers import create_test_session_factory

BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
GOBLIN_CAVES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scenarios", "starters", "goblin_caves.yaml"
)


def _scope(scope_type, player_id=None, side_channel_id=None):
    return make_conversation_scope(
        campaign_id="c1",
        scope_type=scope_type,
        player_id=player_id,
        side_channel_id=side_channel_id,
    )


def _fact(owner_scope_id: str) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=_uid(),
        campaign_id="c1",
        scene_id="sc1",
        owner_scope_id=owner_scope_id,
        fact_type=KnowledgeFactType.clue,
        payload="secret clue",
        revealed_at=_now(),
    )


def _build_init_data(user_id: int, first_name: str, bot_token: str) -> str:
    user_json = json.dumps({"id": user_id, "first_name": first_name})
    params = {"user": user_json, "auth_date": "1700000000"}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return urlencode(params)


# -------------------------------------------------------------------
# BUG-001: Bot token not accepted from client
# -------------------------------------------------------------------


class TestBUG001AuthTokenServerSide:
    def _make_client(self) -> TestClient:
        orch = GameOrchestrator(session_factory=create_test_session_factory())
        orch.load_scenario(GOBLIN_CAVES_PATH)
        app = create_api_app(orch, bot_token=BOT_TOKEN)
        return TestClient(app)

    def test_auth_succeeds_without_client_token(self):
        client = self._make_client()
        init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
        resp = client.post("/api/auth/validate", json={"init_data": init_data})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_auth_rejects_forged_initdata(self):
        client = self._make_client()
        init_data = _build_init_data(12345, "Alice", "wrong_token")
        resp = client.post("/api/auth/validate", json={"init_data": init_data})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_auth_request_does_not_accept_bot_token_field(self):
        client = self._make_client()
        init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
        # Extra fields are silently ignored by Pydantic, but the token
        # should not influence validation — server uses its own token
        resp = client.post(
            "/api/auth/validate",
            json={"init_data": init_data, "bot_token": "attacker_token"},
        )
        assert resp.status_code == 200
        # Should still validate against the server-side token, not the attacker's
        assert resp.json()["valid"] is True

    def test_auth_fails_when_no_server_token(self):
        orch = GameOrchestrator(session_factory=create_test_session_factory())
        orch.load_scenario(GOBLIN_CAVES_PATH)
        # Don't set bot_token — should fail
        app = create_api_app(orch)
        set_bot_token("")  # Clear any previously set token
        client = TestClient(app)
        with patch.dict(os.environ, {}, clear=False):
            # Remove BOT_TOKEN from env if present
            os.environ.pop("BOT_TOKEN", None)
            init_data = _build_init_data(12345, "Alice", BOT_TOKEN)
            resp = client.post("/api/auth/validate", json={"init_data": init_data})
            assert resp.status_code == 500


# -------------------------------------------------------------------
# BUG-002: Path traversal in /newgame
# -------------------------------------------------------------------


class TestBUG002PathTraversal:
    @pytest.mark.asyncio
    async def test_rejects_parent_traversal(self):
        from bot.commands import cmd_newgame

        update = MagicMock(spec_set=["effective_user", "message"])
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()
        update.message.chat.id = 456
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = ["../../etc/passwd"]
        context.application.bot_data = {"orchestrator": MagicMock()}

        await cmd_newgame(update, context)

        # Should have replied with an error, NOT called load_scenario
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "invalid" in reply_text.lower() or "scenarios/" in reply_text.lower()

    @pytest.mark.asyncio
    async def test_accepts_valid_scenario_path(self):
        from bot.commands import cmd_newgame

        update = MagicMock(spec_set=["effective_user", "message"])
        update.effective_user = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()
        update.message.chat.id = 456
        update.message.reply_text = AsyncMock()

        from scenarios.loader import ScenarioLoadResult

        orchestrator = MagicMock()
        orchestrator.load_scenario.return_value = ScenarioLoadResult(success=True)
        orchestrator.campaign_id = "c1"
        orchestrator.get_scenes.return_value = []

        context = MagicMock()
        context.args = [GOBLIN_CAVES_PATH]
        context.application.bot_data = {
            "orchestrator": orchestrator,
            "registry": MagicMock(),
        }

        await cmd_newgame(update, context)
        # Should have called load_scenario with the valid path
        orchestrator.load_scenario.assert_called_once()


# -------------------------------------------------------------------
# BUG-003: Scope grant leakage
# -------------------------------------------------------------------


class TestBUG003ScopeGrantLeakage:
    def test_grant_to_player_b_invisible_to_player_c(self):
        engine = ScopeEngine()
        priv_a = _scope(ScopeType.private_referee, player_id="a")
        priv_b = _scope(ScopeType.private_referee, player_id="b")
        fact = _fact(priv_a.scope_id)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id=priv_b.scope_id,
            granted_at=_now(),
        )
        scopes = {priv_a.scope_id: priv_a, priv_b.scope_id: priv_b}

        # Player B (grantee) can see
        assert engine.can_player_see_fact(
            "b", fact, priv_a, [grant], scopes_by_id=scopes
        )
        # Player C (not grantee) cannot see
        assert not engine.can_player_see_fact(
            "c", fact, priv_a, [grant], scopes_by_id=scopes
        )

    def test_grant_to_public_scope_visible_to_all(self):
        engine = ScopeEngine()
        priv = _scope(ScopeType.private_referee, player_id="a")
        pub = _scope(ScopeType.public)
        fact = _fact(priv.scope_id)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id=pub.scope_id,
            granted_at=_now(),
        )
        scopes = {priv.scope_id: priv, pub.scope_id: pub}

        assert engine.can_player_see_fact("b", fact, priv, [grant], scopes_by_id=scopes)
        assert engine.can_player_see_fact("c", fact, priv, [grant], scopes_by_id=scopes)

    def test_grant_to_unknown_scope_denies(self):
        engine = ScopeEngine()
        priv = _scope(ScopeType.private_referee, player_id="a")
        fact = _fact(priv.scope_id)
        grant = VisibilityGrant(
            grant_id=_uid(),
            fact_id=fact.fact_id,
            campaign_id="c1",
            granted_to_scope_id="nonexistent-scope",
            granted_at=_now(),
        )
        scopes = {priv.scope_id: priv}
        # Unknown granted scope → deny
        assert not engine.can_player_see_fact(
            "b", fact, priv, [grant], scopes_by_id=scopes
        )
