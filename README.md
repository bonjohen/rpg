# AI-Refereed Multiplayer Text RPG on Telegram

A multiplayer text-based adventure game delivered through Telegram, where an AI serves as the referee voice and narrator while the server maintains authoritative control over game state, rules, timing, and visibility.

Players interact via a Telegram supergroup (public party chat) and private DMs (hidden information, rules questions). A Telegram Mini App provides read-only views (character sheet, inventory, map) and interactive features (action builder, inbox, side-channel management).

## Core Design

**The AI is the referee voice. The server is the referee authority.**

The server owns state, timer control, action validation, rules resolution, scope enforcement, and the append-only turn log. The LLM owns narration prose, NPC dialogue, combat summaries, and ruling proposals. The LLM never directly mutates canonical state.

### Two-Tier LLM Routing

| Tier | Model | Latency Target | Tasks |
|---|---|---|---|
| Fast | qwen2.5:1.5b via Ollama | < 500 ms | Intent classification, command normalization, action extraction, scope suggestion, format repair |
| Main | Gemma 4 26B A4B (local) or GPT-5.4 mini (OpenAI API) | < 5–10 s | Scene narration, NPC dialogue, combat summaries, ruling proposals, unusual action interpretation |

The fast model runs locally via [Ollama](https://ollama.com). The main model supports two backends: a local Gemma adapter (any OpenAI-compatible endpoint) or the OpenAI API. Both implement the `MainAdapter` protocol. If either model is unavailable, the server falls back to deterministic responses — the game never blocks on a model failure.

### Conversation Scopes

All scope is explicit in data, not inferred from chat structure:

| Scope | Visible To | Used For |
|---|---|---|
| Public | Entire party | Scene narration, NPC dialogue, combat summaries |
| Private-referee | One player + bot | Hidden clues, awareness results, rules questions |
| Side-channel | Subset of players + bot | Private player-to-player coordination |
| Referee-only | Server only | Trap triggers, NPC intent, unrevealed facts |

### Turn Lifecycle

```
open --> all_ready --> locked --> resolving --> committed
                                     |
                                     +--> aborted
```

Each player submits one committed action packet per turn. A countdown timer enforces deadlines; players who don't submit get a deterministic fallback (hold position).

## Architecture

```
+---------------------------------------------------------+
|                   Telegram Platform                      |
|  Supergroup + Private DMs + Inline Keyboards + Mini App  |
+------------------------+--------------------------------+
                         | Bot API
+------------------------v--------------------------------+
|                   Telegram Bot Gateway                   |
|  bot/ -- messages, callbacks, commands                   |
+------------------------+--------------------------------+
                         |
+------------------------v--------------------------------+
|                   Game Orchestrator                       |
|  server/orchestrator/ -- wires all subsystems            |
|  Database-backed persistence (SQLite/PostgreSQL)         |
+------------------------+--------------------------------+
|                     Game Server                          |
|  Turn engine, scope enforcement, timer, combat,          |
|  exploration, NPC social, split-party, reliability       |
+--------+---------------------------+--------------------+
         | Fast tier                 | Main tier
+--------v----------+   +-----------v--------------------+
|  qwen2.5:1.5b     |   |  Gemma 4 26B A4B (local)      |
|  via Ollama        |   |  or GPT-5.4 mini (OpenAI API) |
+-------------------+   +--------------------------------+
```

## Getting Started

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) (for local model inference)
- A Telegram Bot token (from [@BotFather](https://t.me/BotFather))
- A Telegram supergroup with forum topics enabled

### Installation

```bash
git clone <repo-url> && cd rpg
python -m venv .venv

# Activate virtual environment
.venv/Scripts/activate          # Windows
source .venv/bin/activate       # Linux/Mac

pip install -r requirements.txt
```

### Pull the Fast Model

```bash
ollama pull qwen2.5:1.5b
```

If using Gemma locally as the main model:

```bash
ollama pull gemma3:27b       # or your preferred Gemma variant
```

The Ollama `OLLAMA_MODELS` environment variable controls where model weights are stored. Set it if you want models on a specific drive. If using GPT-5.4 mini instead, set `OPENAI_API_KEY` (no Ollama pull needed for the main model).

### Environment Variables

Create a `.env` file or set these in your shell:

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram Bot API token |
| `GROUP_CHAT_ID` | Yes | Telegram supergroup chat ID |
| `PLAY_TOPIC_ID` | No | Forum topic ID for the main play thread |
| `WEBHOOK_URL` | No | Webhook URL (if empty, uses polling mode) |
| `WEBHOOK_PORT` | No | Webhook port (default: 8443) |
| `FAST_MODEL_BASE_URL` | No | Ollama URL for fast model (default: http://localhost:11434) |
| `OPENAI_API_KEY` | No | OpenAI API key (if using GPT-5.4 mini as main model) |
| `GEMMA_BASE_URL` | No | Ollama/vLLM URL for Gemma main model (default: http://localhost:11434) |
| `GEMMA_API_KEY` | No | API key for Gemma endpoint (if required by your setup) |
| `DATABASE_URL` | No | Database connection string (default: `sqlite:///rpg.db`) |

### Start the Bot

```bash
# Polling mode (development)
python -m bot

# The bot reads BOT_TOKEN from the environment.
# If WEBHOOK_URL is set, it runs in webhook mode; otherwise polling.
```

### Start the Mini App API Server

```bash
uvicorn server.api.app:api_app --host 0.0.0.0 --port 8000
```

The API serves both the REST endpoints (`/api/...`) and the Mini App frontend (`/app/...`).

## Gameplay

### Bot Commands

| Command | Where | Description |
|---|---|---|
| `/start` | DM | Start a conversation with the bot |
| `/join` | Group | Register as a player in the campaign |
| `/help` | Anywhere | Show available commands |
| `/status` | Anywhere | Show your current game status |
| `/newgame <path>` | Group | Load a scenario (admin) |
| `/nextturn` | Group | Open the next turn (admin/debug) |
| `/forceresolve` | Group | Force-resolve the current turn (admin/debug) |
| `/diagnostics` | Anywhere | Show system diagnostics (admin) |
| `/scene` | Anywhere | Show your current scene and exits |
| `/who` | Anywhere | Show which players are in which scenes |

### Starting a Game

1. Create a Telegram supergroup with forum topics enabled
2. Add the bot as an admin
3. Each player DMs the bot with `/start`
4. Players send `/join` in the group
5. Admin sends `/newgame scenarios/starters/goblin_caves.yaml`
6. Admin sends `/nextturn` to open the first turn
7. Players submit actions via chat or the Mini App action builder

### Mini App Views

| View | Description |
|---|---|
| Character Sheet | Stats, status effects, health |
| Inventory | Items with properties and quantities |
| Turn Recap | Chronological narration history |
| Action Builder | Compose and submit actions with type selectors |
| Private Inbox | Private referee messages and clues |
| Side Channels | Private player-to-player coordination |
| Quest Log | Active, completed, and failed quests |
| Clue Journal | Discovered clues grouped by scene |
| Map | Scene graph showing discovered locations |

## Starter Scenarios

Four scenarios are included in `scenarios/starters/`:

| Scenario | Focus | Scenes | Description |
|---|---|---|---|
| `goblin_caves.yaml` | Mixed | 4 | Investigate goblin raids, rescue a merchant, find hidden treasure |
| `haunted_manor.yaml` | Puzzle/Investigation | 5 | Solve mysteries in a haunted estate, discover the truth about Lady Ashworth |
| `forest_ambush.yaml` | Combat/Tactical | 3 | Survive a bandit ambush, rescue a captive, retrieve stolen cargo |
| `merchant_quarter.yaml` | Social/Investigation | 4 | Track down a stolen necklace through merchants, thieves, and the city watch |

### Writing Custom Scenarios

Scenarios are YAML files validated by the scenario loader. See `scenarios/starters/goblin_caves.yaml` for the full format. A scenario defines:

- Scenes with descriptions, exits (including hidden/locked), and tags
- NPCs with personality tags, goals, trust thresholds, and behavioral tells
- Monster groups with behavior modes, awareness states, and special rules
- Items with properties, key status, and exit-unlock references
- Puzzles with solution actions, hints, and max attempts
- Quests with objectives and completion conditions
- Triggers that fire on scene entry, search, interaction, or as traps

Validate a scenario before use:

```python
from scenarios.loader import ScenarioLoader
loader = ScenarioLoader()
result = loader.load_from_yaml("path/to/scenario.yaml")
if not result.success:
    print(result.errors)
```

## Development

### Running Tests

```bash
pytest                              # Run all 1479 tests
pytest tests/unit/                  # Unit tests only
pytest tests/integration/           # Integration tests only
pytest -k "test_combat"             # Run tests matching a pattern
```

### Linting

```bash
ruff check .                        # Lint check
ruff format --check .               # Format check
ruff check . --fix && ruff format . # Auto-fix
```

### Project Structure

```
rpg/
+-- server/
|   +-- domain/          # Entities and enums (pure dataclasses)
|   +-- engine/          # Turn engine (lifecycle, validation, commit)
|   +-- scope/           # Scope enforcement, side channels, leakage guard
|   +-- timer/           # Countdown timer, early-close, pause/resume
|   +-- exploration/     # Movement, actions, triggers, clues, objects, memory
|   +-- npc/             # Trust engine, tells, dialogue, social resolution
|   +-- combat/          # Conditions, actions, monsters, morale, visibility
|   +-- scene/           # Scene membership, multi-scene, split-party timing
|   +-- orchestrator/    # GameOrchestrator (top-level game loop)
|   +-- api/             # FastAPI REST API for Mini App
|   +-- reliability/     # Retry, idempotency, model recovery, turn recovery
|   +-- observability/   # Structured logging, metrics, diagnostics
|   +-- storage/         # ORM models, repositories, database setup
+-- bot/                 # Telegram bot gateway
+-- models/
|   +-- fast/            # Fast model adapter (qwen2.5:1.5b via Ollama)
|   +-- main/            # Main model adapter (OpenAI API / GPT-5.4 mini)
|   +-- gemma/           # Main model adapter (Gemma 4 26B A4B, OpenAI-compatible)
|   +-- contracts/       # Prompt contracts, context assembly, output repair
+-- scenarios/           # Scenario schema, loader, validator, patterns
|   +-- starters/        # 4 starter scenarios (YAML)
+-- webapp/              # Mini App frontend (HTML/JS/CSS)
+-- tests/               # 1479 tests (unit + integration)
+-- docs/                # Architecture, design, conventions, routing
```

## License

This project is not yet licensed for distribution.
