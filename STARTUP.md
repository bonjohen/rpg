# STARTUP.md — Session Restore Context

Read this at the start of every session before touching any code.

## Project Summary

AI-refereed multiplayer text RPG delivered via Telegram. The game server owns state, timing, visibility, and turn commitment. The AI (fast local model via Ollama + main tier via Gemma 4 26B A4B or GPT-5.4 mini) acts as referee voice, narrator, and NPC presenter. Players interact via a Telegram supergroup (public party chat) and private DMs (hidden info, rules questions). All game state is persisted to SQLite (dev) or PostgreSQL (production) via SQLAlchemy repositories.

## Active Plan

`docs/chat_loop_plan.md` — 9-phase plan to wire the chat-driven game loop. Work one phase at a time, one task at a time.

**Current phase: Phase 9 (Documentation and Cleanup) — Phases 1-8 complete, 1550 tests pass.**

### Chat-Driven Game Loop

The core UX problem: all infrastructure (turn engine, scope, combat, models, persistence, 1479 tests) exists, but bot handlers log and drop player messages instead of dispatching to the orchestrator. The design doc describes a conversational game loop; the implementation requires slash commands for every action. This plan closes that gap.

**Design docs:**
- `docs/chat_loop_pdr.md` — Physical design requirements (7 integration gaps, async/sync boundary, scope safety, replayability)
- `docs/chat_loop_test_plan.md` — ~73 new tests across 8 specification sections
- `docs/chat_loop_plan.md` — 9-phase implementation plan

**Phases:**
1. Scene Introduction & Scenario Metadata — `/newgame` and `/join` produce narrative output
2. Bot Handler Dispatch & Orchestrator Wiring — messages dispatch to orchestrator
3. Auto-Turn Management — turns open/resolve automatically
4. Rich Narration & Result Delivery — main model narration, private facts via DM
5. Inline Keyboard & Callback Queries — Ready/Pass buttons
6. Timer Expiry via Job Queue — PTB `job_queue.run_once()` auto-resolve
7. Question Intent Handling — AI responses via `propose_ruling()`
8. E2E Integration Tests — goblin_caves playthrough, PDR §9 verification
9. Documentation & Cleanup

### Prior Completed Plans

All 20 original phases, 7 database integration phases, 7 P0/P1 bug-fix phases, and 7 P2 bug-fix phases are complete:
- **DB Phase 1-7**: Full database integration (SQLite/PostgreSQL via SQLAlchemy, repositories, optimistic locking). 1327 tests.
- **Bug-fix Phase 1-7 (P0/P1)**: 24 bugs fixed across security, bot handlers, combat, contracts, timer, NPC, reliability. 1396 tests pass.
- **P2 Bug-fix Phase 1-7**: 48 P2 bugs fixed across API auth, timer arithmetic, combat scaling, exploration state, NPC types, model contracts, API routes, bot safety, scenario errors, connection reuse, datetime hardening, replay warnings. 1479 tests pass.
- **P3 Bug fixes**: 12 of 13 P3 bugs fixed (correctness, performance, data model). Enum type safety for NPC/MonsterGroup fields, BFS deque optimization, set-based lookups, quest title persistence, exploration memory text, side channel typing, scope nullability.
- **App wiring**: dotenv loading, GameOrchestrator creation at startup, `/join` calls `add_player()`, campaign dedup on `/newgame`.
- **Chat loop Phases 1-8**: Scene introductions, handler dispatch, auto-turn management, rich narration, inline keyboard turn controls, timer expiry via job queue, question intent handling, E2E integration tests. 1550 tests pass.

## Key Design Decisions (do not revisit without cause)

- **Server is referee authority.** The LLM narrates; the server decides legality, randomization, visibility, and state commits.
- **Two-tier LLM routing.** Fast local model (qwen2.5:1.5b via Ollama) handles cheap/structured tasks. Main tier (Gemma 4 26B A4B via local OpenAI-compatible endpoint, or GPT-5.4 mini via OpenAI API) handles narration, NPC dialogue, and arbitration proposals. Adapter selected at startup via `MainAdapter` protocol.
- **Scope is explicit in data.** Public / private-referee / side-channel / referee-only are first-class data fields, not inferred from chat structure.
- **One committed action packet per player per turn.** Free chat is separate from resolution input.
- **Append-only turn log.** All committed results are written and never overwritten. Replay is a design requirement.
- **No push without explicit per-message authorization.** Commits stay local.

## Repo Layout

```
C:\Projects\rpg\
├── STARTUP.md               # This file
├── CLAUDE.md                # Claude Code project instructions
├── docs/
│   ├── plan.md              # Original 20-phase release tracker (complete)
│   ├── database_plan.md     # Database integration plan (7 phases, complete)
│   ├── database_design.md   # Database design document
│   ├── phase_status.md      # Phase completion log
│   ├── architecture.md      # System architecture
│   ├── model_routing.md     # LLM routing rules
│   ├── repo_conventions.md  # Branch, commit, env, logging conventions
│   ├── testing.md           # Test strategy
│   ├── bugs.md              # Bug tracker (88 bugs, 87 resolved, 1 open)
│   ├── release_readiness.md # Open bugs and release criteria
│   ├── design.md            # Original design document
│   └── pdr.md               # Product design requirements
├── server/                  # Game server (Python)
│   ├── api/                 # REST API for Mini App (FastAPI)
│   ├── orchestrator/        # Top-level game loop (GameOrchestrator)
│   ├── scope/               # Scope engine, leakage guard, referee guard
│   ├── engine/              # Turn engine
│   ├── combat/              # Combat loop, conditions, dice
│   ├── exploration/         # Movement, triggers, actions, clues, objects
│   ├── npc/                 # NPC social engine, trust, memory
│   ├── scene/               # Scene membership
│   ├── timer/               # Timer controller
│   ├── storage/             # ORM models, repositories, database setup
│   ├── reliability/         # Idempotency, retry, recovery
│   ├── observability/       # Diagnostics, metrics
│   └── domain/              # Entities, enums (pure data, no I/O)
├── bot/                     # Telegram bot gateway
├── models/                  # Inference adapters (fast + main tier)
│   ├── protocol.py          # MainAdapter protocol (shared interface)
│   ├── fast/                # Fast local model (qwen2.5:1.5b) adapter
│   ├── main/                # Main model (GPT-5.4 mini via OpenAI) adapter
│   ├── gemma/               # Gemma 4 26B A4B adapter (OpenAI-compatible endpoint)
│   └── contracts/           # Prompt contracts and context assembly
├── scenarios/               # Scenario YAML files, loader, validator
│   └── starters/            # 4 starter scenarios (goblin_caves, haunted_manor, forest_ambush, merchant_quarter)
├── webapp/                  # Mini App frontend (HTML/JS/CSS)
├── docs/                    # Design docs, plan, release readiness
│   ├── chat_loop_pdr.md     # Chat-driven game loop PDR (active)
│   ├── chat_loop_test_plan.md # Chat loop test plan (~73 new tests)
│   ├── chat_loop_plan.md    # Chat loop implementation plan (active, 9 phases)
│   ├── release_readiness.md # Open bugs and release criteria
│   ├── feature_freeze.md   # Feature freeze notice
│   ├── miniapp_architecture.md # Mini App architecture
│   └── code_review.md      # Code review instructions
└── tests/                   # 1479 tests (unit + integration)
```

## Known Defects / Open Issues

See `docs/bugs.md` for the full bug tracker (88 bugs) and `docs/release_readiness.md` for release criteria.

**P0 (3 — all fixed):** Bot token auth bypass, path traversal in /newgame, scope grant leakage.
**P1 (21 — all fixed):** Combat pipeline, NPC trust rollback, bot handler None guards, contract drift, timer, idempotency, scope, recovery, model adapters.
**P2 (48 — all fixed):** API auth, timer arithmetic, combat scaling, exploration state, NPC types, model contracts, API routes, bot safety, scenario errors, connection reuse, datetime hardening, replay warnings.
**P3 (16, 15 fixed):** Only BUG-002 (narration fallback text repetitive) remains open. Fixed: enum type safety, BFS optimization, set-based lookups, quest title persistence, exploration memory, side channel typing, scope nullability, dead code removal.

## Phase Completion Log

See `docs/phase_status.md` for the authoritative phase log.

## Environment Quick Reference

- Python version: 3.14+ (3.14 in use locally)
- Database: SQLite by default (`sqlite:///rpg.db`), PostgreSQL via `DATABASE_URL` env var
- Environment variables: loaded from `.env` via `python-dotenv` in `bot/__main__.py`
  - `BOT_TOKEN` — Telegram bot token (from BotFather)
  - `GROUP_CHAT_ID` — Telegram supergroup chat ID
  - `OPENAI_API_KEY` — system env var (not in .env), used by main model adapter
  - `FAST_MODEL_BASE_URL` — Ollama endpoint (default `http://localhost:11434`)
- Startup: `python -m bot` from project root. Creates DB tables, loads orchestrator with all subsystems.
- Startup recovery: `GameOrchestrator.startup()` creates tables, loads campaigns, reconstructs timers, recovers stuck turns
- Run tests: `pytest`
- Lint: `ruff check . && ruff format --check .`
- Never push without explicit per-message authorization
