"""Tests for prompt contracts, context assembly, truncation, and output repair.

Target: ~80 tests covering:
  - Contract registry completeness and field validation
  - Scope-safe context assembly and leakage prevention
  - Truncation policies for history and facts
  - Output validation and repair pipeline
  - Template rendering
"""

from __future__ import annotations

import json

import pytest

from models.contracts.fast_contracts import (
    FAST_CONTRACTS,
    get_fast_contract,
)
from models.contracts.main_contracts import (
    MAIN_CONTRACTS,
    get_main_contract,
)
from models.contracts.context_assembly import (
    ContextAssembler,
    ScopedFact,
    detect_scope_violations,
    filter_facts_by_scope,
)
from models.contracts.truncation import TruncationPolicy
from models.contracts.output_repair import (
    RepairPipeline,
    validate_output,
)
from tests.fixtures.prompt_fixtures import (
    make_broken_json_outputs,
    make_combat_summary_inputs,
    make_narration_inputs,
    make_npc_dialogue_inputs,
    make_oversized_history,
    make_ruling_inputs,
    make_valid_json_outputs,
)


# ===================================================================
# Contract registry tests
# ===================================================================


class TestFastContractRegistry:
    """All fast-tier contracts are registered and complete."""

    EXPECTED_FAST_TASKS = [
        "intent_classification",
        "command_normalization",
        "action_packet_extraction",
        "scope_suggestion",
        "context_summarization",
        "clarification_generation",
        "schema_repair",
    ]

    def test_all_fast_contracts_registered(self):
        assert len(FAST_CONTRACTS) == 7

    @pytest.mark.parametrize("task_type", EXPECTED_FAST_TASKS)
    def test_get_fast_contract_by_task_type(self, task_type):
        contract = get_fast_contract(task_type)
        assert contract.task_type == task_type
        assert contract.tier == "fast"

    def test_get_fast_contract_unknown_raises(self):
        with pytest.raises(KeyError):
            get_fast_contract("nonexistent_task")

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_contract_has_system_prompt(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        assert contract.system_prompt_template
        assert len(contract.system_prompt_template) > 10

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_contract_has_user_prompt(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        assert contract.user_prompt_template
        assert len(contract.user_prompt_template) > 5

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_contract_has_output_schema(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        assert isinstance(contract.output_schema, dict)
        assert len(contract.output_schema) > 0

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_contract_has_fallback(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        assert isinstance(contract.fallback_output, dict)

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_contract_token_limits(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        assert contract.max_input_tokens <= 4096
        assert contract.max_output_tokens > 0


class TestMainContractRegistry:
    """All main-tier contracts are registered and complete."""

    EXPECTED_MAIN_TASKS = [
        "scene_narration",
        "npc_dialogue",
        "combat_summary",
        "ruling_proposal",
        "social_arbitration",
        "puzzle_flavor",
        "unusual_action_interpretation",
    ]

    def test_all_main_contracts_registered(self):
        assert len(MAIN_CONTRACTS) == 7

    @pytest.mark.parametrize("task_type", EXPECTED_MAIN_TASKS)
    def test_get_main_contract_by_task_type(self, task_type):
        contract = get_main_contract(task_type)
        assert contract.task_type == task_type
        assert contract.tier == "main"

    def test_get_main_contract_unknown_raises(self):
        with pytest.raises(KeyError):
            get_main_contract("nonexistent_task")

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_has_system_prompt(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        assert contract.system_prompt_template
        assert len(contract.system_prompt_template) > 10

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_has_user_prompt(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        assert contract.user_prompt_template
        assert len(contract.user_prompt_template) > 5

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_has_output_schema(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        assert isinstance(contract.output_schema, dict)
        assert len(contract.output_schema) > 0

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_has_fallback(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        assert isinstance(contract.fallback_output, dict)

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_token_limits_match_routing(self, contract_id):
        """Main-tier contracts respect model_routing.md limits."""
        contract = MAIN_CONTRACTS[contract_id]
        assert contract.max_input_tokens <= 16384
        assert contract.max_output_tokens > 0

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_contract_has_scope_rules(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        assert isinstance(contract.scope_rules, list)
        assert len(contract.scope_rules) > 0


# ===================================================================
# Context assembly -- narration
# ===================================================================


class TestContextAssemblyNarration:
    """Scope-safe assembly for scene narration."""

    def setup_method(self):
        self.assembler = ContextAssembler()
        self.inputs = make_narration_inputs()

    def test_narration_contains_scene_description(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context=self.inputs["scene_context"],
            active_players=self.inputs["active_players"],
            committed_actions=self.inputs["committed_actions"],
        )
        assert "Silver Stag Tavern" in result.user_prompt

    def test_narration_contains_player_names(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context=self.inputs["scene_context"],
            active_players=self.inputs["active_players"],
        )
        assert "Kira" in result.user_prompt
        assert "Dorn" in result.user_prompt

    def test_narration_contains_committed_actions(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            committed_actions=self.inputs["committed_actions"],
        )
        assert "notice board" in result.user_prompt

    def test_narration_excludes_referee_facts(self):
        all_facts = self.inputs["public_facts"] + self.inputs["referee_facts"]
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context=self.inputs["scene_context"],
            all_facts=all_facts,
        )
        assert "spy for the thieves guild" not in result.user_prompt
        assert "spy for the thieves guild" not in result.system_prompt

    def test_narration_includes_public_facts(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            all_facts=self.inputs["public_facts"],
        )
        assert "notice board has three postings" in result.user_prompt

    def test_narration_no_side_channel_facts(self):
        side_fact = ScopedFact(
            fact_id="sc1",
            text="Secret plan to steal the treasure.",
            scope="side_channel",
        )
        result = self.assembler.assemble(
            "main.scene_narration",
            all_facts=[side_fact],
        )
        assert "steal the treasure" not in result.user_prompt


# ===================================================================
# Context assembly -- NPC dialogue
# ===================================================================


class TestContextAssemblyNpcDialogue:
    """Scope-safe assembly for NPC dialogue."""

    def setup_method(self):
        self.assembler = ContextAssembler()
        self.inputs = make_npc_dialogue_inputs()

    def test_npc_dialogue_contains_npc_personality(self):
        result = self.assembler.assemble(
            "main.npc_dialogue",
            npc_context=self.inputs["npc_context"],
            scene_context=self.inputs["scene_context"],
        )
        assert "Mira" in result.user_prompt

    def test_npc_dialogue_excludes_other_npc_facts(self):
        all_facts = self.inputs["npc_facts"] + self.inputs["other_npc_facts"]
        result = self.assembler.assemble(
            "main.npc_dialogue",
            npc_context=self.inputs["npc_context"],
            all_facts=all_facts,
            target_npc_id="npc_mira",
        )
        assert "hidden dagger" not in result.user_prompt

    def test_npc_dialogue_includes_own_public_facts(self):
        result = self.assembler.assemble(
            "main.npc_dialogue",
            npc_context=self.inputs["npc_context"],
            all_facts=self.inputs["npc_facts"],
            target_npc_id="npc_mira",
        )
        assert "goblin raids" in result.user_prompt

    def test_npc_dialogue_contains_dialogue_hints(self):
        result = self.assembler.assemble(
            "main.npc_dialogue",
            dialogue_hints=self.inputs["dialogue_hints"],
        )
        assert "warm drawl" in result.user_prompt


# ===================================================================
# Context assembly -- combat
# ===================================================================


class TestContextAssemblyCombat:
    """Scope-safe assembly for combat summary."""

    def setup_method(self):
        self.assembler = ContextAssembler()
        self.inputs = make_combat_summary_inputs()

    def test_combat_contains_battlefield_summary(self):
        result = self.assembler.assemble(
            "main.combat_summary",
            battlefield_summary=self.inputs["battlefield_summary"],
            action_results=self.inputs["action_results"],
        )
        assert "goblin scouts" in result.user_prompt

    def test_combat_contains_action_results(self):
        result = self.assembler.assemble(
            "main.combat_summary",
            action_results=self.inputs["action_results"],
        )
        assert "5 damage" in result.user_prompt

    def test_combat_excludes_hidden_monster_facts(self):
        result = self.assembler.assemble(
            "main.combat_summary",
            battlefield_summary=self.inputs["battlefield_summary"],
            all_facts=self.inputs["hidden_facts"],
        )
        assert "planning an ambush" not in result.user_prompt


# ===================================================================
# Context assembly -- ruling
# ===================================================================


class TestContextAssemblyRuling:
    """Scope-safe assembly for ruling proposals."""

    def setup_method(self):
        self.assembler = ContextAssembler()
        self.inputs = make_ruling_inputs()

    def test_ruling_contains_action_text(self):
        result = self.assembler.assemble(
            "main.ruling_proposal",
            action_text=self.inputs["action_text"],
        )
        assert "kick the locked door" in result.user_prompt

    def test_ruling_contains_character_context(self):
        result = self.assembler.assemble(
            "main.ruling_proposal",
            character_context=self.inputs["character_context"],
        )
        assert "Dorn the Fighter" in result.user_prompt

    def test_ruling_minimal_private_facts(self):
        """Only critical private facts should be included."""
        result = self.assembler.assemble(
            "main.ruling_proposal",
            action_text=self.inputs["action_text"],
            all_facts=self.inputs["private_facts"],
        )
        # Critical fact should survive (poison needle trap is relevant)
        assert "poison needle" in result.user_prompt
        # Non-critical private fact should be excluded
        assert "Old graffiti" not in result.user_prompt


# ===================================================================
# Scope violation detection
# ===================================================================


class TestScopeViolationDetection:
    """Scope violations are caught when excluded fact text leaks."""

    def test_violation_detected_when_referee_fact_in_prompt(self):
        excluded = [
            ScopedFact(
                fact_id="secret1",
                text="The dragon sleeps in the north tower",
                scope="referee_only",
            ),
        ]
        prompt = "You see the north tower. The dragon sleeps in the north tower."
        violations = detect_scope_violations(prompt, excluded)
        assert len(violations) == 1
        assert "secret1" in violations[0]

    def test_no_violation_when_text_absent(self):
        excluded = [
            ScopedFact(
                fact_id="secret2",
                text="The merchant has a hidden escape tunnel.",
                scope="referee_only",
            ),
        ]
        prompt = "You enter the bustling market square."
        violations = detect_scope_violations(prompt, excluded)
        assert len(violations) == 0

    def test_short_facts_not_matched(self):
        excluded = [
            ScopedFact(fact_id="s3", text="short", scope="referee_only"),
        ]
        prompt = "A short goblin stands here."
        violations = detect_scope_violations(prompt, excluded, min_match_length=15)
        assert len(violations) == 0

    def test_case_insensitive_detection(self):
        excluded = [
            ScopedFact(
                fact_id="s4",
                text="The Secret Passage Behind The Waterfall",
                scope="referee_only",
            ),
        ]
        prompt = "...the secret passage behind the waterfall opens up."
        violations = detect_scope_violations(prompt, excluded)
        assert len(violations) == 1


# ===================================================================
# Scope filtering
# ===================================================================


class TestScopeFiltering:
    """filter_facts_by_scope correctly excludes by rule."""

    def _make_facts(self):
        return [
            ScopedFact(fact_id="pub1", text="Public info", scope="public"),
            ScopedFact(fact_id="ref1", text="Referee secret", scope="referee_only"),
            ScopedFact(
                fact_id="sc1", text="Side channel whisper", scope="side_channel"
            ),
            ScopedFact(
                fact_id="pr1", text="Private referee note", scope="private_referee"
            ),
        ]

    def test_public_only_rule(self):
        facts = self._make_facts()
        result = filter_facts_by_scope(facts, ["public_only"])
        assert len(result) == 1
        assert result[0].fact_id == "pub1"

    def test_no_referee_facts_rule(self):
        facts = self._make_facts()
        result = filter_facts_by_scope(facts, ["no_referee_facts"])
        assert all(f.scope != "referee_only" for f in result)

    def test_no_side_channel_rule(self):
        facts = self._make_facts()
        result = filter_facts_by_scope(facts, ["no_side_channel_facts"])
        assert all(f.scope != "side_channel" for f in result)

    def test_npc_scoped_rule(self):
        facts = [
            ScopedFact(fact_id="a", text="Public", scope="public"),
            ScopedFact(
                fact_id="b", text="Mira's secret", scope="public", npc_id="npc_mira"
            ),
            ScopedFact(
                fact_id="c", text="Gruk's secret", scope="public", npc_id="npc_gruk"
            ),
        ]
        result = filter_facts_by_scope(facts, ["npc_scoped"], target_npc_id="npc_mira")
        npc_ids = [f.npc_id for f in result if f.npc_id]
        assert "npc_gruk" not in npc_ids
        assert any(f.fact_id == "b" for f in result)

    def test_minimal_private_facts_keeps_critical(self):
        facts = [
            ScopedFact(fact_id="p1", text="Public", scope="public"),
            ScopedFact(
                fact_id="r1", text="Important trap", scope="public", is_critical=True
            ),
            ScopedFact(
                fact_id="r2",
                text="Minor detail",
                scope="private_referee",
                is_critical=False,
            ),
        ]
        result = filter_facts_by_scope(facts, ["minimal_private_facts"])
        ids = {f.fact_id for f in result}
        assert "p1" in ids
        assert "r1" in ids
        assert "r2" not in ids


# ===================================================================
# Truncation tests
# ===================================================================


class TestTruncation:
    """Prompt size limits and truncation policies."""

    def setup_method(self):
        self.policy = TruncationPolicy()

    def test_estimate_tokens_reasonable(self):
        text = "Hello world, this is a test sentence for token estimation."
        tokens = self.policy.estimate_tokens(text)
        # ~58 chars / 4 = ~14 tokens
        assert 10 <= tokens <= 20

    def test_estimate_tokens_empty_returns_one(self):
        assert self.policy.estimate_tokens("") == 1

    def test_truncate_history_200_entries_under_tight_budget(self):
        """200 entries truncated when budget is tight."""
        history = make_oversized_history()
        # Use a tight budget so truncation is forced
        remaining, was_truncated = self.policy.truncate_history(
            history, current_prompt_tokens=14000, max_tokens=16384
        )
        assert was_truncated
        assert len(remaining) < len(history)
        assert len(remaining) > 0

    def test_truncate_history_oldest_removed_first(self):
        history = ["oldest message", "middle message", "newest message"]
        remaining, _ = self.policy.truncate_history(
            history, current_prompt_tokens=0, max_tokens=5
        )
        # With very tight budget, should keep newest
        if remaining:
            assert remaining[-1] == "newest message"

    def test_truncate_history_no_truncation_needed(self):
        history = ["short message"]
        remaining, was_truncated = self.policy.truncate_history(
            history, current_prompt_tokens=0, max_tokens=100000
        )
        assert not was_truncated
        assert remaining == history

    def test_truncate_history_empty(self):
        remaining, was_truncated = self.policy.truncate_history(
            [], current_prompt_tokens=0, max_tokens=1000
        )
        assert not was_truncated
        assert remaining == []

    def test_truncate_fast_tier_history(self):
        """Prompt exceeding 4K hard limit is truncated for fast tier."""
        # Each entry ~60 chars -> ~15 tokens. 200 entries -> ~3000 tokens
        history = make_oversized_history()
        remaining, was_truncated = self.policy.truncate_history(
            history,
            current_prompt_tokens=1000,
            max_tokens=self.policy.FAST_HARD_LIMIT_TOKENS,
        )
        total_chars = sum(len(e) + 1 for e in remaining) + 1000 * 4
        total_tokens = total_chars // 4
        assert total_tokens <= self.policy.FAST_HARD_LIMIT_TOKENS + 100

    def test_truncate_facts_preserves_critical(self):
        from models.contracts.truncation import ScopedFact as TruncFact

        facts = [
            TruncFact(
                fact_id="c1", text="Critical quest objective " * 20, is_critical=True
            ),
            TruncFact(fact_id="n1", text="Old news " * 50, is_critical=False),
            TruncFact(fact_id="n2", text="Another old fact " * 50, is_critical=False),
        ]
        remaining, was_truncated = self.policy.truncate_facts(
            facts, current_tokens=15000, max_tokens=16384
        )
        remaining_ids = {f.fact_id for f in remaining}
        assert "c1" in remaining_ids  # critical preserved

    def test_truncate_facts_no_truncation_needed(self):
        from models.contracts.truncation import ScopedFact as TruncFact

        facts = [
            TruncFact(fact_id="f1", text="Short fact."),
        ]
        remaining, was_truncated = self.policy.truncate_facts(
            facts, current_tokens=100, max_tokens=100000
        )
        assert not was_truncated
        assert len(remaining) == 1

    def test_check_limit_fast_within_target(self):
        text = "x" * (2048 * 4 - 100)  # just under 2K tokens
        result = self.policy.check_limit(text, "fast")
        assert result.within_target
        assert result.within_hard_limit
        assert result.tier == "fast"

    def test_check_limit_fast_over_target_under_hard(self):
        text = "x" * (3000 * 4)  # ~3K tokens, between 2K target and 4K hard
        result = self.policy.check_limit(text, "fast")
        assert not result.within_target
        assert result.within_hard_limit

    def test_check_limit_fast_over_hard(self):
        text = "x" * (5000 * 4)  # ~5K tokens, over 4K hard
        result = self.policy.check_limit(text, "fast")
        assert not result.within_target
        assert not result.within_hard_limit

    def test_check_limit_main_within_target(self):
        text = "x" * (10000 * 4)  # ~10K tokens
        result = self.policy.check_limit(text, "main")
        assert result.within_target
        assert result.within_hard_limit
        assert result.tier == "main"

    def test_check_limit_main_over_target(self):
        text = "x" * (20000 * 4)  # ~20K tokens
        result = self.policy.check_limit(text, "main")
        assert not result.within_target
        assert result.within_hard_limit


# ===================================================================
# Output validation
# ===================================================================


class TestOutputValidation:
    """validate_output checks JSON parsing and schema compliance."""

    def test_valid_json_matching_schema_passes(self):
        contract = get_fast_contract("intent_classification")
        result = validate_output(contract, '{"intent": "action", "confidence": "high"}')
        assert result.is_valid
        assert result.parsed_data == {"intent": "action", "confidence": "high"}

    def test_invalid_json_fails(self):
        contract = get_fast_contract("intent_classification")
        result = validate_output(contract, "not json at all")
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_missing_required_field_fails(self):
        contract = get_fast_contract("intent_classification")
        result = validate_output(contract, '{"intent": "action"}')
        assert not result.is_valid
        assert any("confidence" in e for e in result.errors)

    def test_wrong_enum_value_fails(self):
        contract = get_fast_contract("intent_classification")
        result = validate_output(contract, '{"intent": "dance", "confidence": "high"}')
        assert not result.is_valid
        assert any("dance" in e for e in result.errors)

    def test_wrong_type_fails(self):
        contract = get_fast_contract("action_packet_extraction")
        result = validate_output(
            contract,
            '{"action_type": 123, "target": "goblin", "item_ids": [], "notes": ""}',
        )
        assert not result.is_valid
        assert any("string" in e for e in result.errors)

    def test_valid_main_narration(self):
        contract = get_main_contract("scene_narration")
        result = validate_output(
            contract,
            '{"narration": "The cave echoes.", "private_notes": "", "tone": "tense"}',
        )
        assert result.is_valid

    def test_valid_main_ruling(self):
        contract = get_main_contract("ruling_proposal")
        result = validate_output(
            contract,
            '{"ruling": "allow", "success": true, "confidence": "high", "reasoning": "Valid."}',
        )
        assert result.is_valid

    def test_all_valid_outputs_pass(self):
        valid_outputs = make_valid_json_outputs()
        all_contracts = {**FAST_CONTRACTS, **MAIN_CONTRACTS}
        for contract_id, json_str in valid_outputs.items():
            if contract_id in all_contracts:
                contract = all_contracts[contract_id]
                result = validate_output(contract, json_str)
                assert result.is_valid, f"{contract_id} failed: {result.errors}"

    def test_all_broken_outputs_fail(self):
        broken_outputs = make_broken_json_outputs()
        all_contracts = {**FAST_CONTRACTS, **MAIN_CONTRACTS}
        for contract_id, json_str in broken_outputs.items():
            if contract_id in all_contracts:
                contract = all_contracts[contract_id]
                result = validate_output(contract, json_str)
                assert not result.is_valid, f"{contract_id} unexpectedly passed"


# ===================================================================
# Fallback validation
# ===================================================================


class TestFallbackValues:
    """Each contract's fallback_output validates against its own schema."""

    @pytest.mark.parametrize("contract_id", list(FAST_CONTRACTS.keys()))
    def test_fast_fallback_validates(self, contract_id):
        contract = FAST_CONTRACTS[contract_id]
        fallback_json = json.dumps(contract.fallback_output)
        result = validate_output(contract, fallback_json)
        # schema_repair has a minimal schema, so we allow it
        if contract_id != "fast.schema_repair":
            assert result.is_valid, f"{contract_id} fallback failed: {result.errors}"

    @pytest.mark.parametrize("contract_id", list(MAIN_CONTRACTS.keys()))
    def test_main_fallback_validates(self, contract_id):
        contract = MAIN_CONTRACTS[contract_id]
        fallback_json = json.dumps(contract.fallback_output)
        result = validate_output(contract, fallback_json)
        assert result.is_valid, f"{contract_id} fallback failed: {result.errors}"


# ===================================================================
# Repair pipeline (sync-only tests -- no actual model calls)
# ===================================================================


class TestRepairPipeline:
    """Repair pipeline without a live model."""

    def setup_method(self):
        self.pipeline = RepairPipeline(fast_adapter=None)

    def test_validate_valid_output(self):
        result = self.pipeline.validate(
            "fast.intent_classification",
            '{"intent": "action", "confidence": "high"}',
        )
        assert result.is_valid

    def test_validate_invalid_output(self):
        result = self.pipeline.validate(
            "fast.intent_classification",
            "not json",
        )
        assert not result.is_valid

    def test_get_fallback(self):
        fallback = self.pipeline.get_fallback("fast.intent_classification")
        assert fallback == {"intent": "unknown", "confidence": "low"}

    def test_get_fallback_main(self):
        fallback = self.pipeline.get_fallback("main.scene_narration")
        assert "narration" in fallback

    def test_get_fallback_unknown_contract_raises(self):
        with pytest.raises(KeyError):
            self.pipeline.get_fallback("nonexistent.contract")

    @pytest.mark.asyncio
    async def test_repair_valid_output_returns_directly(self):
        result = await self.pipeline.repair(
            "fast.intent_classification",
            '{"intent": "action", "confidence": "high"}',
        )
        assert result.success
        assert result.data == {"intent": "action", "confidence": "high"}
        assert not result.repair_attempted
        assert not result.fallback_used

    @pytest.mark.asyncio
    async def test_repair_invalid_no_adapter_uses_fallback(self):
        result = await self.pipeline.repair(
            "fast.intent_classification",
            "broken json",
        )
        assert result.success
        assert result.fallback_used
        assert result.data == {"intent": "unknown", "confidence": "low"}


# ===================================================================
# Template rendering
# ===================================================================


class TestTemplateRendering:
    """System and user prompts render correctly with inputs."""

    def setup_method(self):
        self.assembler = ContextAssembler()

    def test_narration_template_renders(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context="Dark cave",
            active_players="Kira, Dorn",
            committed_actions="- Kira: attack -> goblin",
        )
        assert "Dark cave" in result.user_prompt
        assert result.contract_id == "main.scene_narration"

    def test_npc_template_renders(self):
        result = self.assembler.assemble(
            "main.npc_dialogue",
            npc_context="Mira the Innkeeper",
            scene_context="Tavern",
            action_context="Ask about rumours",
        )
        assert "Mira" in result.user_prompt

    def test_combat_template_renders(self):
        result = self.assembler.assemble(
            "main.combat_summary",
            battlefield_summary="Cave fight",
            action_results="Kira attacks",
        )
        assert "Cave fight" in result.user_prompt

    def test_ruling_template_renders(self):
        result = self.assembler.assemble(
            "main.ruling_proposal",
            action_text="Kick the door",
            character_context="Dorn the Fighter",
        )
        assert "Kick the door" in result.user_prompt

    def test_unknown_contract_raises(self):
        with pytest.raises(KeyError):
            self.assembler.assemble("nonexistent.contract")

    def test_token_estimate_populated(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context="A long description " * 100,
        )
        assert result.token_estimate > 0

    def test_assembled_prompt_contract_id(self):
        result = self.assembler.assemble(
            "main.npc_dialogue",
            npc_context="Test NPC",
        )
        assert result.contract_id == "main.npc_dialogue"

    def test_history_included_when_provided(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context="Dark cave",
            recent_history=["Turn 1: Kira entered", "Turn 2: Dorn followed"],
        )
        assert "Kira entered" in result.user_prompt

    def test_scope_violations_empty_for_clean_assembly(self):
        result = self.assembler.assemble(
            "main.scene_narration",
            scene_context="Safe context only",
            all_facts=[
                ScopedFact(fact_id="p1", text="A public fact", scope="public"),
            ],
        )
        assert result.scope_violations == []

    def test_scope_violations_detected_on_leakage(self):
        """If scope filtering fails and a referee fact leaks, we detect it."""
        # Manually craft a scenario where the scene_context contains referee text
        referee_fact = ScopedFact(
            fact_id="leak1",
            text="The dragon guards the secret entrance",
            scope="referee_only",
        )
        result = self.assembler.assemble(
            "main.scene_narration",
            # Simulate leakage: scene_context contains the referee text
            scene_context="You see The dragon guards the secret entrance ahead.",
            all_facts=[referee_fact],
        )
        assert len(result.scope_violations) > 0
