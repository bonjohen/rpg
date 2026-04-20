# STARTUP.md — Session Restore Context

Read this at the start of every session before touching any code.

## Project Summary

AI-refereed multiplayer text RPG delivered via Telegram. The game server owns state, timing, visibility, and turn commitment. The AI (fast local model + GPT-5.4 mini via OpenAI API) acts as referee voice, narrator, and NPC presenter. Players interact via a Telegram supergroup (public party chat) and private DMs (hidden info, rules questions).

## Active Plan

`docs/plan.md` — work one phase at a time, one task at a time.

Current phase: **Database Phase 6 — Startup Recovery and Multi-Campaign Support** (next). Active plan: `docs/database_plan.md`.

All 20 original phases complete. Database integration plan (`docs/database_plan.md`, 7 phases) is now active:
- **DB Phase 1** (complete): SQLite pragmas, optimistic locking, test fixtures.
- **DB Phase 2** (complete): `session_factory` on orchestrator, `_session_scope()` context manager, `_run_in_session()` async helper, `create_api_app()` accepts session factory.
- **DB Phase 3** (complete): Removed all 12 in-memory entity dicts from orchestrator, all entity reads/writes go through repos, added 20+ query methods, updated all tests. 1314 tests pass, lint clean.
- **DB Phase 4** (complete): Migrated `open_turn()`, `submit_action()`, `resolve_turn()` to use database repos. `resolve_turn()` uses split-session pattern (load → compute → version-checked commit with `StaleStateError` retry). Refactored action effects to working-set pattern. Removed `self.turn_windows`, `self.committed_actions`, `self.turn_log` in-memory dicts. 1314 tests pass, lint clean.
- **DB Phase 5** (complete): Bot commands migrated from dict access to query methods. Session factory injected into routes module. API routes were already migrated in Phases 3–4. Added `list_for_campaign()` to `TurnWindowRepo`, `get_turn_windows()` to orchestrator. 1314 tests pass, lint clean.
- **DB Phase 6** (next): Startup recovery/multi-campaign.
- **DB Phase 7** (future): Documentation/cleanup.

## Key Design Decisions (do not revisit without cause)

- **Server is referee authority.** The LLM narrates; the server decides legality, randomization, visibility, and state commits.
- **Two-tier LLM routing.** Fast local model handles cheap/structured tasks. Main tier (GPT-5.4 mini via OpenAI API, or Gemma 4 26B A4B via local OpenAI-compatible endpoint) handles narration, NPC dialogue, and arbitration proposals. Adapter selected at startup via `MainAdapter` protocol.
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
│   ├── plan.md              # Active phased release tracker
│   ├── phase_status.md      # Phase completion log
│   ├── architecture.md      # System architecture
│   ├── model_routing.md     # LLM routing rules
│   ├── repo_conventions.md  # Branch, commit, env, logging conventions
│   ├── testing.md           # Test strategy
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
└── tests/                   # 1314 tests (unit + integration)
```

## Known Defects / Open Issues

See `docs/bugs.md` for the full bug tracker (86 bugs) and `docs/release_readiness.md` for release criteria.

**P0 (3 — must fix):** Bot token auth bypass, path traversal in /newgame, scope grant leakage.
**P1 (21 — must fix):** Combat pipeline inconsistencies, HP clamping, permanent status effects, NPC trust rollback, bot handler None guards, contract drift, timer state machine gaps, idempotency, multi-scene scope, turn recovery, model recovery.
**P2 (48):** Various correctness, performance, error handling, and design issues.
**P3 (14):** Data model enhancements, minor correctness, performance.

## Phase Completion Log

See `docs/phase_status.md` for the authoritative phase log.

## Environment Quick Reference

- Python version: see `docs/repo_conventions.md`
- Secrets: see `docs/repo_conventions.md`
- Run tests: `pytest`
- Lint: `ruff check . && ruff format --check .`
- Never push without explicit per-message authorization
