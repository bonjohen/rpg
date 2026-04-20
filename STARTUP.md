# STARTUP.md — Session Restore Context

Read this at the start of every session before touching any code.

## Project Summary

AI-refereed multiplayer text RPG delivered via Telegram. The game server owns state, timing, visibility, and turn commitment. The AI (fast local model via Ollama + main tier via Gemma 4 26B A4B or GPT-5.4 mini) acts as referee voice, narrator, and NPC presenter. Players interact via a Telegram supergroup (public party chat) and private DMs (hidden info, rules questions). All game state is persisted to SQLite (dev) or PostgreSQL (production) via SQLAlchemy repositories.

## Active Plan

`docs/plan.md` — work one phase at a time, one task at a time.

Current phase: **Bug-fix plan complete.** All P0+P1 bugs closed. Active plan: `docs/bugfix_plan.md`.

All 20 original phases, 7 database integration phases, and 7 bug-fix phases are complete:
- **DB Phase 1-7**: Full database integration (SQLite/PostgreSQL via SQLAlchemy, repositories, optimistic locking). 1327 tests.
- **Bug-fix Phase 1 (P0)**: Auth bypass, path traversal, scope leakage — all 3 P0 security bugs closed.
- **Bug-fix Phase 2**: Bot handler None guards and registry fallback.
- **Bug-fix Phase 3**: Combat HP clamp, damage delegation, status cleanup, morale enum.
- **Bug-fix Phase 4**: Prompt contract alignment with schema validators.
- **Bug-fix Phase 5**: Timer state machine, deterministic idempotency keys, per-scene public scopes.
- **Bug-fix Phase 6**: NPC trust rollback on failure, scene transfer atomicity with logging.
- **Bug-fix Phase 7**: Model adapter failure reporting (async fallback, empty choices). 1396 tests pass.

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
│   ├── bugs.md              # Bug tracker (89 bugs)
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
│   ├── release_readiness.md # Open bugs and release criteria
│   └── feature_freeze.md   # Feature freeze notice
└── tests/                   # 1396 tests (unit + integration)
```

## Known Defects / Open Issues

See `docs/bugs.md` for the full bug tracker (89 bugs) and `docs/release_readiness.md` for release criteria.

**P0 (3 — all Fixed):** Bot token auth bypass, path traversal in /newgame, scope grant leakage.
**P1 (21 — all Fixed):** Combat pipeline, NPC trust rollback, bot handler None guards, contract drift, timer, idempotency, scope, recovery, model adapters.
**P2 (49, 1 fixed):** Various correctness, performance, error handling, and design issues. BUG-049 (combat_summary fallback invalid tone) fixed as bonus.
**P3 (16, 1 closed):** Data model enhancements, minor correctness, performance. BUG-003 (persistent storage) closed.

## Phase Completion Log

See `docs/phase_status.md` for the authoritative phase log.

## Environment Quick Reference

- Python version: 3.12+ (see `docs/repo_conventions.md`)
- Database: SQLite by default (`sqlite:///rpg.db`), PostgreSQL via `DATABASE_URL` env var
- Startup recovery: `GameOrchestrator.startup()` creates tables, loads campaigns, reconstructs timers, recovers stuck turns
- Secrets: see `docs/repo_conventions.md`
- Run tests: `pytest`
- Lint: `ruff check . && ruff format --check .`
- Never push without explicit per-message authorization
