# Testing Strategy

## Philosophy

Tests verify behavior, not implementation details. The game server's correctness is what matters — not internal wiring. Tests should be fast, deterministic, and runnable without a live Telegram connection or live model inference.

## Test Runner

```
pytest
```

Run from the repo root. No special arguments needed for the default suite.

## Linting

```
ruff check .
ruff format --check .
```

Both must be clean before any phase commit.

## Test Layers

### Unit Tests

Cover individual functions and classes in isolation:

- State machine transitions (Scene, TurnWindow, CommittedAction)
- Turn engine logic (open, lock, resolve, commit, abort, replay)
- Scope enforcement rules (who can see what)
- Timer logic (expiry, early-close, pause)
- Action validation (late-submission rejection, one-action-per-player)
- Rules resolution functions
- Commit ordering (deterministic given same input)

No database, no network, no model calls in unit tests. Use fixtures and simple in-memory fakes.

### Integration Tests (Persistence)

Cover storage round-trips:

- Create / load / update for all core entities
- Append-only turn log: write and replay
- State persistence across simulated restarts
- Fixture builders for core entities (Campaign, Player, Character, Scene, TurnWindow, NPC, MonsterGroup)

Use a real test database (SQLite or equivalent). Never mock the database layer — integration tests must verify actual SQL/ORM behavior.

### Telegram Payload Tests

Cover the bot gateway layer:

- Incoming message parsing (public group, private DM, callback queries)
- Command routing (/start, /join, /help, /status, /ready, /pass)
- User-to-player and chat-to-campaign mapping
- Outbound message construction (public, private DM)
- Topic-aware message routing (message_thread_id handling)
- Inline keyboard construction

Use fixture payloads from real Telegram Bot API shapes. Never hit the live Bot API in automated tests.

### LLM Routing Tests

Cover the routing layer and model adapters:

- Fast-tier intent classification (correct bucket for simple inputs)
- Action packet extraction (correct fields from raw player text)
- Scope suggestion (public vs. private-referee vs. side-channel)
- Schema validation and repair logic
- Fallback behavior when a model returns invalid output or times out
- Prompt assembly for narration, dialogue, arbitration (regression fixtures)
- Scope-safe context assembly (no referee-only facts leak into player-visible prompts)

Use recorded model outputs as fixtures. Do not invoke live model inference in the standard test suite.

### Scenario-Level Tests

Cover higher-level game behavior from scenario fixtures:

- Exploration: movement, inspection, trigger resolution, clue delivery
- Social: NPC trust change, stance change, memory persistence
- Combat: hit resolution, morale change, grouped enemies, end conditions
- Side-channel secrecy and public prompt isolation
- Split-party scene isolation

Use scripted scenario slices (JSON or YAML fixture files). No live Telegram, no live model.

### Chat-Driven Game Loop Tests

Cover the end-to-end chat interaction pipeline:

- Scene introduction on `/newgame` and `/join` (`tests/unit/test_scene_introduction.py`)
- Bot handler dispatch and orchestrator wiring (`tests/unit/test_bot_handlers.py`)
- Orchestrator message handling and intent routing (`tests/unit/test_orchestrator_message.py`)
- Auto-turn management: ensure_turn_open, race guards (`tests/unit/test_auto_turn.py`)
- Rich narration pipeline: main model call + fallback (`tests/unit/test_narration_pipeline.py`)
- Turn result delivery: public narration + private DMs (`tests/unit/test_delivery.py`)
- Inline keyboard and callback queries: Ready/Pass buttons (`tests/unit/test_callback_queries.py`)
- Timer job integration: schedule, fire, skip, cancel (`tests/unit/test_timer_job.py`)
- E2E chat turn lifecycle (`tests/integration/test_chat_turn_e2e.py`)
- Goblin caves scenario playthrough (`tests/integration/test_goblin_caves_playthrough.py`)

Use mock model adapters (canned intent/action/narration) and in-memory SQLite. No live Telegram or model calls.

## Fixtures

- Entity fixture builders live in `tests/fixtures/` (builders.py plus per-scenario fixtures)
- Telegram payload builders in `tests/fixtures/telegram_builders.py` (make_user, make_group_message, make_private_message, make_update, make_callback_query, make_callback_update, make_context)
- Combat scenario fixtures in `tests/fixtures/combat_scenario.py`
- Exploration scenario fixtures in `tests/fixtures/exploration_scenario.py`
- NPC social scenario fixtures in `tests/fixtures/npc_social_scenario.py`
- Split-party scenario fixtures in `tests/fixtures/split_party_scenario.py`

## Failure-Path Coverage

Every phase that adds reliability or recovery logic must include failure-path tests:

- Retry handling (Telegram delivery failures)
- Duplicate-delivery protection (idempotency)
- Model timeout and recovery
- Crash-safe turn recovery (restart mid-turn)
- Late submission rejection after turn lock

## What Not to Test

- Internal implementation details that are likely to change
- Live Telegram API behavior (tested manually before production)
- Live model inference quality (tested manually via playtest)
- Formatting and whitespace (covered by ruff)

## Regression Protocol

When a bug is found in playtest or production, a failing test must be added before the fix is committed. The test lives in the most specific layer where it fits (unit > integration > scenario).
