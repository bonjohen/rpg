# STARTUP.md — Session Restore Context

Read this at the start of every session before touching any code.

## Project Summary

AI-refereed multiplayer text RPG delivered via Telegram. The game server owns state, timing, visibility, and turn commitment. The AI (fast local model + Gemma 4 26B A4B) acts as referee voice, narrator, and NPC presenter. Players interact via a Telegram supergroup (public party chat) and private DMs (hidden info, rules questions).

## Active Plan

`docs/plan.md` — work one phase at a time, one task at a time.

Current phase: **Phase 20 — Pre-Release Stabilization** (completing). Phase 19 completed 2026-04-18 04:02 AM.

All 20 phases complete. 1265 tests pass, lint clean. No P0/P1 bugs.

## Key Design Decisions (do not revisit without cause)

- **Server is referee authority.** The LLM narrates; the server decides legality, randomization, visibility, and state commits.
- **Two-tier LLM routing.** Fast local model handles cheap/structured tasks. Gemma 4 26B A4B handles narration, NPC dialogue, and arbitration proposals.
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
│   ├── fast/                # Fast local model (qwen2.5:1.5b) adapter
│   ├── main/                # Main model (Gemma 4 26B A4B) adapter
│   └── contracts/           # Prompt contracts and context assembly
├── scenarios/               # Scenario YAML files, loader, validator
│   └── starters/            # 4 starter scenarios (goblin_caves, haunted_manor, forest_ambush, merchant_quarter)
├── webapp/                  # Mini App frontend (HTML/JS/CSS)
├── docs/                    # Design docs, plan, release readiness
│   ├── release_readiness.md # Open bugs and release criteria
│   └── feature_freeze.md   # Feature freeze notice
└── tests/                   # 1265 tests (unit + integration)
```

## Known Defects / Open Issues

See `docs/release_readiness.md` for the full bug table and release criteria.

- BUG-001 (P2): Gemma inference adapter disabled; all narration uses deterministic fallback. Deferred (requires live model).
- BUG-002 (P3): Narration fallback text is functional but repetitive across turns. Open.
- BUG-003 (P3): No persistent storage; all state is in-memory (by design for playtest). Deferred.

## Phase Completion Log

See `docs/phase_status.md` for the authoritative phase log.

## Environment Quick Reference

- Python version: see `docs/repo_conventions.md`
- Secrets: see `docs/repo_conventions.md`
- Run tests: `pytest`
- Lint: `ruff check . && ruff format --check .`
- Never push without explicit per-message authorization
