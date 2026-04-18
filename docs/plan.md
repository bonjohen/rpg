# AI-Refereed Multiplayer Text Game on Telegram: Phased Release Tracker

Use this file one phase at a time and one task at a time. When a task begins, change its status from [ ] to [X] and fill in Started (PST). When the task is finished, change its status from [X] to [#] and fill in Completed (PST). Keep status and datelines accurate at all times. Treat [!] as a disabled task that is not currently being worked.

Status legend: [ ] Unstarted, [X] Started, [#] Completed, [!] Disabled

Follow this progression pattern with the statuses of each task:
[ ]  ──>  [X] ──>  [#] 
        │
        └──> [!] ──>  [X] ──>  [#]
Update Started and Completed datetimes when starting or completing a task.

At the beginning of each phase perform the following:
Phase Startup
* Sync repo and review branch status
* Read STARTUP.md and restore working context
* Review previous phase notes, known defects, and current priorities

At the end of each phase perform the following:
Phase End
* Run all tests and repair failures
* Update phase_status.md, STARTUP.md, and record Phase completion
* Commit Phase work locally without pushing
* Clear the context and move to the next phase without delay.

## Phase 0: Repository Foundation and Startup Context

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Create or refine STARTUP.md as the authoritative startup file | Started (PST): | Completed (PST):
[ ] Create or refine docs/architecture.md | Started (PST): | Completed (PST):
[ ] Create or refine docs/testing.md | Started (PST): | Completed (PST):
[ ] Create or refine docs/phase_status.md | Started (PST): | Completed (PST):
[ ] Create or refine docs/model_routing.md | Started (PST): | Completed (PST):
[ ] Create or refine docs/repo_conventions.md | Started (PST): | Completed (PST):
[ ] Define local workflow rules for branch, commit, and no-push behavior | Started (PST): | Completed (PST):
[ ] Define environment, secrets, logging, and debug conventions | Started (PST): | Completed (PST):
[ ] Define the repo layout for server, bot, models, scenarios, and docs | Started (PST): | Completed (PST):
[ ] Define where prompt contracts and scenario notes will live | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 1: Core Domain Model and Persistence

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define Campaign entity and persistence fields | Started (PST): | Completed (PST):
[ ] Define Player entity and persistence fields | Started (PST): | Completed (PST):
[ ] Define Character entity and persistence fields | Started (PST): | Completed (PST):
[ ] Define Scene entity and persistence fields | Started (PST): | Completed (PST):
[ ] Define ConversationScope and SideChannel entities | Started (PST): | Completed (PST):
[ ] Define TurnWindow, CommittedAction, and TurnLogEntry entities | Started (PST): | Completed (PST):
[ ] Define NPC and MonsterGroup entities | Started (PST): | Completed (PST):
[ ] Define InventoryItem, QuestState, PuzzleState, and KnowledgeFact entities | Started (PST): | Completed (PST):
[ ] Define state-machine enums for scene, turn, and action lifecycles | Started (PST): | Completed (PST):
[ ] Implement schema or ORM models | Started (PST): | Completed (PST):
[ ] Implement migrations or schema creation flow | Started (PST): | Completed (PST):
[ ] Add fixture builders for core entities | Started (PST): | Completed (PST):
[ ] Add persistence tests for create, load, update, and replayability | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 2: Canonical Turn Engine

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement TurnWindow lifecycle states and transitions | Started (PST): | Completed (PST):
[ ] Implement one authoritative committed action per player per turn | Started (PST): | Completed (PST):
[ ] Implement action validation and rejection flow | Started (PST): | Completed (PST):
[ ] Implement late-submission rejection after turn lock | Started (PST): | Completed (PST):
[ ] Implement all-ready early-close behavior | Started (PST): | Completed (PST):
[ ] Implement timeout fallback behavior hooks | Started (PST): | Completed (PST):
[ ] Implement append-only turn log writing | Started (PST): | Completed (PST):
[ ] Implement deterministic turn commit ordering | Started (PST): | Completed (PST):
[ ] Implement turn replay support from committed records | Started (PST): | Completed (PST):
[ ] Add unit tests for open, lock, resolve, commit, abort, and replay | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 3: Telegram Bot Integration Skeleton

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement Telegram bot gateway entry point | Started (PST): | Completed (PST):
[ ] Implement webhook or polling handler | Started (PST): | Completed (PST):
[ ] Implement public group message parsing | Started (PST): | Completed (PST):
[ ] Implement private DM message parsing | Started (PST): | Completed (PST):
[ ] Implement user-to-player and chat-to-campaign mapping | Started (PST): | Completed (PST):
[ ] Implement player onboarding requirement for private DM initiation | Started (PST): | Completed (PST):
[ ] Implement topic-aware routing for the main play topic | Started (PST): | Completed (PST):
[ ] Implement minimal command handling for /start, /join, /help, /status | Started (PST): | Completed (PST):
[ ] Implement outbound public message sending | Started (PST): | Completed (PST):
[ ] Implement outbound private DM sending | Started (PST): | Completed (PST):
[ ] Add Telegram payload fixtures and integration tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 4: Scope and Visibility Enforcement

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement public scope delivery rules | Started (PST): | Completed (PST):
[ ] Implement private-referee scope delivery rules | Started (PST): | Completed (PST):
[ ] Implement side-channel scope model and permissions | Started (PST): | Completed (PST):
[ ] Implement referee-only storage rules | Started (PST): | Completed (PST):
[ ] Implement KnowledgeFact ownership by scope | Started (PST): | Completed (PST):
[ ] Implement scope-safe retrieval for prompts and message generation | Started (PST): | Completed (PST):
[ ] Implement guardrails against accidental public leakage | Started (PST): | Completed (PST):
[ ] Add tests for awareness checks, hidden clues, stealth, and secret objectives | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 5: Countdown Timer and Readiness Control

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement timer creation for each turn | Started (PST): | Completed (PST):
[ ] Implement timer expiration handling | Started (PST): | Completed (PST):
[ ] Implement all-ready early completion | Started (PST): | Completed (PST):
[ ] Implement timeout fallback action application | Started (PST): | Completed (PST):
[ ] Implement pause and admin-stop controls | Started (PST): | Completed (PST):
[ ] Implement a single public turn-control message | Started (PST): | Completed (PST):
[ ] Implement inline controls for Ready, Pass, Ask Ref, Revise, and Submit | Started (PST): | Completed (PST):
[ ] Implement timer message update logic | Started (PST): | Completed (PST):
[ ] Add tests for expiry, early close, pause, and late submission | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 6: Fast Local Model Routing Layer

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement fast-model inference adapter | Started (PST): | Completed (PST):
[ ] Define routing rules for simple and low-risk requests | Started (PST): | Completed (PST):
[ ] Implement intent classification | Started (PST): | Completed (PST):
[ ] Implement command normalization | Started (PST): | Completed (PST):
[ ] Implement action packet extraction from raw player text | Started (PST): | Completed (PST):
[ ] Implement likely-scope suggestion from message content | Started (PST): | Completed (PST):
[ ] Implement short clarification-question generation | Started (PST): | Completed (PST):
[ ] Implement recent-turn context summarization | Started (PST): | Completed (PST):
[ ] Implement structured output validation and repair | Started (PST): | Completed (PST):
[ ] Add latency, usage, and failure instrumentation | Started (PST): | Completed (PST):
[ ] Add tests for extraction, repair, and fallback behavior | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 7: Main Gameplay Model Integration

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement Gemma 4 26B A4B inference adapter | Started (PST): | Completed (PST):
[ ] Define prompt contract for narration | Started (PST): | Completed (PST):
[ ] Define prompt contract for NPC dialogue | Started (PST): | Completed (PST):
[ ] Define prompt contract for structured arbitration proposals | Started (PST): | Completed (PST):
[ ] Implement scoped context assembly from canonical state | Started (PST): | Completed (PST):
[ ] Implement schema validation and repair for model output | Started (PST): | Completed (PST):
[ ] Implement fallback behavior for model timeout or invalid output | Started (PST): | Completed (PST):
[ ] Add regression fixtures for representative game states | Started (PST): | Completed (PST):
[ ] Add tests for prompt assembly, schema validation, and fallback behavior | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 8: Exploration Loop

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement room and scene transition rules | Started (PST): | Completed (PST):
[ ] Implement move, inspect, search, and interact actions | Started (PST): | Completed (PST):
[ ] Implement environmental triggers and simple traps | Started (PST): | Completed (PST):
[ ] Implement hidden clue discovery and scoped delivery | Started (PST): | Completed (PST):
[ ] Implement object-state change handling | Started (PST): | Completed (PST):
[ ] Implement revisit memory and scene recall behavior | Started (PST): | Completed (PST):
[ ] Add a small connected-room scenario slice | Started (PST): | Completed (PST):
[ ] Add tests for movement, interaction, trigger resolution, and clue delivery | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 9: NPC Social Loop

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement NPC hard-state usage in scene resolution | Started (PST): | Completed (PST):
[ ] Implement trust-by-player and party-stance fields in logic | Started (PST): | Completed (PST):
[ ] Implement NPC memory-tag updates after interactions | Started (PST): | Completed (PST):
[ ] Implement social action types for question, persuade, threaten, lie, and bargain | Started (PST): | Completed (PST):
[ ] Implement secret NPC tells and private reactions | Started (PST): | Completed (PST):
[ ] Implement NPC dialogue generation tied to structured state | Started (PST): | Completed (PST):
[ ] Add at least two meaningful NPC interactions to starter content | Started (PST): | Completed (PST):
[ ] Add tests for trust change, stance change, and memory persistence | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 10: Combat Loop

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define combat entry and exit conditions | Started (PST): | Completed (PST):
[ ] Implement attack, move, defend, assist, use item, and ability actions | Started (PST): | Completed (PST):
[ ] Implement grouped monster encounter behavior | Started (PST): | Completed (PST):
[ ] Implement damage, armor, status effects, and defeat states | Started (PST): | Completed (PST):
[ ] Implement morale and flee behavior | Started (PST): | Completed (PST):
[ ] Implement combat visibility and awareness rules | Started (PST): | Completed (PST):
[ ] Implement battlefield summaries for public turn posts | Started (PST): | Completed (PST):
[ ] Add at least one combat encounter to starter content | Started (PST): | Completed (PST):
[ ] Add tests for hit resolution, morale, grouped enemies, and end conditions | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 11: Side-Channels and Private Coordination

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define side-channel lifecycle and membership rules | Started (PST): | Completed (PST):
[ ] Implement side-channel creation and closure | Started (PST): | Completed (PST):
[ ] Implement DM-relay delivery for side-channel messages | Started (PST): | Completed (PST):
[ ] Implement visibility isolation for side-channel content | Started (PST): | Completed (PST):
[ ] Implement audit entries for side-channel activity | Started (PST): | Completed (PST):
[ ] Add tests for side-channel secrecy and public prompt isolation | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 12: Split Party and Multi-Scene Handling

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement explicit scene membership for players and NPCs | Started (PST): | Completed (PST):
[ ] Implement multiple active scene contexts in a campaign | Started (PST): | Completed (PST):
[ ] Implement scoped prompts by subgroup | Started (PST): | Completed (PST):
[ ] Implement coordinated timing policy for split-party play | Started (PST): | Completed (PST):
[ ] Implement delayed information propagation between subgroups | Started (PST): | Completed (PST):
[ ] Add split-party scenario cases and tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 13: Scenario Authoring Format

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define scenario file structure and schema | Started (PST): | Completed (PST):
[ ] Define scene, exit, item, NPC, monster, puzzle, and trigger formats | Started (PST): | Completed (PST):
[ ] Define public versus hidden content authoring rules | Started (PST): | Completed (PST):
[ ] Implement scenario validation tools | Started (PST): | Completed (PST):
[ ] Implement scenario import and load flow | Started (PST): | Completed (PST):
[ ] Create starter scenario package in the new format | Started (PST): | Completed (PST):
[ ] Add validation tests and content fixtures | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 14: Prompt Contracts and Context Assembly

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define fast-model prompt contracts | Started (PST): | Completed (PST):
[ ] Define Gemma gameplay prompt contracts | Started (PST): | Completed (PST):
[ ] Define context assembly rules for narration, arbitration, dialogue, and summaries | Started (PST): | Completed (PST):
[ ] Define prompt size limits and truncation policies | Started (PST): | Completed (PST):
[ ] Define schema validation and output-repair rules | Started (PST): | Completed (PST):
[ ] Add prompt-assembly regression fixtures | Started (PST): | Completed (PST):
[ ] Add tests for scope-safe context assembly and leakage prevention | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 15: Reliability, Recovery, and Observability

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement structured logging and trace IDs | Started (PST): | Completed (PST):
[ ] Implement retry handling for Telegram delivery failures | Started (PST): | Completed (PST):
[ ] Implement duplicate-delivery and replay protection | Started (PST): | Completed (PST):
[ ] Implement model timeout and recovery behavior | Started (PST): | Completed (PST):
[ ] Implement crash-safe turn recovery | Started (PST): | Completed (PST):
[ ] Implement admin diagnostics for stuck turns and failed deliveries | Started (PST): | Completed (PST):
[ ] Implement metrics for latency, routing, and failures | Started (PST): | Completed (PST):
[ ] Add failure-path tests for retries, duplicates, and restart recovery | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 16: Internal Playtest Release

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Prepare internal playtest build locally | Started (PST): | Completed (PST):
[ ] Select and stage starter scenario for playtest | Started (PST): | Completed (PST):
[ ] Run structured multiplayer playtest session | Started (PST): | Completed (PST):
[ ] Capture logs, transcripts, and issues | Started (PST): | Completed (PST):
[ ] Categorize defects by timing, clarity, leakage, routing, and rules | Started (PST): | Completed (PST):
[ ] Patch highest-severity issues found in playtest | Started (PST): | Completed (PST):
[ ] Add regression tests for discovered failures | Started (PST): | Completed (PST):
[ ] Update architecture, prompts, and phase notes from findings | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 17: Mini App Foundation

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Define Mini App architecture and launch flow | Started (PST): | Completed (PST):
[ ] Implement Telegram-linked Mini App shell | Started (PST): | Completed (PST):
[ ] Implement read-only character sheet view | Started (PST): | Completed (PST):
[ ] Implement read-only inventory view | Started (PST): | Completed (PST):
[ ] Implement read-only turn recap view | Started (PST): | Completed (PST):
[ ] Add Mini App state-hydration tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 18: Mini App Gameplay Utilities

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Implement draft action builder | Started (PST): | Completed (PST):
[ ] Implement private inbox view | Started (PST): | Completed (PST):
[ ] Implement side-channel management UI | Started (PST): | Completed (PST):
[ ] Implement quest log and clue journal views | Started (PST): | Completed (PST):
[ ] Implement optional map or scene view | Started (PST): | Completed (PST):
[ ] Add Mini App submission-flow tests | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 19: Content Expansion and Quality Pass

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Add additional starter scenarios | Started (PST): | Completed (PST):
[ ] Add more puzzle patterns and trigger types | Started (PST): | Completed (PST):
[ ] Add more NPC archetypes and monster templates | Started (PST): | Completed (PST):
[ ] Improve narration style guidance and pacing rules | Started (PST): | Completed (PST):
[ ] Expand scenario validation coverage | Started (PST): | Completed (PST):
[ ] Add regression cases from long-session transcripts | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):

## Phase 20: Pre-Release Stabilization

[ ] Phase Startup | Started (PST): | Completed (PST):
[ ] Review open bugs and severity | Started (PST): | Completed (PST):
[ ] Freeze nonessential feature work | Started (PST): | Completed (PST):
[ ] Harden onboarding, diagnostics, and failure messages | Started (PST): | Completed (PST):
[ ] Review privacy, visibility, and routing safety | Started (PST): | Completed (PST):
[ ] Run extended campaigns and full regression suite | Started (PST): | Completed (PST):
[ ] Patch release blockers | Started (PST): | Completed (PST):
[ ] Update STARTUP.md and core docs to match the actual system | Started (PST): | Completed (PST):
[ ] Phase End | Started (PST): | Completed (PST):
