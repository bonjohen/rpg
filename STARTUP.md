# STARTUP.md — Session Restore Context

Read this at the start of every session before touching any code.

## Project Summary

AI-refereed multiplayer text RPG delivered via Telegram. The game server owns state, timing, visibility, and turn commitment. The AI (fast local model + Gemma 4 26B A4B) acts as referee voice, narrator, and NPC presenter. Players interact via a Telegram supergroup (public party chat) and private DMs (hidden info, rules questions).

## Active Plan

`docs/plan.md` — work one phase at a time, one task at a time.

Current phase: **Phase 3 — Telegram Bot Integration Skeleton** (not started). Phase 2 completed 2026-04-18 10:54 PM.

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
├── server/                  # Game server (Python, added in Phase 1+)
├── bot/                     # Telegram bot gateway (added in Phase 3+)
├── models/                  # Inference adapters (added in Phase 6+)
├── scenarios/               # Scenario content files (added in Phase 13+)
└── prompts/                 # Prompt contracts (added in Phase 14+)
```

## Known Defects / Open Issues

None yet. (Update this section as issues are found during phase work.)

## Phase Completion Log

See `docs/phase_status.md` for the authoritative phase log.

## Environment Quick Reference

- Python version: see `docs/repo_conventions.md`
- Secrets: see `docs/repo_conventions.md`
- Run tests: `pytest`
- Lint: `ruff check . && ruff format --check .`
- Never push without explicit per-message authorization
