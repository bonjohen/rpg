# Phase Status Log

Record each phase completion here. One row per phase, filled in at Phase End.

| Phase | Title | Status | Completed (PST) | Notes |
|---|---|---|---|---|
| 0 | Repository Foundation and Startup Context | Completed | 2026-04-18 09:16 AM | |
| 1 | Core Domain Model and Persistence | Completed | 2026-04-18 09:52 AM | |
| 2 | Canonical Turn Engine | Completed | 2026-04-18 10:54 PM | |
| 3 | Telegram Bot Integration Skeleton | Completed | 2026-04-18 11:27 PM | |
| 4 | Scope and Visibility Enforcement | Completed | 2026-04-18 11:58 PM | |
| 5 | Countdown Timer and Readiness Control | Completed | 2026-04-19 12:22 AM | |
| 6 | Fast Local Model Routing Layer | Completed | 2026-04-18 11:26 PM | |
| 7 | Main Gameplay Model Integration | Completed | 2026-04-18 11:46 PM | Gemma inference adapter [!] disabled; all other deliverables complete |
| 8 | Exploration Loop | Completed | 2026-04-19 12:02 AM | 97 new tests; server/exploration/ package |
| 9 | NPC Social Loop | Completed | 2026-04-19 12:12 AM | 90 new tests; server/npc/ package |
| 10 | Combat Loop | Completed | 2026-04-18 02:00 AM | 89 new tests; server/combat/ package |
| 11 | Side-Channels and Private Coordination | Completed | 2026-04-18 02:35 AM | 58 new tests; server/scope/ extensions + side_channel_engine + side_channel_audit |
| 12 | Split Party and Multi-Scene Handling | Not Started | — | |
| 13 | Scenario Authoring Format | Not Started | — | |
| 14 | Prompt Contracts and Context Assembly | Not Started | — | |
| 15 | Reliability, Recovery, and Observability | Not Started | — | |
| 16 | Internal Playtest Release | Not Started | — | |
| 17 | Mini App Foundation | Not Started | — | |
| 18 | Mini App Gameplay Utilities | Not Started | — | |
| 19 | Content Expansion and Quality Pass | Not Started | — | |
| 20 | Pre-Release Stabilization | Not Started | — | |

## Phase Notes

### Phase 0

Started: 2026-04-18

Inputs: `docs/design.md`, `docs/pdr.md` (both pre-existing from initial documentation commit).

Outputs: `STARTUP.md`, `docs/architecture.md`, `docs/testing.md`, `docs/phase_status.md`, `docs/model_routing.md`, `docs/repo_conventions.md`.

No code changes. Foundation documentation only.

### Phase 6

Started: 2026-04-18

Inputs: `server/engine/turn_engine.py`, `server/timer/`, `docs/model_routing.md` (from prior phases).

Outputs: `models/fast/adapter.py` (OllamaFastAdapter: async Ollama HTTP wrapper, failure-safe), `models/fast/instrumentation.py` (ModelCallLog), `models/fast/router.py` (TaskType enum, routing predicates), `models/fast/tasks.py` (classify_intent, normalize_command, extract_action_packet, suggest_scope, summarize_context, generate_clarification, repair_schema — all with structured JSON output and deterministic fallbacks). Added `tests/unit/test_fast_model.py` (35 tests, all passing). Added `httpx>=0.27` to `requirements.txt`.

### Phase 7

Started: 2026-04-18

Inputs: `models/fast/` (Phase 6), `docs/model_routing.md`.

Outputs: `models/main/__init__.py`, `models/main/adapter.py` (OllamaMainAdapter: async Ollama HTTP wrapper for gemma3:27b, configurable model name), `models/main/router.py` (MainTaskType enum, is_main_tier, assert_main_tier), `models/main/schemas.py` (output dataclasses + validate_* functions for all 6 main-tier task types, SchemaValidationError, SCHEMA_DESCRIPTIONS registry), `models/main/context.py` (SceneContext, PlayerContext, NpcContext, ActionContext, RecentHistory; assemble_* prompt functions for all task types; token budget helpers), `models/main/fallback.py` (deterministic fallbacks for all task types, get_fallback registry), `models/main/tasks.py` (narrate_scene, generate_npc_dialogue, summarize_combat, propose_ruling, arbitrate_social, generate_puzzle_flavor — all with full 3-step failure pipeline: validate → repair → fallback). Added `tests/fixtures/main_model_fixtures.py` (representative game state fixtures) and `tests/unit/test_main_model.py` (103 tests, all passing). The OllamaMainAdapter [!] requires live gemma3:27b; all other code fully testable via mocks. Total tests: 338, all passing.

### Phase 9

Started: 2026-04-19

Inputs: `server/domain/entities.py` (NPC entity with trust_by_player, stance_to_party, memory_tags), `server/exploration/` (pattern reference).

Outputs: `server/npc/` package — `trust.py` (TrustEngine: per-player trust deltas, party stance derivation, cooperative/hostile helpers), `tells.py` (NpcTellEngine: behavioral tell evaluation, trust-status facts, private reaction facts), `dialogue.py` (DialogueContextBuilder: structured dialogue context for main model, public/referee dict split), `social.py` (SocialEngine: question/persuade/threaten/lie/bargain resolution, memory tag updates, referee fact generation). Added `tests/fixtures/npc_social_scenario.py` (Mira the Innkeeper + Theron the Gate Guard with full tell libraries) and `tests/unit/test_npc_social.py` (90 tests, all passing). Total suite: 525 tests, all green.

### Phase 8

Started: 2026-04-19

Inputs: `server/domain/entities.py`, `server/domain/enums.py`, `server/scope/` (all from prior phases).

Outputs: `server/exploration/` package (movement.py, actions.py, triggers.py, clues.py, objects.py, memory.py), `tests/fixtures/exploration_scenario.py` (three-room dungeon fixture), `tests/unit/test_exploration.py` (97 tests, all passing). Total suite: 435 tests, all green.

### Phase 10

Started: 2026-04-18

Inputs: `server/domain/entities.py` (Character, MonsterGroup, Scene, InventoryItem), `server/domain/enums.py` (AwarenessState, BehaviorMode, ActionType).

Outputs: `server/combat/` package — `conditions.py` (CombatConditionEngine), `actions.py` (CombatActionEngine: 6 action types), `monsters.py` (MonsterBehaviorEngine + MoraleEngine), `resolution.py` (CombatResolutionEngine: damage/armor/status/defeat), `visibility.py` (CombatVisibilityEngine: awareness state machine), `summaries.py` (BattlefieldSummaryBuilder). `tests/fixtures/combat_scenario.py` (forest clearing encounter). `tests/unit/test_combat.py` (89 tests, all passing). Total suite: 614 tests, all green.

### Phase 11

Started: 2026-04-18

Inputs: `server/scope/side_channel.py` (SideChannelPolicy from Phase 4), `server/scope/engine.py` (ScopeEngine), `bot/outbound.py` (send_private_by_player_id), `server/domain/entities.py` (SideChannel, ConversationScope, KnowledgeFact).

Outputs: Extended `server/scope/side_channel.py` (add_member, remove_member with auto-close, can_create with per-player limit). Created `server/scope/side_channel_engine.py` (SideChannelEngine: create_channel, close_channel with audit fact). Created `server/scope/side_channel_audit.py` (SideChannelAuditor: record_creation, record_message, record_closure — all referee-only). Extended `bot/outbound.py` (send_side_channel DM relay). Extended `server/scope/engine.py` (assert_no_side_channel_leakage). Added `tests/fixtures/side_channel_scenario.py` and `tests/unit/test_side_channels.py` (58 tests). Total suite: 672 tests, all green.

### Phase 2

Started: 2026-04-18

Inputs: `server/domain/entities.py`, `server/domain/enums.py`, `server/storage/repository.py` (all from Phase 1).

Outputs: `server/engine/turn_engine.py`, `tests/unit/test_turn_engine.py`.

Pure domain engine with no DB calls. All lifecycle transitions, action submission, validation, rejection, timeout fallbacks, deterministic ordering, append-only log production, and replay. 54 unit tests, all passing.
