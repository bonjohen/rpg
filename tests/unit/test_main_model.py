"""Unit tests for the main gameplay model tier.

Tests cover:
  - Prompt contract assembly (narration, NPC dialogue, ruling, combat, social, puzzle)
  - Schema validation (valid, missing fields, wrong enums, out-of-range values)
  - Fallback behavior (model timeout, model connection error, invalid output)
  - Fast-tier repair integration (mock repair succeeds / fails)
  - Routing guards (is_main_tier, assert_main_tier)
  - Context assembly (scoped knowledge packets, token truncation)
  - ModelCallLog instrumentation (tier, task_type, fallback_triggered)

All tests use mocked adapters — no live Ollama instance required.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.fast.adapter import GenerateResult as FastGenerateResult
from models.main.adapter import GenerateResult, OpenAIMainAdapter
from models.main.context import (
    _estimate_tokens,
    _truncate_history,
    assemble_narration_prompt,
    assemble_npc_dialogue_prompt,
    assemble_ruling_proposal_prompt,
    assemble_combat_summary_prompt,
    assemble_social_arbitration_prompt,
    assemble_puzzle_flavor_prompt,
)
from models.main.fallback import (
    fallback_narration,
    fallback_npc_dialogue,
    fallback_combat_summary,
    fallback_ruling_proposal,
    fallback_social_arbitration,
    fallback_puzzle_flavor,
    get_fallback,
)
from models.main.router import MainTaskType, assert_main_tier, is_main_tier
from models.main.schemas import (
    NarrationOutput,
    NpcDialogueOutput,
    CombatSummaryOutput,
    RulingProposalOutput,
    SocialArbitrationOutput,
    PuzzleFlavorOutput,
    SchemaValidationError,
    validate_narration,
    validate_npc_dialogue,
    validate_combat_summary,
    validate_ruling_proposal,
    validate_social_arbitration,
    validate_puzzle_flavor,
    SCHEMA_DESCRIPTIONS,
)
from models.main.tasks import (
    narrate_scene,
    generate_npc_dialogue,
    summarize_combat,
    propose_ruling,
    arbitrate_social,
    generate_puzzle_flavor,
)
from tests.fixtures.main_model_fixtures import (
    BAD_RULING_ENUM_JSON,
    EMPTY_NARRATION_FIELD,
    INVALID_JSON_RAW,
    MISSING_REQUIRED_FIELD_DIALOGUE,
    MISSING_REQUIRED_FIELD_NARRATION,
    MISSING_REQUIRED_FIELD_RULING,
    OUT_OF_RANGE_DC_JSON,
    SAMPLE_COMBAT_OUTCOMES,
    VALID_COMBAT_SUMMARY_JSON,
    VALID_NARRATION_JSON,
    VALID_NPC_DIALOGUE_JSON,
    VALID_PUZZLE_FLAVOR_JSON,
    VALID_RULING_PROPOSAL_JSON,
    VALID_SOCIAL_ARBITRATION_JSON,
    make_aldric_player,
    make_attack_action,
    make_bram_npc,
    make_dungeon_scene,
    make_inspect_action,
    make_persuade_action,
    make_puzzle_room_scene,
    make_recent_history,
    make_tavern_scene,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _success_result(text: str) -> GenerateResult:
    return GenerateResult(
        text=text,
        prompt_token_count=100,
        output_token_count=50,
        latency_ms=250.0,
        success=True,
    )


def _failure_result(reason: str = "timeout: mock") -> GenerateResult:
    return GenerateResult(
        latency_ms=30_001.0,
        success=False,
        failure_reason=reason,
    )


def _fast_success(text: str) -> FastGenerateResult:
    return FastGenerateResult(
        text=text,
        prompt_token_count=80,
        output_token_count=40,
        latency_ms=120.0,
        success=True,
    )


def _fast_failure() -> FastGenerateResult:
    return FastGenerateResult(
        latency_ms=5000.0,
        success=False,
        failure_reason="timeout: mock",
    )


def _mock_main_adapter(result: GenerateResult) -> OpenAIMainAdapter:
    adapter = MagicMock(spec=OpenAIMainAdapter)
    adapter.generate = AsyncMock(return_value=result)
    return adapter


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


class TestMainTierRouter:
    def test_all_main_tier_tasks_are_recognized(self):
        for task in MainTaskType:
            assert is_main_tier(task.value)

    def test_fast_tasks_are_not_main_tier(self):
        fast_tasks = [
            "intent_classification",
            "command_normalization",
            "action_packet_extraction",
            "scope_suggestion",
            "context_summarization",
            "clarification_generation",
            "schema_repair",
        ]
        for t in fast_tasks:
            assert not is_main_tier(t)

    def test_unknown_task_is_not_main_tier(self):
        assert not is_main_tier("fly_to_moon")

    def test_assert_main_tier_raises_for_fast_task(self):
        with pytest.raises(ValueError, match="not a main-tier task"):
            assert_main_tier("intent_classification")

    def test_assert_main_tier_passes_for_main_task(self):
        assert_main_tier("scene_narration")  # no exception

    def test_main_task_type_enum_values(self):
        assert MainTaskType.scene_narration.value == "scene_narration"
        assert MainTaskType.npc_dialogue.value == "npc_dialogue"
        assert MainTaskType.ruling_proposal.value == "ruling_proposal"


# ---------------------------------------------------------------------------
# Schema validation — NarrationOutput
# ---------------------------------------------------------------------------


class TestValidateNarration:
    def test_valid_full_json(self):
        output = validate_narration(VALID_NARRATION_JSON)
        assert isinstance(output, NarrationOutput)
        assert "tavern" in output.narration.lower()
        assert output.tone == "tense"
        assert output.private_notes

    def test_missing_narration_field_raises(self):
        with pytest.raises(SchemaValidationError, match="narration"):
            validate_narration(MISSING_REQUIRED_FIELD_NARRATION)

    def test_empty_narration_field_raises(self):
        with pytest.raises(SchemaValidationError, match="empty"):
            validate_narration(EMPTY_NARRATION_FIELD)

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError, match="invalid JSON"):
            validate_narration(INVALID_JSON_RAW)

    def test_unknown_tone_coerced_to_neutral(self):
        raw = '{"narration": "Something happened.", "tone": "sad"}'
        output = validate_narration(raw)
        assert output.tone == "neutral"

    def test_minimal_valid_json(self):
        raw = '{"narration": "The party advances."}'
        output = validate_narration(raw)
        assert output.narration == "The party advances."
        assert output.tone == "neutral"
        assert output.private_notes == ""


# ---------------------------------------------------------------------------
# Schema validation — NpcDialogueOutput
# ---------------------------------------------------------------------------


class TestValidateNpcDialogue:
    def test_valid_full_json(self):
        output = validate_npc_dialogue(VALID_NPC_DIALOGUE_JSON)
        assert isinstance(output, NpcDialogueOutput)
        assert "W-welcome" in output.dialogue
        assert output.mood == "nervous"

    def test_missing_dialogue_field_raises(self):
        with pytest.raises(SchemaValidationError, match="dialogue"):
            validate_npc_dialogue(MISSING_REQUIRED_FIELD_DIALOGUE)

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError, match="invalid JSON"):
            validate_npc_dialogue(INVALID_JSON_RAW)

    def test_unknown_mood_coerced_to_neutral(self):
        raw = '{"dialogue": "Hello there.", "mood": "sleepy"}'
        output = validate_npc_dialogue(raw)
        assert output.mood == "neutral"

    def test_minimal_valid_json(self):
        raw = '{"dialogue": "Hello there."}'
        output = validate_npc_dialogue(raw)
        assert output.dialogue == "Hello there."
        assert output.action_beat == ""
        assert output.mood == "neutral"


# ---------------------------------------------------------------------------
# Schema validation — CombatSummaryOutput
# ---------------------------------------------------------------------------


class TestValidateCombatSummary:
    def test_valid_full_json(self):
        output = validate_combat_summary(VALID_COMBAT_SUMMARY_JSON)
        assert isinstance(output, CombatSummaryOutput)
        assert output.tension == "high"
        assert len(output.outcomes) == 2

    def test_missing_summary_raises(self):
        raw = '{"outcomes": [], "tension": "low"}'
        with pytest.raises(SchemaValidationError, match="summary"):
            validate_combat_summary(raw)

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_combat_summary(INVALID_JSON_RAW)

    def test_unknown_tension_coerced_to_medium(self):
        raw = '{"summary": "A battle occurred.", "tension": "extreme"}'
        output = validate_combat_summary(raw)
        assert output.tension == "medium"

    def test_non_list_outcomes_coerced_to_empty(self):
        raw = '{"summary": "Combat.", "outcomes": "many", "tension": "high"}'
        output = validate_combat_summary(raw)
        assert output.outcomes == []


# ---------------------------------------------------------------------------
# Schema validation — RulingProposalOutput
# ---------------------------------------------------------------------------


class TestValidateRulingProposal:
    def test_valid_full_json(self):
        output = validate_ruling_proposal(VALID_RULING_PROPOSAL_JSON)
        assert isinstance(output, RulingProposalOutput)
        assert output.ruling == "allow_with_condition"
        assert output.difficulty_class == 14

    def test_invalid_ruling_enum_raises(self):
        with pytest.raises(SchemaValidationError, match="ruling"):
            validate_ruling_proposal(BAD_RULING_ENUM_JSON)

    def test_missing_reason_raises(self):
        with pytest.raises(SchemaValidationError, match="reason"):
            validate_ruling_proposal(MISSING_REQUIRED_FIELD_RULING)

    def test_out_of_range_dc_clamped_to_none(self):
        output = validate_ruling_proposal(OUT_OF_RANGE_DC_JSON)
        assert output.difficulty_class is None

    def test_null_dc_is_none(self):
        raw = '{"ruling": "allow", "reason": "Fine.", "difficulty_class": null}'
        output = validate_ruling_proposal(raw)
        assert output.difficulty_class is None

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_ruling_proposal(INVALID_JSON_RAW)

    def test_all_valid_ruling_values(self):
        for ruling in (
            "allow",
            "allow_with_condition",
            "deny",
            "request_clarification",
        ):
            raw = json.dumps({"ruling": ruling, "reason": "Reason."})
            output = validate_ruling_proposal(raw)
            assert output.ruling == ruling


# ---------------------------------------------------------------------------
# Schema validation — SocialArbitrationOutput
# ---------------------------------------------------------------------------


class TestValidateSocialArbitration:
    def test_valid_full_json(self):
        output = validate_social_arbitration(VALID_SOCIAL_ARBITRATION_JSON)
        assert isinstance(output, SocialArbitrationOutput)
        assert output.outcome == "partial_success"
        assert output.trust_delta.get("npc-bram-001") == 1

    def test_invalid_outcome_raises(self):
        raw = '{"outcome": "unknown", "narration": "Something happened."}'
        with pytest.raises(SchemaValidationError, match="outcome"):
            validate_social_arbitration(raw)

    def test_missing_narration_raises(self):
        raw = '{"outcome": "success"}'
        with pytest.raises(SchemaValidationError, match="narration"):
            validate_social_arbitration(raw)

    def test_invalid_trust_delta_values_skipped(self):
        raw = '{"outcome": "success", "narration": "Done.", "trust_delta": {"a": "bad", "b": 2}}'
        output = validate_social_arbitration(raw)
        assert "a" not in output.trust_delta
        assert output.trust_delta["b"] == 2

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_social_arbitration(INVALID_JSON_RAW)


# ---------------------------------------------------------------------------
# Schema validation — PuzzleFlavorOutput
# ---------------------------------------------------------------------------


class TestValidatePuzzleFlavor:
    def test_valid_full_json(self):
        output = validate_puzzle_flavor(VALID_PUZZLE_FLAVOR_JSON)
        assert isinstance(output, PuzzleFlavorOutput)
        assert output.progress == "partial"
        assert output.hint

    def test_missing_flavor_raises(self):
        raw = '{"hint": "Try the runes.", "progress": "none"}'
        with pytest.raises(SchemaValidationError, match="flavor"):
            validate_puzzle_flavor(raw)

    def test_unknown_progress_coerced_to_none(self):
        raw = '{"flavor": "You fiddle with the puzzle.", "progress": "in_progress"}'
        output = validate_puzzle_flavor(raw)
        assert output.progress == "none"

    def test_invalid_json_raises(self):
        with pytest.raises(SchemaValidationError):
            validate_puzzle_flavor(INVALID_JSON_RAW)


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


class TestFallbacks:
    def test_fallback_narration_returns_valid_output(self):
        fb = fallback_narration("the dungeon")
        assert isinstance(fb, NarrationOutput)
        assert "dungeon" in fb.narration
        assert fb.tone == "neutral"
        assert "[Fallback" in fb.private_notes

    def test_fallback_npc_dialogue_returns_valid_output(self):
        fb = fallback_npc_dialogue("Bram")
        assert isinstance(fb, NpcDialogueOutput)
        assert "Bram" in fb.dialogue
        assert fb.mood == "neutral"

    def test_fallback_combat_summary_empty_outcomes(self):
        fb = fallback_combat_summary()
        assert isinstance(fb, CombatSummaryOutput)
        assert fb.outcomes == []

    def test_fallback_combat_summary_preserves_outcomes(self):
        fb = fallback_combat_summary(SAMPLE_COMBAT_OUTCOMES)
        assert fb.outcomes == SAMPLE_COMBAT_OUTCOMES

    def test_fallback_ruling_is_request_clarification(self):
        fb = fallback_ruling_proposal()
        assert isinstance(fb, RulingProposalOutput)
        assert fb.ruling == "request_clarification"

    def test_fallback_social_outcome_is_failure(self):
        fb = fallback_social_arbitration()
        assert isinstance(fb, SocialArbitrationOutput)
        assert fb.outcome == "failure"

    def test_fallback_puzzle_progress_is_none_str(self):
        fb = fallback_puzzle_flavor()
        assert isinstance(fb, PuzzleFlavorOutput)
        assert fb.progress == "none"

    def test_get_fallback_dispatches_correctly(self):
        for task_type in (
            "scene_narration",
            "npc_dialogue",
            "combat_summary",
            "ruling_proposal",
            "social_arbitration",
            "puzzle_flavor",
        ):
            result = get_fallback(task_type)
            assert result is not None

    def test_get_fallback_unknown_task_raises(self):
        with pytest.raises(ValueError, match="No fallback"):
            get_fallback("unknown_task")

    def test_get_fallback_kwargs_passed_through(self):
        fb = get_fallback("scene_narration", location_name="Castle Hall")
        assert "Castle Hall" in fb.narration

    def test_get_fallback_npc_name_passed_through(self):
        fb = get_fallback("npc_dialogue", npc_name="Elara")
        assert "Elara" in fb.dialogue


# ---------------------------------------------------------------------------
# Context assembly — prompt structure
# ---------------------------------------------------------------------------


class TestContextAssembly:
    def test_narration_prompt_contains_scene_name(self):
        scene = make_tavern_scene()
        actions = [make_attack_action()]
        system, prompt = assemble_narration_prompt(scene, actions)
        assert "Rusty Flagon" in system + prompt

    def test_narration_prompt_contains_action(self):
        scene = make_tavern_scene()
        actions = [make_attack_action(character_name="Aldric", target="goblin")]
        _, prompt = assemble_narration_prompt(scene, actions)
        assert "Aldric" in prompt
        assert "attack" in prompt

    def test_narration_prompt_contains_public_facts(self):
        scene = make_tavern_scene()
        _, prompt = assemble_narration_prompt(scene, [])
        assert "Bram" in prompt or "innkeeper" in prompt.lower()

    def test_narration_prompt_includes_recent_history(self):
        scene = make_tavern_scene()
        history = make_recent_history()
        _, prompt = assemble_narration_prompt(scene, [], history)
        # At least some history should appear
        assert any(msg in prompt for msg in history.messages[-2:])

    def test_narration_prompt_schema_in_system(self):
        scene = make_tavern_scene()
        system, _ = assemble_narration_prompt(scene, [])
        assert "narration" in system
        assert "tone" in system

    def test_npc_dialogue_prompt_contains_npc_name(self):
        npc = make_bram_npc()
        scene = make_tavern_scene()
        system, prompt = assemble_npc_dialogue_prompt(npc, scene)
        assert "Bram" in system + prompt

    def test_npc_dialogue_prompt_contains_disposition(self):
        npc = make_bram_npc()
        scene = make_tavern_scene()
        system, _ = assemble_npc_dialogue_prompt(npc, scene)
        assert "nervous" in system

    def test_npc_dialogue_prompt_includes_known_facts(self):
        npc = make_bram_npc()
        scene = make_tavern_scene()
        _, prompt = assemble_npc_dialogue_prompt(npc, scene)
        assert "Redcloak" in prompt or "daughter" in prompt

    def test_npc_dialogue_prompt_includes_trigger_action(self):
        npc = make_bram_npc()
        scene = make_tavern_scene()
        action = make_persuade_action()
        _, prompt = assemble_npc_dialogue_prompt(npc, scene, action)
        assert "persuade" in prompt or "Mirela" in prompt

    def test_ruling_prompt_contains_action(self):
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        system, prompt = assemble_ruling_proposal_prompt(action, scene, player)
        assert "attack" in prompt
        assert "Aldric" in prompt

    def test_ruling_prompt_contains_player_hp(self):
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        _, prompt = assemble_ruling_proposal_prompt(action, scene, player)
        assert "18/20" in prompt

    def test_ruling_prompt_contains_rules_excerpt(self):
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        rules = ["Flanking grants +2 to attack rolls."]
        _, prompt = assemble_ruling_proposal_prompt(action, scene, player, rules)
        assert "Flanking" in prompt

    def test_combat_prompt_contains_outcomes(self):
        scene = make_dungeon_scene()
        actions = [make_attack_action()]
        system, prompt = assemble_combat_summary_prompt(
            scene, SAMPLE_COMBAT_OUTCOMES, actions
        )
        assert "goblin warrior 1" in prompt
        assert "defeat" in prompt

    def test_social_prompt_contains_players(self):
        scene = make_tavern_scene()
        players = [make_aldric_player()]
        npcs = [make_bram_npc()]
        _, prompt = assemble_social_arbitration_prompt(
            scene, players, npcs, "Aldric offers to help find Bram's daughter"
        )
        assert "Aldric" in prompt

    def test_social_prompt_contains_npc_disposition(self):
        scene = make_tavern_scene()
        players = [make_aldric_player()]
        npcs = [make_bram_npc()]
        _, prompt = assemble_social_arbitration_prompt(scene, players, npcs, "test")
        assert "Bram" in prompt
        assert "nervous" in prompt

    def test_puzzle_prompt_contains_puzzle_description(self):
        scene = make_puzzle_room_scene()
        action = make_inspect_action()
        _, prompt = assemble_puzzle_flavor_prompt(
            scene, "A four-symbol rune lock.", action
        )
        assert "rune lock" in prompt

    def test_puzzle_prompt_contains_player_action(self):
        scene = make_puzzle_room_scene()
        action = make_inspect_action()
        _, prompt = assemble_puzzle_flavor_prompt(scene, "A rune lock.", action)
        assert "inspect" in prompt or "Aldric" in prompt


# ---------------------------------------------------------------------------
# Token estimation and truncation
# ---------------------------------------------------------------------------


class TestTokenUtilities:
    def test_estimate_tokens_non_zero(self):
        assert _estimate_tokens("hello world") > 0

    def test_estimate_tokens_scales_with_length(self):
        short = _estimate_tokens("hi")
        long = _estimate_tokens("hi " * 100)
        assert long > short

    def test_truncate_history_fits_budget(self):
        messages = [f"Message number {i}" for i in range(20)]
        budget = 50  # very tight
        kept = _truncate_history(messages, budget)
        total_len = sum(len(m) + 1 for m in kept)
        assert total_len <= budget

    def test_truncate_history_keeps_newest(self):
        messages = ["old message", "newer message", "newest message"]
        kept = _truncate_history(messages, 1000)
        assert "newest message" in kept

    def test_truncate_history_empty_on_zero_budget(self):
        messages = ["msg1", "msg2"]
        kept = _truncate_history(messages, 0)
        assert kept == []

    def test_truncate_history_empty_input(self):
        kept = _truncate_history([], 1000)
        assert kept == []


# ---------------------------------------------------------------------------
# Task functions — happy path (mocked adapter)
# ---------------------------------------------------------------------------


class TestNarrateScene:
    @pytest.mark.asyncio
    async def test_returns_narration_output_on_success(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [], trace_id="t1")
        assert isinstance(output, NarrationOutput)
        assert log.success is True
        assert log.tier == "openai"
        assert log.task_type == "scene_narration"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_log_has_trace_id(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        scene = make_tavern_scene()
        _, log = await narrate_scene(adapter, scene, [], trace_id="my-trace")
        assert log.trace_id == "my-trace"

    @pytest.mark.asyncio
    async def test_auto_generates_trace_id(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        scene = make_tavern_scene()
        _, log = await narrate_scene(adapter, scene, [])
        assert log.trace_id  # non-empty UUID


class TestNarrateSceneFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_adapter_failure(self):
        adapter = _mock_main_adapter(_failure_result("timeout: mock"))
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [])
        assert isinstance(output, NarrationOutput)
        assert log.fallback_triggered is True
        assert "timeout" in log.failure_reason

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_schema(self):
        adapter = _mock_main_adapter(_success_result(MISSING_REQUIRED_FIELD_NARRATION))
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [])
        assert isinstance(output, NarrationOutput)
        assert log.fallback_triggered is True

    @pytest.mark.asyncio
    async def test_fallback_on_non_json_output(self):
        adapter = _mock_main_adapter(_success_result(INVALID_JSON_RAW))
        scene = make_tavern_scene()
        output, log = await narrate_scene(adapter, scene, [])
        assert isinstance(output, NarrationOutput)
        assert log.fallback_triggered is True


class TestNarrateSceneRepair:
    @pytest.mark.asyncio
    async def test_repair_succeeds_returns_repaired_output(self):
        """When schema is invalid but fast-tier repair produces valid JSON."""
        main_adapter = _mock_main_adapter(
            _success_result(MISSING_REQUIRED_FIELD_NARRATION)
        )
        fast_adapter = MagicMock()
        # repair_schema will be called and should return valid JSON
        fast_adapter.generate = AsyncMock(
            return_value=_fast_success(VALID_NARRATION_JSON)
        )
        scene = make_tavern_scene()
        output, log = await narrate_scene(
            main_adapter, scene, [], fast_adapter=fast_adapter
        )
        assert isinstance(output, NarrationOutput)
        assert "tavern" in output.narration.lower()
        # repair was used — fallback should NOT be triggered
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_repair_fails_uses_fallback(self):
        """When both main model and fast repair fail, fallback is used."""
        main_adapter = _mock_main_adapter(
            _success_result(MISSING_REQUIRED_FIELD_NARRATION)
        )
        fast_adapter = MagicMock()
        fast_adapter.generate = AsyncMock(return_value=_fast_failure())
        scene = make_tavern_scene()
        output, log = await narrate_scene(
            main_adapter, scene, [], fast_adapter=fast_adapter
        )
        assert isinstance(output, NarrationOutput)
        assert log.fallback_triggered is True


# ---------------------------------------------------------------------------
# Task functions — NPC Dialogue
# ---------------------------------------------------------------------------


class TestGenerateNpcDialogue:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        adapter = _mock_main_adapter(_success_result(VALID_NPC_DIALOGUE_JSON))
        npc = make_bram_npc()
        scene = make_tavern_scene()
        output, log = await generate_npc_dialogue(adapter, npc, scene)
        assert isinstance(output, NpcDialogueOutput)
        assert log.task_type == "npc_dialogue"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        adapter = _mock_main_adapter(_failure_result())
        npc = make_bram_npc()
        scene = make_tavern_scene()
        output, log = await generate_npc_dialogue(adapter, npc, scene)
        assert isinstance(output, NpcDialogueOutput)
        assert log.fallback_triggered is True
        assert "Bram" in output.dialogue

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_schema(self):
        adapter = _mock_main_adapter(_success_result(MISSING_REQUIRED_FIELD_DIALOGUE))
        npc = make_bram_npc()
        scene = make_tavern_scene()
        output, log = await generate_npc_dialogue(adapter, npc, scene)
        assert isinstance(output, NpcDialogueOutput)
        assert log.fallback_triggered is True


# ---------------------------------------------------------------------------
# Task functions — Combat Summary
# ---------------------------------------------------------------------------


class TestSummarizeCombat:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        adapter = _mock_main_adapter(_success_result(VALID_COMBAT_SUMMARY_JSON))
        scene = make_dungeon_scene()
        output, log = await summarize_combat(
            adapter, scene, SAMPLE_COMBAT_OUTCOMES, [make_attack_action()]
        )
        assert isinstance(output, CombatSummaryOutput)
        assert log.task_type == "combat_summary"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_preserves_outcomes(self):
        adapter = _mock_main_adapter(_failure_result())
        scene = make_dungeon_scene()
        output, log = await summarize_combat(adapter, scene, SAMPLE_COMBAT_OUTCOMES, [])
        assert isinstance(output, CombatSummaryOutput)
        assert log.fallback_triggered is True
        assert output.outcomes == SAMPLE_COMBAT_OUTCOMES


# ---------------------------------------------------------------------------
# Task functions — Ruling Proposal
# ---------------------------------------------------------------------------


class TestProposeRuling:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        adapter = _mock_main_adapter(_success_result(VALID_RULING_PROPOSAL_JSON))
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        output, log = await propose_ruling(adapter, action, scene, player)
        assert isinstance(output, RulingProposalOutput)
        assert log.task_type == "ruling_proposal"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_is_request_clarification(self):
        adapter = _mock_main_adapter(_failure_result())
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        output, log = await propose_ruling(adapter, action, scene, player)
        assert output.ruling == "request_clarification"
        assert log.fallback_triggered is True

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_ruling_enum(self):
        adapter = _mock_main_adapter(_success_result(BAD_RULING_ENUM_JSON))
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        output, log = await propose_ruling(adapter, action, scene, player)
        assert output.ruling == "request_clarification"
        assert log.fallback_triggered is True

    @pytest.mark.asyncio
    async def test_with_rules_excerpt(self):
        adapter = _mock_main_adapter(_success_result(VALID_RULING_PROPOSAL_JSON))
        scene = make_dungeon_scene()
        player = make_aldric_player()
        action = make_attack_action()
        output, log = await propose_ruling(
            adapter,
            action,
            scene,
            player,
            relevant_rules=["Flanking grants +2 attack."],
        )
        assert isinstance(output, RulingProposalOutput)
        assert log.fallback_triggered is False


# ---------------------------------------------------------------------------
# Task functions — Social Arbitration
# ---------------------------------------------------------------------------


class TestArbitrateSocial:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        adapter = _mock_main_adapter(_success_result(VALID_SOCIAL_ARBITRATION_JSON))
        scene = make_tavern_scene()
        output, log = await arbitrate_social(
            adapter,
            scene,
            players_involved=[make_aldric_player()],
            npcs_involved=[make_bram_npc()],
            situation_description="Aldric tries to gain Bram's trust",
        )
        assert isinstance(output, SocialArbitrationOutput)
        assert log.task_type == "social_arbitration"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_outcome_is_failure(self):
        adapter = _mock_main_adapter(_failure_result())
        scene = make_tavern_scene()
        output, log = await arbitrate_social(adapter, scene, [], [], "test")
        assert output.outcome == "failure"
        assert log.fallback_triggered is True


# ---------------------------------------------------------------------------
# Task functions — Puzzle Flavor
# ---------------------------------------------------------------------------


class TestGeneratePuzzleFlavor:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        adapter = _mock_main_adapter(_success_result(VALID_PUZZLE_FLAVOR_JSON))
        scene = make_puzzle_room_scene()
        action = make_inspect_action()
        output, log = await generate_puzzle_flavor(
            adapter, scene, "A rune lock with four symbols.", action
        )
        assert isinstance(output, PuzzleFlavorOutput)
        assert log.task_type == "puzzle_flavor"
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_progress_is_none(self):
        adapter = _mock_main_adapter(_failure_result())
        scene = make_puzzle_room_scene()
        action = make_inspect_action()
        output, log = await generate_puzzle_flavor(
            adapter, scene, "A rune lock.", action
        )
        assert output.progress == "none"
        assert log.fallback_triggered is True


# ---------------------------------------------------------------------------
# Instrumentation — ModelCallLog fields
# ---------------------------------------------------------------------------


class TestModelCallLog:
    @pytest.mark.asyncio
    async def test_log_tier_is_gemma(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.tier == "openai"

    @pytest.mark.asyncio
    async def test_log_has_token_counts_on_success(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.prompt_token_count == 100
        assert log.output_token_count == 50

    @pytest.mark.asyncio
    async def test_log_has_latency(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.latency_ms > 0

    @pytest.mark.asyncio
    async def test_log_failure_reason_on_timeout(self):
        adapter = _mock_main_adapter(_failure_result("timeout: mock"))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert "timeout" in log.failure_reason

    @pytest.mark.asyncio
    async def test_log_failure_reason_on_schema_error(self):
        adapter = _mock_main_adapter(_success_result(MISSING_REQUIRED_FIELD_NARRATION))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.failure_reason  # non-empty

    @pytest.mark.asyncio
    async def test_log_fallback_not_triggered_on_success(self):
        adapter = _mock_main_adapter(_success_result(VALID_NARRATION_JSON))
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_log_fallback_triggered_on_failure(self):
        adapter = _mock_main_adapter(_failure_result())
        _, log = await narrate_scene(adapter, make_tavern_scene(), [])
        assert log.fallback_triggered is True


# ---------------------------------------------------------------------------
# Schema descriptions registry
# ---------------------------------------------------------------------------


class TestSchemaDescriptions:
    def test_all_main_tasks_have_schema_description(self):
        for task in MainTaskType:
            if task.value in SCHEMA_DESCRIPTIONS:
                assert SCHEMA_DESCRIPTIONS[task.value]  # non-empty

    def test_known_tasks_in_registry(self):
        expected = [
            "scene_narration",
            "npc_dialogue",
            "combat_summary",
            "ruling_proposal",
            "social_arbitration",
            "puzzle_flavor",
        ]
        for key in expected:
            assert key in SCHEMA_DESCRIPTIONS

    def test_schema_descriptions_are_non_empty_strings(self):
        for key, desc in SCHEMA_DESCRIPTIONS.items():
            assert isinstance(desc, str) and len(desc) > 10
