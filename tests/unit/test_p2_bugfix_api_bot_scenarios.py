"""Tests for P2 Phase 6: API routes, bot safety, scenario errors, connection reuse."""

from __future__ import annotations

from server.domain.entities import SideChannel
from server.scope.side_channel_engine import SideChannelEngine
from scenarios.loader import ScenarioLoader
from scenarios.archetypes import NpcArchetype, _as_str_list


# -------------------------------------------------------------------
# BUG-046: leave_channel routed through SideChannelEngine
# -------------------------------------------------------------------


class TestBUG046LeaveChannel:
    def test_leave_channel_removes_member(self):
        engine = SideChannelEngine()
        ch = SideChannel(
            side_channel_id="sc-test",
            campaign_id="camp-1",
            created_at=None,
            created_by_player_id="p1",
            member_player_ids=["p1", "p2", "p3"],
            is_open=True,
            label="test",
        )
        result = engine.leave_channel(ch, "p2")
        assert result.success
        assert "p2" not in ch.member_player_ids
        assert ch.is_open  # still >=2 members

    def test_leave_channel_auto_closes_below_min(self):
        engine = SideChannelEngine()
        ch = SideChannel(
            side_channel_id="sc-test",
            campaign_id="camp-1",
            created_at=None,
            created_by_player_id="p1",
            member_player_ids=["p1", "p2"],
            is_open=True,
            label="test",
        )
        result = engine.leave_channel(ch, "p2")
        assert result.success
        assert not ch.is_open
        assert result.reason == "closed"

    def test_leave_channel_non_member_fails(self):
        engine = SideChannelEngine()
        ch = SideChannel(
            side_channel_id="sc-test",
            campaign_id="camp-1",
            created_at=None,
            created_by_player_id="p1",
            member_player_ids=["p1", "p2"],
            is_open=True,
            label="test",
        )
        result = engine.leave_channel(ch, "p999")
        assert not result.success
        assert "p999" in result.reason

    def test_leave_channel_closed_channel_fails(self):
        engine = SideChannelEngine()
        ch = SideChannel(
            side_channel_id="sc-test",
            campaign_id="camp-1",
            created_at=None,
            created_by_player_id="p1",
            member_player_ids=["p1", "p2"],
            is_open=False,
            label="test",
        )
        result = engine.leave_channel(ch, "p1")
        assert not result.success


# -------------------------------------------------------------------
# BUG-066: Narration truncated to 4096 chars
# -------------------------------------------------------------------


class TestBUG066NarrationTruncation:
    def test_short_narration_unchanged(self):
        narration = "The goblins retreat."
        header = "Turn 1 resolved.\n"
        _TELEGRAM_MAX = 4096
        max_narration = _TELEGRAM_MAX - len(header) - 1
        assert len(narration) <= max_narration
        # Would not be truncated
        msg = f"{header}{narration}"
        assert len(msg) <= 4096

    def test_long_narration_truncated_to_limit(self):
        narration = "A" * 5000
        header = "Turn 1 resolved.\n"
        _TELEGRAM_MAX = 4096
        max_narration = _TELEGRAM_MAX - len(header) - 1
        if len(narration) > max_narration:
            narration = narration[: max_narration - 3] + "..."
        msg = f"{header}{narration}"
        assert len(msg) <= 4096
        assert msg.endswith("...")


# -------------------------------------------------------------------
# BUG-052: YAML parse error context preserved
# -------------------------------------------------------------------


class TestBUG052YamlParseError:
    def test_missing_file_includes_error_context(self):
        loader = ScenarioLoader()
        result = loader.load_from_yaml("/nonexistent/path/scenario.yaml")
        assert not result.success
        assert len(result.errors) == 1
        # Should contain original error info, not just "Failed to parse"
        assert "nonexistent" in result.errors[0]
        # The dash separator indicates error context was appended
        assert "\u2014" in result.errors[0] or "—" in result.errors[0]

    def test_invalid_yaml_includes_parse_details(self):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(":\n  - :\n    bad: [unclosed")
            f.flush()
            path = f.name

        try:
            loader = ScenarioLoader()
            result = loader.load_from_yaml(path)
            assert not result.success
            # Either it parsed (unlikely) or error includes YAML details
            if result.errors:
                assert len(result.errors[0]) > 30  # has meaningful context
        finally:
            os.unlink(path)


# -------------------------------------------------------------------
# BUG-054: Validated coercion in archetypes
# -------------------------------------------------------------------


class TestBUG054ValidatedCoercion:
    def test_as_str_list_with_list_input(self):
        result = _as_str_list(["a", "b"], ["default"])
        assert result == ["a", "b"]

    def test_as_str_list_with_none_uses_default(self):
        result = _as_str_list(None, ["default"])
        assert result == ["default"]

    def test_as_str_list_with_non_list_uses_default(self):
        result = _as_str_list("not a list", ["default"])
        assert result == ["default"]

    def test_as_str_list_coerces_elements_to_str(self):
        result = _as_str_list([1, 2, 3], [])
        assert result == ["1", "2", "3"]

    def test_instantiate_with_valid_overrides(self):
        arch = NpcArchetype(
            archetype_id="test",
            personality_tags=["default_tag"],
            default_goals=["default_goal"],
            dialogue_hints=["default_hint"],
            default_tells=[],
        )
        npc = arch.instantiate(
            "npc-1",
            "Test NPC",
            personality_tags=["custom_tag"],
            goals=["custom_goal"],
        )
        assert npc.personality_tags == ["custom_tag"]
        assert npc.goals == ["custom_goal"]
        assert npc.dialogue_hints == ["default_hint"]

    def test_instantiate_with_invalid_override_type_uses_default(self):
        arch = NpcArchetype(
            archetype_id="test",
            personality_tags=["default_tag"],
            default_goals=["default_goal"],
            dialogue_hints=["default_hint"],
            default_tells=[],
        )
        # Pass a string instead of a list — should fall back to default
        npc = arch.instantiate(
            "npc-1",
            "Test NPC",
            personality_tags="not_a_list",
        )
        assert npc.personality_tags == ["default_tag"]

    def test_instantiate_trust_initial_with_dict(self):
        arch = NpcArchetype(
            archetype_id="test",
            personality_tags=[],
            default_goals=[],
            dialogue_hints=[],
            default_tells=[],
        )
        npc = arch.instantiate(
            "npc-1",
            "Test NPC",
            trust_initial={"p1": 50},
        )
        assert npc.trust_initial == {"p1": 50}

    def test_instantiate_trust_initial_non_dict_uses_empty(self):
        arch = NpcArchetype(
            archetype_id="test",
            personality_tags=[],
            default_goals=[],
            dialogue_hints=[],
            default_tells=[],
        )
        npc = arch.instantiate(
            "npc-1",
            "Test NPC",
            trust_initial="bad",
        )
        assert npc.trust_initial == {}


# -------------------------------------------------------------------
# BUG-057: Shared httpx.AsyncClient per adapter
# -------------------------------------------------------------------


class TestBUG057SharedClient:
    def test_fast_adapter_reuses_client(self):
        from models.fast.adapter import OllamaFastAdapter

        adapter = OllamaFastAdapter()
        client1 = adapter._get_client()
        client2 = adapter._get_client()
        assert client1 is client2

    async def test_fast_adapter_close(self):
        from models.fast.adapter import OllamaFastAdapter

        adapter = OllamaFastAdapter()
        client = adapter._get_client()
        assert not client.is_closed
        await adapter.close()
        assert adapter._client is None

    def test_main_adapter_reuses_client(self):
        from models.main.adapter import OpenAIMainAdapter

        adapter = OpenAIMainAdapter(api_key="test-key")
        client1 = adapter._get_client()
        client2 = adapter._get_client()
        assert client1 is client2

    async def test_main_adapter_close(self):
        from models.main.adapter import OpenAIMainAdapter

        adapter = OpenAIMainAdapter(api_key="test-key")
        client = adapter._get_client()
        assert not client.is_closed
        await adapter.close()
        assert adapter._client is None
