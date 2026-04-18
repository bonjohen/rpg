# Repository Conventions

Covers branch policy, commit protocol, environment setup, secrets, logging, debugging, repo layout, prompt contracts, and scenario content location.

---

## Branch Policy

- **`main`** is the only long-lived branch.
- All work is done on `main` unless a specific parallel workstream requires a feature branch (rare).
- Feature branches (if ever created) are named `feature/<short-slug>`.
- No push to any remote without explicit per-message authorization from the user.
- Commits stay local until explicitly requested.

---

## Commit Protocol

- **One commit per completed phase.** Never commit partial phases.
- Commit only when: all phase tasks are `[#]`, tests pass (`pytest`), lint is clean (`ruff check .` and `ruff format --check .`).
- Commit message format: `Phase N: <title>` (e.g., `Phase 0: Repository Foundation and Startup Context`).
- Never `git push` without explicit per-message user authorization. Do not chain `&& git push` onto commit commands.
- Do not amend published commits. If a phase commit needs fixing, add a follow-up commit.

---

## Repo Layout

```
C:\Projects\rpg\
├── STARTUP.md               # Session-restore context (update each phase)
├── CLAUDE.md                # Claude Code project instructions
├── docs/
│   ├── plan.md              # Active phased release tracker (source of truth for work queue)
│   ├── phase_status.md      # Phase completion log
│   ├── architecture.md      # System architecture
│   ├── model_routing.md     # LLM routing rules
│   ├── repo_conventions.md  # This file
│   ├── testing.md           # Test strategy
│   ├── design.md            # Original design document
│   └── pdr.md               # Product design requirements
├── server/                  # Game server (Python)
│   ├── domain/              # Domain model: entities, state machines, enums
│   ├── engine/              # Turn engine, timer, rules resolution
│   ├── storage/             # ORM models, migrations, repositories
│   ├── scopes/              # Scope enforcement layer
│   ├── router/              # LLM routing logic
│   └── api/                 # Internal API (for bot gateway)
├── bot/                     # Telegram bot gateway
│   ├── handlers/            # Incoming message and callback handlers
│   ├── outbound/            # Outbound message sending (public + DM)
│   └── commands/            # /start, /join, /help, /status, etc.
├── models/                  # Inference adapters
│   ├── fast/                # Fast local model adapter
│   └── gemma/               # Gemma 4 26B A4B adapter
├── scenarios/               # Scenario content files (YAML/JSON)
│   └── starter/             # First playable scenario
├── prompts/                 # Prompt contract templates
│   ├── fast/                # Fast-tier prompt contracts
│   └── gemma/               # Gemma-tier prompt contracts
└── tests/
    ├── unit/                # Unit tests
    ├── integration/         # Persistence and integration tests
    ├── fixtures/            # Entity builders, Telegram payloads, LLM outputs, scenarios
    └── scenarios/           # Scenario-level game behavior tests
```

Directories are created as they are needed in each phase. Do not create empty directories in advance.

---

## Where Prompt Contracts Live

All prompt templates live in `prompts/`. Each template is a text file with clear variable placeholders (e.g., `{scene_description}`, `{player_actions}`).

- `prompts/fast/` — fast-model prompt contracts (intent classification, extraction, scope suggestion, etc.)
- `prompts/gemma/` — Gemma 4 26B A4B prompt contracts (narration, NPC dialogue, ruling proposals, combat summaries)

Prompt contracts are versioned alongside the code. A change to a prompt contract is a code change and requires a test update if it affects any regression fixture.

---

## Where Scenario Content Lives

All scenario files live in `scenarios/`. Format is YAML (preferred) or JSON.

- `scenarios/starter/` — the first playable scenario (developed in Phase 13)
- `scenarios/<name>/` — additional scenarios added in Phase 19+

Each scenario directory contains:
- `scenario.yaml` — top-level scenario metadata
- `scenes/` — individual scene definitions (room descriptions, exits, items, hidden content)
- `npcs/` — NPC definitions (hard state + durable mind initial values)
- `monsters/` — monster group templates
- `puzzles/` — puzzle definitions
- `quests/` — quest definitions

Scenarios must pass `python -m server.tools.validate_scenario <path>` before use (validation tool added in Phase 13).

---

## Environment Setup

**Python version:** 3.12+

**Virtual environment:** Use `python -m venv .venv` at repo root. Activate with `.venv/Scripts/activate` (Windows) or `.venv/bin/activate` (Linux/Mac).

**Install dependencies:**
```
pip install -r requirements.txt
```

`requirements.txt` is maintained at repo root. Add dependencies there; do not install ad-hoc.

**Test:**
```
pytest
```

**Lint:**
```
ruff check .
ruff format --check .
```

---

## Secrets and Environment Variables

Secrets are never committed to the repo.

| Variable | Purpose | Where to set |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | `.env` file (local only) |
| `GEMMA_BASE_URL` | Gemma 4 26B A4B inference endpoint | `.env` file |
| `FAST_MODEL_BASE_URL` | Fast local model inference endpoint | `.env` file |
| `DATABASE_URL` | Persistence connection string | `.env` file |

`.env` is in `.gitignore`. Use `python-dotenv` (or equivalent) to load it. Never hard-code tokens or URLs in source files.

For tests, use environment variables or test-specific config overrides. Never use production secrets in tests.

---

## Logging Conventions

- Use Python's standard `logging` module with structured output.
- Log at `INFO` level for normal game events (turn open, action submitted, turn committed).
- Log at `DEBUG` level for internal state transitions and model call details.
- Log at `WARNING` for recoverable anomalies (model fallback triggered, late submission rejected).
- Log at `ERROR` for failures that affect players (delivery failure, turn stuck).
- Every log record for a turn event must include: `campaign_id`, `turn_window_id`, `scene_id` (where applicable).
- Every LLM call must include: `trace_id`, `tier`, `task_type`, `latency_ms`, `success`.
- Do not log raw player message content at INFO or higher in production (privacy). Debug-level only, and only when debug logging is explicitly enabled.

---

## Debug Conventions

- `DEBUG=1` environment variable enables verbose logging.
- Admin diagnostics endpoint (Phase 15) can inspect stuck turns and failed deliveries.
- Append-only turn log is the primary replay and audit source. Use it before adding extra logging.
- For model debugging, regression fixtures in `tests/fixtures/llm/` capture representative inputs and expected outputs.

---

## No-Push Behavior

- `git push` requires explicit per-message authorization in the current user message.
- Never chain `&& git push` onto commit commands.
- Previous authorization does not carry forward across messages or sessions.
- The push guard hook at `~/.claude/hooks/pre-bash-git-push-guard.py` enforces this mechanically.
