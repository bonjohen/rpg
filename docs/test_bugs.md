# Test Code Revision List

**Audit date:** 2026-04-20
**Evaluation criteria:** `docs/test_evaluation_criteria.md`
**Scope:** All 1550 tests across `tests/unit/` and `tests/integration/`

---

## Severity Definitions

| Severity | Meaning |
|---|---|
| **P0** | Could cause false positives (tests pass when they shouldn't) or hides real bugs |
| **P1** | Maintainability hazard — slows future work, causes confusion, or makes tests fragile |
| **P2** | Quality/hygiene issue — not urgent but compounds over time |

---

## TBUG-001: Duplicated `_make_orchestrator` helper across 12 files

**Severity:** P1
**Criteria:** §2 Centralized fixture modules, §7 DRY without obscuring, §10 Copy-paste tests
**Files:** `test_auto_turn.py`, `test_orchestrator_message.py`, `test_chat_turn_e2e.py`, `test_goblin_caves_playthrough.py`, `test_callback_queries.py`, `test_timer_job.py`, `test_api_gameplay.py`, `test_api_routes.py`, `test_database_startup_recovery.py`, `test_p2_bugfix_security.py`, `test_scene_introduction.py`, `test_playtest_setup.py`

**Finding:** 12 independent `_make_orchestrator()` functions with slightly different signatures. Each constructs a `GameOrchestrator` with `create_test_session_factory()`, loads a minimal scenario, and adds players. The core pattern is identical; the variations are in which optional parameters they accept (`fast_adapter`, `main_adapter`, scenario path, player count).

**Revision:** Extract a single `make_test_orchestrator()` into `tests/fixtures/builders.py` (or a new `tests/fixtures/orchestrator_builder.py`) that accepts all optional parameters with defaults. Replace the 12 copies. Each test file imports from the shared builder.

---

## TBUG-002: Duplicated `_mock_classify` / `_mock_extract` helpers across 3 files

**Severity:** P1
**Criteria:** §2 Centralized fixture modules, §10 Copy-paste tests
**Files:** `test_orchestrator_message.py`, `test_chat_turn_e2e.py`, `test_goblin_caves_playthrough.py`

**Finding:** Three nearly identical `_mock_classify(intent)` and `_mock_extract(action_type)` functions that build canned `IntentClassificationResult` / `ActionPacketResult` returns. The signatures differ trivially (some accept `confidence`, some don't).

**Revision:** Extract `mock_classify_intent()` and `mock_extract_action()` into `tests/fixtures/` (e.g., `model_mock_helpers.py`). Unify the signature to accept all variants with defaults.

---

## TBUG-003: Duplicated `_make_config()` helper across 3 files

**Severity:** P2
**Criteria:** §2 Centralized fixture modules
**Files:** `test_bot_handlers.py`, `test_callback_queries.py`, `test_delivery.py`

**Finding:** Three identical one-liner `_make_config()` → `BotConfig(group_chat_id=-1001234567890)`. Trivial but a maintenance hazard if `BotConfig` gains required fields.

**Revision:** Add `make_bot_config()` to `tests/fixtures/telegram_builders.py` alongside the existing payload builders.

---

## TBUG-004: Duplicated `_add_player` helper across 4 files

**Severity:** P2
**Criteria:** §2 Centralized fixture modules
**Files:** `test_auto_turn.py`, `test_orchestrator_message.py`, `test_chat_turn_e2e.py`, `test_api_routes.py` (as `_add_players`)

**Finding:** Slight variations of a 2-line helper that calls `orch.add_player()` and returns the player ID. Would break uniformly if `add_player` signature changes.

**Revision:** Include in the shared orchestrator builder from TBUG-001, or add a standalone `add_test_player()` to `tests/fixtures/builders.py`.

---

## TBUG-005: Duplicated `_make_scene` helper across 5 files

**Severity:** P2
**Criteria:** §2 Centralized fixture modules
**Files:** `test_narration_pipeline.py`, `test_delivery.py`, `test_scene_introduction.py`, `test_bugfix_npc_scene.py`, `test_p2_bugfix_timer_diagnostics.py`

**Finding:** Five independent `_make_scene()` functions that construct a `Scene` entity with slightly different defaults. The centralized `make_scene()` already exists in `tests/fixtures/builders.py` (via `make_scene` or per-scenario fixture modules) but is not used by these files.

**Revision:** Replace local `_make_scene()` with imports from existing `tests/fixtures/builders.py`, adding defaults as needed.

---

## TBUG-006: Duplicated `_make_log_entry` helper across 2 files

**Severity:** P2
**Criteria:** §2 Centralized fixture modules
**Files:** `test_narration_pipeline.py`, `test_delivery.py`

**Finding:** Two similar `_make_log_entry()` helpers constructing `TurnLogEntry`. `make_turn_log_entry()` already exists in `tests/fixtures/builders.py`.

**Revision:** Replace with imports from `tests/fixtures/builders.py`.

---

## TBUG-007: Duplicated `_scope()` helper across 2 files

**Severity:** P2
**Criteria:** §2 Centralized fixture modules
**Files:** `test_scope_engine.py`, `test_bugfix_p0.py`

**Finding:** Identical `_scope()` helper that constructs a `ConversationScope` with generated IDs. The fixture module `tests/fixtures/builders.py` already has scope-related builders, but these two files each re-implement.

**Revision:** Add `make_scope()` to `tests/fixtures/builders.py` and replace local copies.

---

## TBUG-008: No `pytest.mark.parametrize` usage in test suite (except 2 files)

**Severity:** P1
**Criteria:** §10 Copy-paste tests, §7 Proportional complexity
**Files:** Suite-wide (1550 tests, only 17 parametrize markers across 2 files)

**Finding:** Many test classes contain 5-10 methods that differ only in the input value (e.g., `TestAwarenessTransitions` has 9 methods each calling `transition_awareness` with a different trigger; `TestMonsterBehavior` has 11 methods each calling `decide_action` with a different mode). These are candidates for `@pytest.mark.parametrize`, which would reduce line count, make it trivial to add new cases, and make the pattern explicit.

**Revision candidates:**
- `test_combat.py` `TestAwarenessTransitions` (9 near-identical methods)
- `test_combat.py` `TestMonsterBehavior` (11 methods varying on behavior_mode/awareness)
- `test_scope_engine.py` `TestCanPlayerSeeFact` (7 methods varying on scope_type)
- `test_turn_engine.py` `TestAssertTransition` (5 methods varying on from/to state)

Low-risk refactor: convert the most repetitive classes; leave those where the test body is genuinely different.

---

## TBUG-009: Module-level mutable singletons shared across tests

**Severity:** P1
**Criteria:** §6 Test independence, §6 No test ordering dependency
**Files:** `test_scope_engine.py` (5 singletons), `test_turn_engine.py` (1), `test_timer.py` (1)

**Finding:** Module-level `ENGINE = ScopeEngine()`, `REFEREE = RefereeGuard()`, `ENGINE = TurnEngine()`, etc. These are instantiated once and shared across every test in the module. If any engine accumulates internal state (cache, counter, logging buffer), tests can bleed into each other. Currently these engines appear stateless, but the pattern is fragile — any future state addition silently breaks isolation.

**Revision:** Move instantiation into `setup_method` (already done in `test_combat.py`, `test_exploration.py`, `test_npc_social.py` — these files do it correctly) or use a `@pytest.fixture` with function scope. This makes the isolation guarantee explicit.

---

## TBUG-010: `test_unknown_intent_falls_back_to_action` doesn't test what it claims

**Severity:** P0
**Criteria:** §3 Specific assertions, §10 Test the mock
**File:** `test_orchestrator_message.py:189-202`

**Finding:** The test name says "unknown intent falls back to action" but the mock classifies intent as `"chat"`, not `"unknown"`. The comment even acknowledges this: `# chat drops; "unknown" would too`. The test then asserts `result.handled is True`, which is true for both `chat` (no-op) and `action` (submit). The test cannot distinguish between "correctly fell back to action" and "was handled as chat and ignored." It would pass even if the unknown-intent fallback were completely broken.

**Revision:** Change mock to return `intent="unknown"` (or `"gibberish"`). Assert `result.action_submitted is True` to confirm it actually fell through to the action path. Add a separate test for `intent="chat"` if one doesn't already exist (it does: `test_chat_intent_returns_empty`).

---

## TBUG-011: `test_timeout_fallback_turn` weak assertion on fallback narration

**Severity:** P1
**Criteria:** §3 Specific assertions, §3 No logic in assertions
**File:** `test_chat_turn_e2e.py:188`

**Finding:** The assertion is:
```python
assert "hesitates" in log_entry.narration.lower() or log_entry.narration
```
The `or log_entry.narration` clause makes this always true for any non-empty string, regardless of content. This was likely intended as "check for 'hesitates' OR just verify narration exists" but the logical OR makes the first condition irrelevant.

**Revision:** Either assert on the specific fallback string (`assert "hesitates" in ...`) or just assert existence (`assert log_entry.narration`). Not both via `or`.

---

## TBUG-012: `test_newgame_shows_scenario_intro` weak assertion via stringified call_args

**Severity:** P1
**Criteria:** §3 Specific assertions
**File:** `test_goblin_caves_playthrough.py:78`

**Finding:**
```python
full_text = " ".join(str(c) for c in reply_calls)
assert "Goblin Caves" in full_text or "goblin" in full_text.lower()
```
Joining `str(call_args)` representations and searching for substrings is fragile — it depends on `unittest.mock`'s string representation format. A mock internals change could break this. The `or` fallback (`"goblin" in full_text.lower()`) is extremely permissive — any mention of "goblin" passes, even error messages.

**Revision:** Extract the actual text argument from `reply_calls[0][0][0]` (the first positional arg) and assert on that directly. Same issue in `test_join_shows_cave_entrance` at line 105.

---

## TBUG-013: Almost zero `@pytest.fixture` usage — all test setup is manual

**Severity:** P2
**Criteria:** §2 Setup and fixtures, §8 Lazy expensive setup
**Files:** Suite-wide

**Finding:** Only 5 `@pytest.fixture` markers in the entire suite (2 in `test_database_session_scope.py`, 2 in `test_persistence.py`, 1 shared). Every other test file uses module-level helpers or `setup_method` for setup. This means:
- No session/module-scoped fixtures for expensive operations (DB creation, scenario loading)
- No automatic teardown guarantees
- Every test that needs an orchestrator + DB does the full `create_test_session_factory()` + `load_scenario()` cycle independently

Not wrong, but the `test_playtest_session.py` and `test_extended_session.py` integration tests each call `_setup_game()` per test method, creating and populating an in-memory DB every time. If the suite grows, this will become a performance bottleneck.

**Revision:** Introduce session-scoped or module-scoped `@pytest.fixture` for the in-memory DB factory. Consider a module-scoped fixture for the loaded-scenario orchestrator in integration tests where the scenario is read-only.

---

## TBUG-014: `test_action_extraction_failure_fallback` doesn't verify fallback logic

**Severity:** P1
**Criteria:** §5 Error path coverage, §3 Specific assertions
**File:** `test_orchestrator_message.py:286-307`

**Finding:** The test claims to verify what happens when the fast model returns "garbage" (`action_type="totally_invalid_type"`), but it only asserts `result.action_submitted is True`. It doesn't verify that the invalid type was actually normalized to `"custom"` (the expected fallback). If the code just blindly accepted any string as an action type, this test would still pass.

**Revision:** Assert on the actual action type that was submitted (e.g., check the committed action's `declared_action_type` via the orchestrator or DB).

---

## TBUG-015: `test_timer_job_generates_fallback_actions` tests nothing beyond `resolve_turn` call

**Severity:** P1
**Criteria:** §10 Test the mock, §3 Specific assertions
**File:** `test_timer_job.py:136-157`

**Finding:** The docstring says "Timer expires with missing submissions -> resolve_turn synthesizes fallbacks." The test then immediately admits in a comment: "The fallback action generation happens inside resolve_turn, so we verify resolve_turn is called (it handles fallback internally)." This is verifying the mock was called, not that fallback actions were generated. It's a duplicate of `test_timer_job_resolves_expired_turn` with different prose.

**Revision:** Either (a) make this a proper integration test using a real orchestrator with 2 players where one hasn't submitted, verify the resulting log_entry contains a hold/fallback for the missing player; or (b) remove this test as a duplicate of `test_timer_job_resolves_expired_turn` and add a note that fallback generation is tested in `test_playtest_session.py` or wherever it's actually exercised.

---

## TBUG-016: `test_callback_queries.py` `_make_orchestrator` builds a MagicMock, not a real orchestrator

**Severity:** P2
**Criteria:** §4 Fake over mock when stateful, §4 Canned responses are realistic
**File:** `test_callback_queries.py:27-62`

**Finding:** Unlike most other test files that build a real `GameOrchestrator` with an in-memory DB, this file's `_make_orchestrator` returns a `MagicMock` with manually configured return values. This means the tests verify that the handler reads mock attributes correctly, but don't verify actual orchestrator behavior (e.g., does `submit_action` with `ActionType.hold` actually succeed for a registered player with an open turn?).

This is acceptable for pure handler-layer tests, but the docstring "Tests per chat_loop_test_plan §3.7" doesn't distinguish between handler-only and end-to-end. The test name `test_ready_button_submits_hold_action` sounds like it verifies the full path but only tests the handler's mock wiring.

**Revision:** Either (a) rename tests to clarify they're handler-layer-only (e.g., `test_ready_button_calls_submit_action`) or (b) add one integration test that uses a real orchestrator to verify the Ready button actually results in a committed hold action in the DB.

---

## TBUG-017: No negative test for `ensure_turn_open` with unknown scene

**Severity:** P1
**Criteria:** §5 Boundary conditions, §3 Negative assertions
**File:** `test_auto_turn.py`

**Finding:** Tests cover `creates_turn_when_none_active`, `returns_existing_when_active`, and `race_condition_guard`, but no test verifies what happens when `ensure_turn_open("nonexistent_scene")` is called. Does it raise? Return None? The behavior is unspecified by tests.

**Revision:** Add `test_ensure_turn_open_unknown_scene_raises` (or `_returns_none`, depending on expected behavior).

---

## TBUG-018: No test for duplicate `/join` by same player

**Severity:** P1
**Criteria:** §5 Boundary conditions, §5 Concurrency / race conditions
**File:** `test_scene_introduction.py`

**Finding:** Tests cover successful join and announcement, but no test verifies what happens when the same player sends `/join` twice. Does it error gracefully? Does it produce a duplicate announcement? The orchestrator has dedup logic but it's not exercised from the bot command layer.

**Revision:** Add `test_join_duplicate_player_is_rejected_or_idempotent`.

---

## TBUG-019: No test for callback button with unknown `callback_data`

**Severity:** P2
**Criteria:** §5 Boundary conditions
**File:** `test_callback_queries.py`

**Finding:** Tests cover `CALLBACK_READY`, `CALLBACK_PASS`, non-player rejection, and post-resolve rejection. No test verifies what happens when `callback_data` is an unexpected string (e.g., `"turn:bogus"` or `""`). If a user tampers with callback data, the handler should respond gracefully.

**Revision:** Add `test_unknown_callback_data_rejected_gracefully`.

---

## TBUG-020: `test_goblin_caves_playthrough.py` tests don't verify game state changes

**Severity:** P1
**Criteria:** §3 Specific assertions, §5 State transitions
**File:** `test_goblin_caves_playthrough.py`

**Finding:** All 6 playthrough tests assert only `action_submitted`, `turn_resolved`, and `handled`. None verify actual game state changes:
- `test_pick_up_torch` doesn't check that the torch is in inventory
- `test_enter_cave_triggers_lookout` doesn't check that the player moved scenes or that the lookout trigger fired
- `test_talk_to_grix` doesn't check NPC trust changes

These tests verify the orchestrator's message pipeline works, but they don't verify the scenario-specific gameplay outcomes that make this a "goblin caves playthrough" test rather than a generic "orchestrator handles messages" test.

**Revision:** Add game-state assertions: inventory contains torch, player is now in a different scene, NPC trust changed, etc. If these assertions are hard to make through the `handle_player_message` path (because the mock extract bypasses real action processing), document that limitation explicitly and link to the integration tests in `test_playtest_session.py` that do verify state.

---

## TBUG-021: `test_bot_handlers.py` tests are brittle to `send_public` call signature

**Severity:** P2
**Criteria:** §4 Verify mock interactions sparingly
**File:** `test_bot_handlers.py:122`

**Finding:** `assert "Action submitted" in mock_pub.call_args[0][2]` — this depends on positional argument index (the 3rd positional arg). If `send_public` adds or reorders parameters, this breaks even if the behavior is correct. Multiple tests in this file use positional index access into `call_args`.

**Revision:** Use keyword arguments in the production code and assert against `call_args.kwargs["text"]`, or use `mock_pub.call_args_list` with a more semantic check.

---

## TBUG-022: No conftest.py for shared fixtures or marks

**Severity:** P2
**Criteria:** §2 Centralized fixture modules, §8 Parallelizable
**Files:** Suite-wide

**Finding:** No `conftest.py` files exist in `tests/`, `tests/unit/`, or `tests/integration/`. All fixture sharing happens via explicit imports from `tests/fixtures/`. This works, but means:
- No central place to register custom marks
- No session-scoped DB factory
- No `asyncio_mode` configuration (each async test needs `@pytest.mark.asyncio` individually)
- `pytest-xdist` parallelization would require manual discovery of sharing constraints

**Revision:** Add minimal `conftest.py` files with:
- `tests/conftest.py`: configure `asyncio_mode = "auto"` (eliminates ~50 `@pytest.mark.asyncio` decorators), register custom marks
- `tests/integration/conftest.py`: session-scoped DB factory fixture
- `tests/unit/conftest.py`: any shared unit-test fixtures

---

## Summary

| Severity | Count | Description |
|---|---|---|
| P0 | 1 | TBUG-010: test asserts wrong thing (false positive risk) |
| P1 | 9 | TBUG-001, 002, 008, 009, 010, 011, 014, 015, 017, 018, 020: duplication, weak assertions, missing coverage |
| P2 | 8 | TBUG-003–007, 013, 016, 019, 021, 022: hygiene, minor duplication, missing infrastructure |

### Recommended fix order

1. **TBUG-010** (P0) — Fix the false positive. Immediate.
2. **TBUG-011, 012, 014** (P1) — Fix weak/misleading assertions. Same commit.
3. **TBUG-015, 020** (P1) — Either fix or document the mock-only tests. Same commit.
4. **TBUG-001, 002** (P1) — Extract shared helpers. One refactor commit.
5. **TBUG-008, 009** (P1) — Parametrize and fix singletons. One commit each.
6. **TBUG-017, 018, 019** (P1/P2) — Add missing boundary tests. One commit.
7. **TBUG-003–007, 006** (P2) — Minor dedup. Can batch with TBUG-001.
8. **TBUG-013, 016, 021, 022** (P2) — Infrastructure improvements. Separate commit.
