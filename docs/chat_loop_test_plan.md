# Test Plan: Chat-Driven Game Loop Integration

**Source document:** `docs/chat_loop_pdr.md`
**Date:** 2026-04-20 11:45 PM (PST)

## 1. Purpose

This test plan covers both existing test coverage (confirming what's already solid) and new tests required by the PDR's seven gaps. The goal is that after implementation, every verification criterion in PDR Section 9 is proven by at least one automated test, and every gap has failure-path coverage.

## 2. Existing Coverage Assessment

### Fully Covered (no new tests needed)

| Area | Test Files | Methods | Notes |
|---|---|---|---|
| Turn lifecycle (open→submit→resolve) | `test_turn_engine.py`, integration tests | 54+ | State machine, late rejection, all-ready, timeout fallback |
| Combat mechanics | `test_combat.py` | 87 | All action types, monster AI, morale, damage, conditions |
| Exploration mechanics | `test_exploration.py` | 97 | Movement, triggers, clues, objects, traps, memory |
| NPC social engine | `test_npc_social.py` | 91 | Trust, stance, tells, dialogue, memory |
| Scope enforcement | `test_scope_engine.py`, `test_privacy_audit.py` | 81 | Visibility grants, fact masking, leakage prevention |
| Side channels | `test_side_channels.py` | 58 | Policy, membership, creation, relay |
| Database persistence | `test_persistence.py`, `test_database_*.py` | 58 | All entity CRUD, session isolation, recovery |
| Scenario loading/validation | `test_scenario.py`, `test_scenario_expanded.py` | 134 | Schema, validation, triggers, puzzles, quests |
| Model contracts (schema) | `test_prompt_contracts.py`, `test_main_model.py` | 187 | Prompt assembly, schema validation, fallback behavior |
| Fast model tasks | `test_fast_model.py` | 35 | Intent classification, action extraction, repair, fallback |
| Bot outbound | `test_bot_outbound.py` | 7 | send_public, send_private, send_private_by_player_id |
| Bot parsers/routing | `test_bot_parsers.py`, `test_bot_routing.py` | 15 | Message classification, group/private parsing, RouteTarget |
| Bot commands | `test_bot_commands.py` | 8 | /start, /join, /help, /status |
| Timer controller | `test_timer.py` | 37 | Create, start, expiry, early close, pause/resume |
| Timer integration | `test_bugfix_timer_orchestrator.py` | 10 | process_tick, timeout fallback |
| Split-party isolation | `test_split_party.py` | 56 | Per-scene visibility, transfers, NPC isolation |
| Reliability | `test_reliability.py` | 87 | Rollback, replay, model error handling |
| P0/P1/P2 regressions | 6 test_bugfix_*.py files | 47 | All fixed bugs have regression tests |

**Total existing: ~1,479 tests across 45 files.**

### Coverage Gaps (new tests required)

| Gap | What's Missing | PDR Gap | Priority |
|---|---|---|---|
| Bot handler dispatch | `_handle_group_message` and `_handle_private_message` never tested beyond None guards | Gap 1 | Critical |
| Orchestrator message handling | `handle_player_message` and `_handle_as_action` have no direct tests | Gap 1 | Critical |
| Auto-turn management | No tests for ensure_turn_open, race condition guard, auto-resolve on all-ready | Gap 2 | Critical |
| Rich narration pipeline | `narrate_scene()` tested in isolation but never called from orchestrator | Gap 3 | High |
| Result delivery to Telegram | No `bot/delivery.py` exists yet; no tests for post-resolution delivery flow | Gap 4 | High |
| Scene introduction on join/newgame | `/newgame` and `/join` narrative output not tested | Gap 5 | Medium |
| Inline keyboard / callback queries | Keyboard structure tested; button press → action flow not tested | Gap 6 | High |
| Question intent handling | No tests for question → propose_ruling flow | Gap 7 | Medium |
| Timer expiry → auto-resolve via job_queue | Timer poll-based expiry tested; PTB job_queue integration not tested | Gap 2c | High |
| Idempotency cross-turn collision | Current key collides on identical text across turns; no test proves this | PDR §5 | Medium |
| Partial delivery failure | No tests for DM failure during result delivery | Gap 4 | Medium |

## 3. New Test Specifications

### 3.1 Bot Handler Dispatch (`tests/unit/test_bot_handlers.py`)

Tests for `_handle_group_message` and `_handle_private_message` after Gap 1 wiring.

| Test | Description | Verifies |
|---|---|---|
| `test_group_play_action_dispatches_to_orchestrator` | Player sends text in play topic → `handle_player_message` called with `is_private=False` | Gap 1 |
| `test_group_non_play_topic_ignored` | Message in non-play topic → orchestrator NOT called | Gap 1 |
| `test_group_action_response_sent_public` | Orchestrator returns response_text → `send_public` called | Gap 1 |
| `test_group_action_submitted_triggers_resolve_check` | `DispatchResult.action_submitted=True` → resolve check runs | Gap 1, Gap 2b |
| `test_group_unknown_user_gets_onboarding` | Unregistered user sends message → onboarding reply, no crash | Gap 1 |
| `test_group_orchestrator_error_handled_gracefully` | Orchestrator raises → error logged, generic reply sent, handler doesn't crash | Gap 1 |
| `test_private_message_dispatches_to_orchestrator` | Player sends DM → `handle_player_message` called with `is_private=True` | Gap 1 |
| `test_private_response_sent_as_dm` | Orchestrator returns response → `send_private` called | Gap 1 |
| `test_private_unregistered_user_gets_onboarding` | Unregistered DM → onboarding prompt | Gap 1 |

**Fixtures:** Mock orchestrator, mock bot, telegram_builders. No real DB or model calls.

### 3.2 Orchestrator Message Handling (`tests/unit/test_orchestrator_message.py`)

Direct tests for `handle_player_message` and `_handle_as_action`.

| Test | Description | Verifies |
|---|---|---|
| `test_action_intent_submits_to_turn` | Text classified as "action" → `submit_action` called | Gap 1 |
| `test_question_intent_calls_ruling` | Text classified as "question" → `propose_ruling` called, response returned | Gap 7 |
| `test_question_private_stays_private` | Private question → response scope is "private" | Gap 7 |
| `test_chat_intent_returns_empty` | Text classified as "chat" → `handled=True`, `response_text=""` | Gap 1 |
| `test_unknown_intent_falls_back_to_action` | Unknown/ambiguous → treated as action | Gap 1 |
| `test_duplicate_message_deduped` | Same player+text+turn → second call returns `handled=True, response_text=""` | PDR §5 |
| `test_identical_text_different_turns_not_deduped` | Same text in turn 1 and turn 2 → both processed | PDR §5 |
| `test_no_fast_adapter_treats_as_action` | Fast adapter is None → message treated as action directly | Gap 1 |
| `test_action_extraction_failure_fallback` | Fast model returns garbage → action_type falls back to "custom" | Gap 1 |

**Fixtures:** Mock fast adapter, mock main adapter, real DB (in-memory SQLite), scenario fixtures.

### 3.3 Auto-Turn Management (`tests/unit/test_auto_turn.py`)

Tests for `ensure_turn_open`, auto-resolve, and the race condition guard.

| Test | Description | Verifies |
|---|---|---|
| `test_ensure_turn_open_creates_turn_when_none_active` | No active turn → `open_turn` called, new TurnWindow returned | Gap 2a |
| `test_ensure_turn_open_returns_existing_when_active` | Active turn exists → returns it, does NOT create a second | Gap 2a |
| `test_ensure_turn_open_race_condition_guard` | Two concurrent calls for same scene → only one TurnWindow created | Gap 2a |
| `test_auto_resolve_on_all_ready` | All players submit → turn auto-resolves without timer expiry | Gap 2b |
| `test_auto_resolve_posts_narration` | After auto-resolve, narration is generated and delivery is triggered | Gap 2b, Gap 4 |
| `test_scene_description_posted_before_turn_opens` | When auto-opening, scene description sent BEFORE turn window is created | Gap 2a (invariant) |
| `test_nextturn_still_works_as_override` | `/nextturn` opens turn even when auto-open would do it | Gap 2 |

**Fixtures:** Mock bot, real DB (in-memory), scenario loaded, multiple players added.

### 3.4 Rich Narration Pipeline (`tests/unit/test_narration_pipeline.py`)

Tests for `generate_narration` in `bot/delivery.py`.

| Test | Description | Verifies |
|---|---|---|
| `test_narration_calls_main_model` | After resolution, `narrate_scene` called with correct scene + actions | Gap 3 |
| `test_narration_uses_context_assembler` | Prompt built via `ContextAssembler` with public-only scope | Gap 3, §6 scope safety |
| `test_narration_no_referee_facts_in_prompt` | Referee-only facts excluded from narration prompt | Gap 3, §6 scope safety |
| `test_narration_fallback_on_model_failure` | Main model returns failure → basic concatenated narration used | Gap 3 |
| `test_narration_fallback_on_model_timeout` | Main model times out → fallback narration, turn not blocked | Gap 3 |
| `test_combat_scene_uses_summarize_combat` | Scene in combat state → `summarize_combat` called instead of `narrate_scene` | Gap 3 |
| `test_npc_involved_generates_dialogue` | NPC targeted by action → `generate_npc_dialogue` called | Gap 3 |

**Fixtures:** Mock main adapter (returns canned rich narration or failure), real DB, resolved turn data.

### 3.5 Result Delivery (`tests/unit/test_delivery.py`)

Tests for `deliver_turn_results` in `bot/delivery.py`.

| Test | Description | Verifies |
|---|---|---|
| `test_public_narration_sent_to_group` | After resolution, `send_public` called with narration text | Gap 4 |
| `test_private_facts_sent_to_owning_player` | Private-referee fact revealed → `send_private_by_player_id` called for that player only | Gap 4 |
| `test_other_players_do_not_receive_private_facts` | Private fact for player A → player B's DM NOT called | Gap 4 |
| `test_partial_delivery_failure_continues` | DM to player B fails (TelegramError) → player A's DM still sent, public narration still sent | Gap 4 |
| `test_partial_delivery_failure_logged` | Failed DM → error logged with player_id and fact_id | Gap 4 |
| `test_control_message_edited_on_resolve` | Turn-control message edited to show "Turn N resolved", keyboard removed | Gap 4, Gap 6 |
| `test_empty_turn_no_private_facts` | Turn with no private revelations → no DMs sent, only public narration | Gap 4 |

**Fixtures:** Mock bot, mock registry, pre-built turn log entry and facts.

### 3.6 Scene Introduction (`tests/unit/test_scene_introduction.py`)

Tests for enhanced `/newgame` and `/join` commands.

| Test | Description | Verifies |
|---|---|---|
| `test_newgame_shows_scenario_title_and_description` | `/newgame` response includes scenario title, description, starting scene | Gap 5 |
| `test_newgame_shows_starting_scene_description` | Response includes the starting scene's narrative description text | Gap 5 |
| `test_join_shows_scene_description` | `/join` response includes full scene description and exits | Gap 5 |
| `test_join_announces_arrival_to_group` | `/join` posts "{name} has entered {scene}" to group chat | Gap 5 |
| `test_scenario_load_result_carries_metadata` | `ScenarioLoadResult` has `title` and `description` from YAML manifest | Gap 5 |

**Fixtures:** Mock bot, telegram_builders, mock orchestrator with scenario loaded.

### 3.7 Inline Keyboard and Callback Queries (`tests/unit/test_callback_queries.py`)

Tests for Ready/Pass button presses and turn-control message lifecycle.

| Test | Description | Verifies |
|---|---|---|
| `test_turn_open_posts_control_message_with_keyboard` | Turn opens → message posted with InlineKeyboard containing Ready/Pass | Gap 6 |
| `test_ready_button_submits_hold_action` | Player presses Ready → `submit_action(player_id, ActionType.hold)` called with ready state | Gap 6 |
| `test_pass_button_submits_hold_action` | Player presses Pass → hold action with pass state | Gap 6 |
| `test_button_press_from_non_player_rejected` | Unregistered user presses button → callback answered with error, no action submitted | Gap 6 |
| `test_button_press_after_turn_resolved_rejected` | Button pressed after turn committed → callback answered with "turn already resolved" | Gap 6 |
| `test_control_message_updates_on_submission` | Player submits action → control message edited to show "Waiting for: {remaining}" | Gap 6 |
| `test_callback_query_answered` | Every button press → `callback_query.answer()` called (Telegram API requirement) | Gap 6 |

**Fixtures:** Mock bot with `edit_message_text` support, telegram callback query builders.

### 3.8 Timer Expiry via Job Queue (`tests/unit/test_timer_job.py`)

Tests for PTB `job_queue.run_once()` integration.

| Test | Description | Verifies |
|---|---|---|
| `test_turn_open_schedules_timer_job` | `open_turn` → job scheduled via `job_queue.run_once(callback, when=expires_at)` | Gap 2c |
| `test_timer_job_resolves_expired_turn` | Job fires → turn resolved, narration generated, results delivered | Gap 2c |
| `test_timer_job_skips_already_resolved_turn` | Turn was resolved by all-ready before timer → job fires → no-op | Gap 2c |
| `test_timer_job_generates_fallback_actions` | Timer expires with missing submissions → hold actions synthesized for absent players | Gap 2c |
| `test_timer_job_has_bot_context` | Job callback receives `context.bot` and `context.application.bot_data` | Gap 2c |

**Fixtures:** PTB Application with job_queue (or mock), real DB, scenario with multiple players.

## 4. Integration Tests

### 4.1 End-to-End Chat Turn (`tests/integration/test_chat_turn_e2e.py`)

Full turn lifecycle through the bot handler layer, with mocked model responses.

| Test | Description | Verifies |
|---|---|---|
| `test_full_turn_via_chat` | Player sends action text → turn auto-opens → action submitted → all-ready → resolve → narration posted | PDR §9 criteria 1, 3, 5 |
| `test_multi_player_turn` | Two players send actions → both submitted → all-ready → single narration | PDR §9 criteria 3, 4 |
| `test_private_question_via_dm` | Player DMs question → ruling returned privately → group sees nothing | PDR §9 criteria 4 |
| `test_timeout_fallback_turn` | One player submits, one doesn't → timer fires → hold action for absent → resolves | PDR §9 criteria 6 |
| `test_consecutive_turns_auto_open` | After resolution, next player action auto-opens turn 2 → game continues | PDR §9 criteria 9 |
| `test_private_facts_delivered_after_resolve` | Resolution reveals private fact → owning player gets DM, others don't | PDR §9 criteria 8 |

**Fixtures:** Full orchestrator with in-memory DB, mock fast adapter (returns canned classifications), mock main adapter (returns canned narrations), mock bot (captures outbound calls), scenario loaded, 2 players joined.

### 4.2 Scenario Playthrough (`tests/integration/test_goblin_caves_playthrough.py`)

Scripted playthrough of the goblin_caves scenario to verify the complete experience.

| Test | Description | Verifies |
|---|---|---|
| `test_newgame_shows_scenario_intro` | `/newgame goblin_caves` → group sees title, description, Cave Entrance | PDR §9 criteria 1 |
| `test_join_shows_cave_entrance` | Player joins → sees Cave Entrance description, exits | PDR §9 criteria 2 |
| `test_pick_up_torch` | Player types "I pick up the discarded torch" → action submitted, resolved, narrated | PDR §9 criteria 3 |
| `test_enter_cave_triggers_lookout` | Player moves north → goblin_lookout trigger fires → whistle narration | Trigger system |
| `test_talk_to_grix` | Player types "I try to negotiate with Grix" → social action, NPC dialogue generated | NPC dialogue |
| `test_private_awareness_check` | Player DMs "Do I notice anything hidden?" → private response about hidden passage (if check passes) | PDR §9 criteria 4, 8 |

**Fixtures:** Full orchestrator, mock model adapters, goblin_caves scenario loaded.

## 5. What NOT to Test (unchanged from `docs/testing.md`)

- Live Telegram API behavior (tested manually before production)
- Live model inference quality (tested manually via playtest)
- Formatting and whitespace (covered by ruff)
- Internal implementation details likely to change

## 6. Test Infrastructure Additions

### New fixture builders needed

| Builder | Location | Purpose |
|---|---|---|
| `make_callback_query()` | `tests/fixtures/telegram_builders.py` | Mock Telegram callback query for inline button tests |
| `make_mock_orchestrator_with_scenario()` | `tests/fixtures/builders.py` | Full orchestrator with in-memory DB and loaded scenario |
| `make_mock_fast_adapter()` | `tests/fixtures/builders.py` | Fast adapter that returns canned intent/action results |
| `make_mock_main_adapter()` | `tests/fixtures/builders.py` | Main adapter that returns canned narration |
| `make_mock_job_queue()` | `tests/fixtures/telegram_builders.py` | Mock PTB job_queue for timer scheduling tests |

### Existing fixtures to extend

| Fixture | Change |
|---|---|
| `make_context()` in `telegram_builders.py` | Already updated to accept `orchestrator` parameter (done this session) |
| `make_user()` in `telegram_builders.py` | Already updated with `full_name` (done this session) |

## 7. Test Execution

All tests run via `pytest` from repo root. No special arguments needed.

```
pytest                                    # Full suite
pytest tests/unit/test_bot_handlers.py    # Just handler dispatch tests
pytest tests/integration/test_chat_turn_e2e.py  # E2E chat turn
pytest -k "test_full_turn_via_chat"       # Single test
```

New tests follow existing patterns:
- Unit tests: mock external dependencies, test one function
- Integration tests: real DB (in-memory SQLite), mock model adapters, verify multi-step flows
- No live Telegram or model calls in automated tests

## 8. Coverage Summary

| Category | Existing Tests | New Tests | Total |
|---|---|---|---|
| Bot handler dispatch | 5 (None guards only) | 9 | 14 |
| Orchestrator message handling | 0 (implicit only) | 9 | 9 |
| Auto-turn management | 0 | 7 | 7 |
| Rich narration pipeline | 103 (schema/contract) | 7 | 110 |
| Result delivery | 0 | 7 | 7 |
| Scene introduction | 0 | 5 | 5 |
| Inline keyboard / callbacks | 4 (format only) | 7 | 11 |
| Timer job integration | 10 (poll-based) | 5 | 15 |
| Question intent | 0 | 3 (in §3.2) | 3 |
| Idempotency fix | 0 | 2 (in §3.2) | 2 |
| Integration E2E | 82 | 12 | 94 |
| **Existing unchanged** | **1,479** | — | **1,479** |
| **Grand total** | **1,479** | **~73** | **~1,552** |

## 9. Mapping: PDR Verification Criteria → Tests

Every PDR §9 criterion must have at least one test that proves it. This is the traceability matrix.

| PDR Criterion | Primary Test(s) |
|---|---|
| 1. Scenario introduction | `test_newgame_shows_scenario_intro`, `test_newgame_shows_scenario_title_and_description` |
| 2. Player onboarding | `test_join_shows_cave_entrance`, `test_join_shows_scene_description`, `test_join_announces_arrival_to_group` |
| 3. Natural action submission | `test_full_turn_via_chat`, `test_pick_up_torch`, `test_group_play_action_dispatches_to_orchestrator` |
| 4. Private question | `test_private_question_via_dm`, `test_question_intent_calls_ruling`, `test_question_private_stays_private` |
| 5. All-ready early close | `test_auto_resolve_on_all_ready`, `test_multi_player_turn` |
| 6. Timeout fallback | `test_timeout_fallback_turn`, `test_timer_job_resolves_expired_turn`, `test_timer_job_generates_fallback_actions` |
| 7. Rich narration / replayability | `test_narration_calls_main_model`, `test_narration_fallback_on_model_failure` |
| 8. Private fact delivery | `test_private_facts_delivered_after_resolve`, `test_private_facts_sent_to_owning_player`, `test_other_players_do_not_receive_private_facts` |
| 9. Consecutive turns | `test_consecutive_turns_auto_open` |
