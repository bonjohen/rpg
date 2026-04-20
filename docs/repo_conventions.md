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
│   ├── architecture.md      # System architecture
│   ├── model_routing.md     # LLM routing rules
│   ├── repo_conventions.md  # This file
│   ├── testing.md           # Test strategy
│   ├── bugs.md              # Bug tracker
│   ├── release_readiness.md # Release criteria and open bug counts
│   ├── feature_freeze.md    # Feature freeze notice
│   ├── design.md            # Original design document
│   ├── database_design.md   # Database integration design
│   ├── miniapp_architecture.md # Mini App architecture
│   └── code_review.md       # Code review instructions
├── server/                  # Game server (Python)
│   ├── domain/              # Entities, enums, helpers (pure dataclasses)
│   ├── engine/              # Turn engine (lifecycle, validation, commit)
│   ├── scope/               # Scope enforcement, side channels, leakage guard
│   ├── timer/               # Countdown timer, early-close, pause/resume
│   ├── exploration/         # Movement, actions, triggers, clues, objects, memory
│   ├── npc/                 # Trust engine, tells, social resolution
│   ├── combat/              # Conditions, actions, monsters, morale, summaries
│   ├── scene/               # Scene membership, multi-scene, split-party
│   ├── orchestrator/        # GameOrchestrator (top-level game loop)
│   ├── api/                 # FastAPI REST API for Mini App
│   ├── reliability/         # Retry, idempotency, model recovery, turn recovery
│   ├── observability/       # Structured logging, metrics, diagnostics
│   └── storage/             # ORM models, repositories, database setup
├── bot/                     # Telegram bot gateway (flat module: commands.py, handlers.py, outbound.py, etc.)
├── models/                  # Inference adapters
│   ├── fast/                # Fast local model adapter (qwen2.5:1.5b via Ollama)
│   ├── main/                # Main model adapter (GPT-5.4 mini via OpenAI API)
│   ├── gemma/               # Main model adapter (Gemma 4 26B A4B, OpenAI-compatible)
│   ├── contracts/           # Prompt contracts, context assembly, output repair
│   └── protocol.py          # MainAdapter protocol (shared interface)
├── scenarios/               # Scenario schema, loader, validator, patterns
│   └── starters/            # 4 starter scenarios (YAML)
├── webapp/                  # Mini App frontend (HTML/JS/CSS)
└── tests/                   # 1479 tests (unit + integration)
    ├── unit/
    ├── integration/
    └── fixtures/            # Entity builders, Telegram payloads, scenario fixtures
```

---

## Where Prompt Contracts Live

Prompt contracts live in `models/contracts/`. Each contract is a Python dataclass in `main_contracts.py` with an output schema, system/user prompt templates, and a fallback output. Context assembly (`context_assembly.py`) builds scoped prompts from game state. Output repair (`output_repair.py`) fixes minor schema errors in model output.

Prompt contracts are versioned alongside the code. A change to a prompt contract is a code change and requires a test update if it affects any regression fixture.

---

## Where Scenario Content Lives

All scenario files live in `scenarios/starters/` as single YAML files. Each file defines the full scenario: metadata, scenes, NPCs, monsters, items, puzzles, quests, and triggers in one document.

Four starter scenarios ship with the repo:
- `goblin_caves.yaml` — mixed exploration/combat
- `haunted_manor.yaml` — puzzle/investigation
- `forest_ambush.yaml` — combat/tactical
- `merchant_quarter.yaml` — social/investigation

Scenarios are validated by the `ScenarioLoader` and `ScenarioValidator` at load time. Use the loader to test:

```python
from scenarios.loader import ScenarioLoader
result = ScenarioLoader().load_from_yaml("scenarios/starters/goblin_caves.yaml")
```

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
| `BOT_TOKEN` | Telegram Bot API token | `.env` file (local only) |
| `GROUP_CHAT_ID` | Telegram supergroup chat ID | `.env` file |
| `FAST_MODEL_BASE_URL` | Fast local model inference endpoint (Ollama) | `.env` file |
| `OPENAI_API_KEY` | OpenAI API key (if using GPT-5.4 mini) | `.env` file |
| `GEMMA_BASE_URL` | Gemma inference endpoint (if using local Gemma) | `.env` file |
| `GEMMA_API_KEY` | API key for Gemma endpoint (if required) | `.env` file |
| `DATABASE_URL` | Persistence connection string (default: sqlite:///rpg.db) | `.env` file |

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
