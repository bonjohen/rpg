# Architecture: AI-Refereed Multiplayer Text Game on Telegram

## Core Principle

**The AI is the referee voice. The server is the referee authority.**

The server owns: state storage, timer control, action validation, rules resolution, randomization, scope enforcement, the append-only turn log, and replay/audit. The LLM owns: narration prose, NPC dialogue, combat summary flavor, and structured ruling proposals. The LLM never directly mutates canonical state.

---

## System Layers

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Platform                      │
│  Supergroup (public party chat + topics)                 │
│  Private DMs (one per player)                            │
│  Inline keyboards (Ready, Pass, Ask Ref, Submit, Revise) │
│  Mini App (sheet, inventory, map, inbox, action builder)  │
└────────────────────────┬────────────────────────────────┘
                         │ Bot API (HTTP)
┌────────────────────────▼────────────────────────────────┐
│                   Telegram Bot Gateway                   │
│  Handles incoming messages, callbacks, commands          │
│  Maps Telegram user IDs → Player records                 │
│  Maps Telegram chat IDs → Campaign records               │
│  Routes to game server over internal API                 │
│  Commands: /start /join /help /status /newgame /nextturn │
│            /forceresolve /diagnostics /scene /who        │
└────────────────────────┬────────────────────────────────┘
                         │ Internal API
┌────────────────────────▼────────────────────────────────┐
│                   Game Orchestrator                       │
│  server/orchestrator/game_loop.py                        │
│  Wires: bot → turn engine → scope → timer → models      │
│  load_scenario, add_player, open_turn, submit_action     │
│  resolve_turn, handle_player_message, run_timer_tick     │
│  In-memory state for playtest (production DB post-Ph.20) │
├──────────────────────────────────────────────────────────┤
│                     Game Server                          │
│  Turn engine (open → lock → resolve → commit)            │
│  Scope enforcement (public / private-ref / side-ch / ref)│
│  Rules resolution (deterministic + dice)                 │
│  Timer control (countdown, early-close, timeout)         │
│  Append-only turn log                                    │
│  Exploration, NPC Social, Combat loops                   │
│  Split-party multi-scene handling                        │
│  Reliability (retry, idempotency, recovery)              │
│  Observability (structured logs, metrics, diagnostics)   │
│  State storage (Campaign, Player, Character, Scene, …)   │
│  LLM router (decides fast tier vs. main tier)            │
└────────┬───────────────────────────┬────────────────────┘
         │ Fast tier                 │ Main tier
┌────────▼──────────┐   ┌───────────▼────────────────────┐
│  Fast Local Model │   │  GPT-5.4 mini (OpenAI API)     │
│  (small, low-lat) │   │  (cloud, Chat Completions)      │
│  intent classify  │   │  scene narration                │
│  cmd normalize    │   │  NPC dialogue                   │
│  action extract   │   │  combat summary prose           │
│  scope suggest    │   │  arbitration proposals          │
│  context summarize│   │  unusual player intent          │
│  format repair    │   │  structured ruling proposals    │
└───────────────────┘   └─────────────────────────────────┘
```

---

## Conversation Scopes

| Scope | Visible To | Used For |
|---|---|---|
| Public | Entire party | Scene narration, NPC dialogue, timer, combat summary, player discussion |
| Private-referee | One player + bot | Awareness results, hidden clues, rules questions, stealth outcomes, personal objectives |
| Side-channel | Subset of players + bot | Private player-to-player coordination |
| Referee-only | Server only | Trap triggers, hidden map links, NPC intent, monster awareness, unrevealed facts |

Scope is a first-class data field. It is never inferred from chat structure.

---

## Turn Lifecycle

```
1. Server posts current situation (public)
2. Server delivers newly relevant private facts (private-referee)
3. Countdown timer opens (server-owned, public message)
4. Players discuss publicly or privately
5. Each player submits one CommittedAction packet
6. Timer expires OR all players mark ready
7. Server locks input (TurnWindow → locked)
8. Server resolves the turn (rules, randomization, state changes)
9. Main game model narrates the result
10. Committed result is appended to the turn log
```

Applies identically to exploration, social, and combat scenes. Only resolution rules differ.

---

## LLM Routing

| Task | Tier |
|---|---|
| Intent classification | Fast |
| Command normalization | Fast |
| Action packet extraction | Fast |
| Scope suggestion | Fast |
| Recent-turn context summarization | Fast |
| Short clarification question generation | Fast |
| Format repair / schema validation | Fast |
| Scene narration (official) | GPT-5.4 mini |
| NPC dialogue | GPT-5.4 mini |
| Combat summary prose | GPT-5.4 mini |
| Structured ruling proposals | GPT-5.4 mini |
| Unusual player action interpretation | GPT-5.4 mini |

All authoritative resolution remains server-side. If Gemma fails schema validation or exceeds latency, the server falls back to a deterministic response rather than blocking the turn.

---

## Data Model (Core Entities)

| Entity | Purpose |
|---|---|
| Campaign | Top-level container; owns one group chat, multiple scenes |
| Player | Telegram user → player mapping |
| Character | Player's in-game character (stats, inventory refs) |
| Scene | Active location; owns NPCs, monsters, items, active TurnWindow |
| TurnWindow | One turn cycle; owns CommittedActions; tracks timer and state |
| CommittedAction | One player's authoritative action packet for a turn |
| TurnLogEntry | Append-only resolved turn record |
| ConversationScope | Scope tag: public / private-referee / side-channel / referee-only |
| SideChannel | Subset-of-players channel; owned by Campaign |
| NPC | Hard state + durable mind structured record |
| MonsterGroup | Grouped tactical actor record |
| InventoryItem | Item instance linked to character or scene |
| QuestState | Quest progress per campaign |
| PuzzleState | Puzzle state per scene |
| KnowledgeFact | Scoped fact (who knows what) |
| VisibilityGrant | Explicit grant of a KnowledgeFact to a scope |

---

## State Machines

**Scene states:** `idle → prompting → awaiting_actions → resolving → narrated → paused`

**TurnWindow states:** `open → all_ready → locked → resolving → committed → aborted`

**CommittedAction states:** `draft → submitted → validated → rejected → resolved`

States are stored explicitly. They are never inferred from message order.

---

## NPC Architecture

- **Hard state** (code-owned): location, health, inventory, faction, status effects, scene membership, visibility
- **Durable mind** (server-stored structured data): goals, loyalties, fears, personality tags, trust-by-player, party stance, memory tags
- **Presentation** (LLM-owned): dialogue, emotional tone, rhetorical style

The LLM may propose durable mind changes; the server commits or rejects them.

---

## Monster Architecture

Monsters are tactical actors, not conversational agents. A MonsterGroup tracks: behavior mode, awareness state, morale, threat priorities, formation state, special rules, territory/pursuit constraints. Small enemies are grouped to keep combat readable.

---

## Telegram Control Surface

**Bot commands:** `/start`, `/join`, `/help`, `/status`, `/ready`, `/pass`, `/sheet`, `/inventory`, `/log`, `/recap`

**Inline keyboard controls** (turn-control message): Ready, Pass, Ask Ref, Revise, Submit

**Group structure:** One supergroup, forum topics enabled, one main play topic. Bot must be group admin to reliably observe all messages.

---

## Mini App

Character sheet, inventory, map, quest log, private inbox, side-channel management, draft action builder, turn recap. Launched from bot menu or inline buttons. Implemented in Phase 17-18 with FastAPI backend (`server/api/`) and HTML/JS/CSS frontend (`webapp/`). Auth via Telegram WebApp HMAC-SHA256 validation.

---

## MVP Scope

Included: one supergroup, one play topic, one DM per player, timer-driven turn loop, one committed action per player per turn, exploration loop, social loop, combat loop, basic NPC memory tags, grouped monster encounters, player-private clue delivery, append-only turn logging, split LLM routing (fast local + GPT-5.4 mini via OpenAI).

Excluded from MVP: live maps, scenario authoring suite, real-time combat, persistent storage (in-memory only for playtest).
