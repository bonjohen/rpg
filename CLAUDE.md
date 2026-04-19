# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI-refereed multiplayer text RPG delivered via Telegram, with a fast local model (qwen2.5:1.5b via Ollama) and a main model tier (GPT-5.4 mini via OpenAI API). Work is tracked phase-by-phase in `docs/plan.md`.

## Development Workflow

Active plan: `docs/plan.md`. Work one phase at a time, one task at a time.

Each phase begins with **Phase Startup** (sync repo, read `STARTUP.md`, review prior phase notes) and ends with **Phase End** (run all tests, update `docs/phase_status.md` and `STARTUP.md`, commit locally without pushing).

Task status progression:
- `[ ]` → `[X]` (started) → `[#]` (completed)
- `[ ]` → `[!]` (blocked) → `[X]` → `[#]`

Fill in Started and Completed PST datetimes as you go. Never push; commits stay local until explicitly requested.

## Key Reference Docs (created in Phase 0)

| File | Purpose |
|---|---|
| `STARTUP.md` | Authoritative session-restore context |
| `docs/architecture.md` | System architecture |
| `docs/phase_status.md` | Phase completion log |
| `docs/model_routing.md` | Fast vs. main model routing rules |
| `docs/repo_conventions.md` | Branch, commit, env, and logging conventions |
| `docs/testing.md` | Test strategy and how to run tests |
