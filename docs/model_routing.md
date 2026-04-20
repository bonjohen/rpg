# Model Routing Rules

## Principle

Split LLM calls into two tiers. Default to the fast tier. Escalate to the main tier only when quality or complexity justifies it.

All authoritative turn resolution stays server-side regardless of which tier is called.

---

## Fast Local Model Tier

**Purpose:** Low-latency, high-volume, structured tasks.

**When to route here:**

| Task | Notes |
|---|---|
| Intent classification | "is this an action, a question, a chat?" |
| Command normalization | Clean raw player text into a structured command |
| Action packet field extraction | Pull action_type, target, item_ids, etc. from free text |
| Scope suggestion | Public vs. private-referee vs. side-channel |
| Recent-turn context summarization | Compact last N public messages into a turn summary |
| Short clarification question generation | "Did you mean X or Y?" |
| Format repair and schema validation | Fix minor JSON/schema errors in main model output |
| Lightweight moderation | Flag out-of-game content |

**When NOT to route here:**

- Official scene narration after turn resolution
- NPC dialogue that will be seen publicly
- Structured ruling proposals for ambiguous actions
- Any task where narrative quality meaningfully affects player experience

**Latency target:** < 500 ms per call.

**Failure handling:** If the fast model returns garbage or times out, the server handles the task deterministically (default action, generic response). Do not block a turn.

---

## Main Game Model Tier

**Purpose:** High-quality narrative and social tasks.

**Supported backends (choose one at startup):**

| Backend | Adapter | Config | Notes |
|---|---|---|---|
| GPT-5.4 mini (OpenAI API) | `OpenAIMainAdapter` | `OPENAI_API_KEY` | Cloud; lowest latency |
| Gemma 4 26B A4B (local) | `GemmaMainAdapter` | `GEMMA_BASE_URL`, optional `GEMMA_API_KEY` | Any OpenAI-compatible endpoint (vLLM, llama.cpp, Ollama /v1) |

Both adapters implement `MainAdapter` protocol (`models/protocol.py`). Pass either to `GameOrchestrator(main_adapter=...)`.

**When to route here:**

| Task | Notes |
|---|---|
| Task | Notes |
|---|---|
| Scene narration (official, post-resolution) | The authoritative public result after a turn commits |
| NPC dialogue | Any NPC line that players will see publicly |
| Combat summary prose | The readable battle narrative for the party |
| Structured ruling proposals | Ambiguous player actions; returns JSON proposal for server validation |
| Unusual player action interpretation | When structured code cannot classify the action |
| Social arbitration | Multi-player social disputes with NPC or other players |
| Puzzle response flavor | Narration of puzzle interaction outcomes |

**When NOT to route here:**

- Cheap, repeated, structured extraction tasks (use fast tier)
- Format repair of its own output (use fast tier for that)
- Anything that should be deterministic (use server logic)

**API:** OpenAI Chat Completions (`/v1/chat/completions`). Both adapters use this protocol.

**Latency target:** < 5 s for OpenAI; < 10 s for Gemma on local hardware. Combat and exploration narration can tolerate slightly longer.

**Failure handling:**
1. Validate output against expected schema.
2. If schema invalid: send to fast tier for repair (one retry).
3. If repair fails or model times out: server falls back to a minimal deterministic narration. Turn is NOT blocked.
4. Log all failures with turn_window_id and trace ID for debugging.

---

## Routing Decision Logic

```
Incoming task
│
├─ Is this a cheap, structured, or classification task?
│   YES → Fast tier
│
├─ Does quality of narration/dialogue matter to players?
│   YES → Main tier
│
├─ Is this a ruling proposal for an ambiguous action?
│   YES → Main tier
│
└─ Default → Fast tier
```

Routing is performed by the server's LLM router component. The router is deterministic code, not itself an LLM call.

---

## Prompt Size Limits (Preliminary)

| Tier | Target prompt size | Hard limit |
|---|---|---|
| Fast | < 2K tokens | 4K tokens |
| Main | < 16K tokens | 32K tokens |

Truncation policy: prefer dropping oldest public chat history before dropping scene state or player facts.

---

## Scoped Knowledge Packets

The LLM must only receive the facts it is allowed to know for a given call. The server assembles a scoped knowledge packet before each inference call:

- **Public narration call:** Public scene state, all public facts, committed action summaries. No referee-only facts.
- **NPC dialogue call:** NPC hard state + durable mind for that NPC, NPC's known facts, scene context. No other NPC private facts.
- **Ruling proposal call:** The specific action, relevant rules, player character state, scene context. Minimal private facts relevant to the ruling only.

Never pass raw unfiltered chat history to any LLM call where secrecy matters.

---

## Instrumentation Requirements

Every model call must log:

- `trace_id` (tied to the TurnWindow or request context)
- `tier` (fast / main)
- `task_type`
- `prompt_token_count`
- `output_token_count`
- `latency_ms`
- `success` (bool)
- `failure_reason` (if applicable)
- `fallback_triggered` (bool)
