Product Design Requirements: AI-Refereed Multiplayer Text Game on Telegram
1. Product Intent
Build a multiplayer text-based adventure game that runs primarily through Telegram. Players interact in a shared party chat, can communicate privately with the referee bot, and can receive player-specific hidden information. The AI acts as narrator, NPC voice, and arbitration assistant. The application server owns canonical state, timing, legality, visibility, randomization, and turn commitment. Telegram is a suitable base because its Bot API is HTTP-based, supports commands, keyboards, buttons, topic-aware messaging, and Mini Apps for richer interfaces. (Telegram)
2. Core Principle
The AI is the referee voice. The server is the referee authority.
The AI may narrate scenes, speak as NPCs, summarize outcomes, and propose rulings for ambiguous actions. The server must decide what actions are legal, what each actor knows, when the timer closes, what random outcomes occur, and what state changes are committed. This split is the main consistency rule for the entire product.
3. Platform Model
The public campaign space should be a Telegram supergroup with forum topics enabled. One main topic should be the active play thread. Additional public topics may be used for planning, downtime, or administrative organization. Telegram supports sending bot messages to specific topics through message_thread_id, so topic-based organization is a supported part of the design. (Telegram)
Each player must also start a private DM with the bot before play begins. Private DMs are the primary channel for secret clues, awareness results, stealth outcomes, rules questions, and player-specific objectives. In groups, the bot should be an admin so it can reliably observe the messages it needs for public play. Telegram documents that bot admins, or bots with privacy mode disabled, receive all group messages except those sent by other bots. (Telegram)
A Telegram Mini App is not required for the first release, but it is the correct expansion path for richer UI such as character sheets, inventories, maps, action drafting, and private inboxes. Telegram’s Mini App documentation explicitly calls out cooperative and multiplayer chat-context use cases and supports launch surfaces such as bot links, the menu, and other bot-driven entry points. (Telegram)
4. Product Goals
The product must support public party play by default.
The product must support private player-to-referee communication.
The product must support player-specific hidden information.
The product must support a countdown timer for simultaneous response windows.
The product must prevent chat order from becoming accidental game truth.
The product must support consistent NPC and monster behavior over long sessions.
The product should support future expansion into a Mini App without redesigning the core game loop.
5. Non-Goals
The first release is not a real-time action game.
The first release is not a virtual tabletop.
The first release does not allow the LLM to directly mutate canonical game state.
The first release does not depend on Telegram public topics for secrecy between selected players.
The first release does not require a Mini App.
6. LLM Routing and Model Responsibilities
The system should split LLM calls into two tiers.
6.1 Fast local model tier
Use small local models for fast, cheap, low-risk tasks such as:
intent classification
command normalization
action packet extraction
simple rules lookup phrasing
summarizing recent public chat into a compact turn context
generating short clarification questions
selecting likely scope such as public, private-referee, or side-channel
lightweight moderation and format repair
This tier should be optimized for low latency and high call volume. It should not narrate the authoritative scene and should not handle major ambiguity in outcomes.
6.2 Main game model tier
Use Gemma 4 26B A4B as the primary local gameplay model for:
scene narration
NPC dialogue
social arbitration proposals
combat summary prose
puzzle response flavor
interpreting unusual player actions when structured code is insufficient
generating structured ruling proposals for the server to validate
Google’s Gemma 4 family includes a 26B A4B model and a 31B dense model. The Gemma 4 model card states that the “A” in 26B A4B means active parameters, with only a 4B subset activated during inference, making it much faster than the dense 31B model, while still retaining strong benchmark performance and up to a 256K context window for the 26B A4B and 31B variants. That makes Gemma 4 26B A4B a strong fit for game-referee work that needs better quality than very small models while still caring about local inference speed. (Google AI for Developers)
6.3 Routing rule
All authoritative turn resolution remains server-side.
The fast tier should be the default first stop. If the request is simple, structured, and low-stakes, the fast tier handles it. If the request affects narrative quality, NPC behavior, social interpretation, or unusual player intent, route to Gemma 4 26B A4B. If the main model fails schema validation or exceeds latency targets, the server should fall back to a simpler deterministic response rather than block the turn.
7. Core Conversation Scopes
Conversation scope is a first-class concept.
7.1 Public scope
Visible to the whole party. This includes:
scene narration
visible NPC dialogue
combat summaries
timer announcements
public player discussion
party-visible consequences
7.2 Private referee scope
Visible only to one player and the bot. This includes:
awareness results
secret clues
rules questions
stealth outcomes
hidden objectives
player-specific lore recognition
7.3 Private side-channel scope
Visible only to a selected subset of players and the bot. This supports cases such as Player 1 and Player 4 keeping a hidden channel open. This is an application-defined scope. It should not depend on public Telegram topics for secrecy.
7.4 Referee-only scope
Visible only to the server and referee systems. This includes:
trap triggers
hidden map links
NPC intent
monster awareness
unrevealed facts
unresolved checks
8. Core Turn Model
The game runs in response windows.
A turn begins when the server posts the current situation to the public play topic. The server also delivers any newly relevant private information to the affected players. A countdown timer opens. Players may talk publicly or privately during that window. Each player submits one committed action packet. When the timer expires, or all players are marked ready, the server locks input, resolves the turn, commits the result, and then asks the main game model to narrate the official outcome.
This structure applies to exploration, social scenes, and combat. Only the resolution rules differ.
9. Countdown Timer Requirements
The timer must be server-owned.
The timer must be visible in the public thread.
The timer must define the official close of the response window.
The timer may end early if all players are ready.
The timer may pause only through explicit server rules such as admin pause or scenario pause.
The AI may describe urgency, but it does not control the clock.
Telegram supports message-attached buttons and bot-edited messages, which fits a turn-control message with Ready, Pass, Ask Ref, Revise, and Submit controls. (Telegram)
10. Timeout Policy
Each character must have a defined fallback action for missed turns.
Typical fallbacks:
hold position
defend
continue prior stance
remain silent
follow leader
no additional contribution
Timeout fallback must be deterministic, logged, and visible in the audit trail. One missing player must never stall the session.
11. Committed Action Packet
Players may chat freely, but only one committed action packet per player affects official resolution.
A committed action packet should contain:
action_id
turn_window_id
player_id
scope_id
declared_action_type
public_text
private_ref_text
target_ids
movement_target
item_ids
ability_ids
ready_state
submitted_at
validation_status
This packet is the basis of fair simultaneous resolution.
12. NPC System
NPCs should be modeled in three layers.
12.1 Hard state
Owned by code:
location
health
inventory
faction
status effects
scene membership
visibility state
12.2 Durable mind
Owned by the server as structured state:
goals
loyalties
fears
personality tags
trust by player
party stance
memory tags
12.3 Presentation
Owned by the main gameplay model:
dialogue
emotional tone
rhetorical style
descriptive behavior
The model may propose changes to durable mind, but the server approves and commits them.
13. Monster System
Monsters should usually be tactical actors rather than full conversational agents.
A monster or monster group should track:
behavior mode
awareness state
morale
target priorities
formation or positional state
special rules
territory or pursuit constraints
Common behavior modes:
patrol
ambush
defend
pursue
flee
guard
call help
Small enemies should usually be grouped to keep combat readable and efficient.
14. Knowledge and Visibility
The server must explicitly control who knows what.
Public facts are visible to all players in the scene.
Private facts are visible only to their player and the bot.
Side-channel facts are visible only to the allowed subset and the bot.
Referee-only facts remain hidden until revealed.
The LLM must receive scoped knowledge packets, not unrestricted raw history, when secrecy matters. This is essential to prevent omniscient enemies, clue leakage, and inconsistent NPC reactions.
15. Responsibilities by Layer
15.1 Fast local model tier
Responsible for:
parsing messages
classifying intent
extracting action fields
selecting likely scope
summarizing recent context
formatting repair
cheap clarification prompts
Not responsible for:
official narration
major social arbitration
complex NPC speech
final turn prose
15.2 Gemma 4 26B A4B tier
Responsible for:
official narration after resolution
NPC dialogue
descriptive combat summaries
structured ruling proposals for ambiguous actions
scene flavor and pacing
Not responsible for:
final legality
official randomness
direct state mutation
visibility enforcement
15.3 Server
Responsible for:
state storage
timer control
action validation
rules resolution
randomization
scope enforcement
append-only turn log
replay and audit
invoking the right model tier
16. Major Use Cases
Use Case 1: Standard exploration turn
The bot posts a room description in the public topic and opens a 90-second timer. Players discuss publicly. Each submits one action packet. Player 3 also privately asks the referee whether a symbol is familiar. The server resolves movement, checks, and discoveries, then the main model narrates the official scene result.
Use Case 2: Private awareness result
Player 2 passes an awareness check. The server records a private fact and sends it only to Player 2 in DM. The public group does not see it. If Player 2 shares it later, that is a normal public action.
Use Case 3: Hidden side-channel
Player 1 and Player 4 maintain a private channel about hiding a relic. Their side-channel is visible only to them and the bot. Their public actions later may reveal or conceal that plan.
Use Case 4: Combat with countdown
Combat starts. The public topic shows the battlefield summary and the timer. Each player submits one action. The server resolves all movement, attacks, effects, morale changes, and visibility. The main model posts one coherent combat summary rather than fragmented per-actor chatter.
Use Case 5: Missing response
Player 4 does not answer before timeout. The server applies the configured fallback action. The session proceeds without delay.
Use Case 6: Split party
Two players move ahead while two remain behind. The server maintains explicit scene membership and scoped prompts for each subgroup. Public play remains organized without corrupting the canonical state.
17. Functional Requirements
The system must support campaign creation.
The system must support onboarding by group join plus player DM initiation.
The system must support one main public play topic.
The system must support one private DM channel per player.
The system must support timer-driven response windows.
The system must support one committed action packet per player per turn.
The system must support timeout fallback actions.
The system must support NPC state, monster state, inventory, quests, and puzzles.
The system must support scoped delivery of private information.
The system must support append-only turn logging.
The system must support split LLM routing between fast local models and Gemma 4 26B A4B.
The system should support later Mini App expansion for sheet, inventory, map, and inbox features. Telegram Mini Apps are designed for richer bot-linked interfaces and explicitly support multiplayer or teamwork-oriented services in a chat context. (Telegram)
18. Non-Functional Requirements
Turn resolution should feel fast enough for synchronous play.
Small-model calls should be low-latency and cheap.
Gemma gameplay calls should be bounded by schema, prompt size, and timeout policy.
State writes must be atomic at turn commit.
Private and public messages must remain consistent within a turn.
The system must tolerate delayed or missing player responses.
The system must remain readable across long campaigns.
19. Data Model
Core entities:
Campaign
Player
Character
GroupChat
Topic
ConversationScope
SideChannel
Scene
TurnWindow
CommittedAction
TurnLogEntry
NPC
MonsterGroup
InventoryItem
QuestState
PuzzleState
KnowledgeFact
VisibilityGrant
Suggested NPC fields:
npc_id
campaign_id
scene_id
health_state
inventory_state
faction_id
stance_to_party
trust_by_player
goal_tags
fear_tags
personality_tags
memory_tags
knowledge_fact_ids
current_behavior_mode
is_visible
Suggested MonsterGroup fields:
monster_group_id
campaign_id
scene_id
unit_type
count
behavior_mode
awareness_state
threat_table
morale_state
formation_state
territory_id
special_rules
Suggested TurnWindow fields:
turn_window_id
campaign_id
scene_id
public_scope_id
opened_at
expires_at
locked_at
status
timeout_policy_id
Suggested KnowledgeFact fields:
fact_id
campaign_id
scene_id
owner_scope_id
fact_type
payload
revealed_at
source_event_id
20. State Machines
Scene states:
idle
prompting
awaiting_actions
resolving
narrated
paused
Turn window states:
open
all_ready
locked
resolving
committed
aborted
Committed action states:
draft
submitted
validated
rejected
resolved
These states must be explicit in storage, not inferred from message order.
21. Rules Resolution Strategy
Straightforward actions resolve in code.
Ambiguous actions are converted into a structured referee request.
The fast model may normalize or classify the request first.
Gemma 4 26B A4B then returns a structured ruling proposal containing interpreted intent, relevant rule hooks, and narrative framing.
The server validates that proposal, applies deterministic rules, performs any rolls, commits the canonical result, and then asks Gemma to produce the final prose narration.
This keeps the system expressive without giving the LLM direct authority over truth.
22. Telegram Control Surface
Initial commands:
/start
/join
/help
/status
/ready
/pass
/sheet
/inventory
/log
/recap
Public play should rely mostly on free text plus inline controls rather than command-heavy interaction. Telegram’s bot features include commands, keyboards, and buttons, which is enough for the MVP control surface. (Telegram)
23. Mini App Expansion Plan
Phase 2 should add a Mini App for:
character sheet
inventory
map
quest log
private inbox
side-channel management
draft action builder
turn recap
This is a later phase, not an MVP dependency. Telegram’s Mini App documentation supports this direction and explicitly positions Mini Apps for full-featured multiplayer or teamwork-oriented services inside chat contexts. (Telegram)
24. MVP Scope
MVP includes:
one Telegram supergroup
one main public play topic
one DM channel per player
one timer-driven turn loop
one committed action per player per turn
one exploration loop
one social loop
one combat loop
basic NPC memory tags
grouped monster encounters
player-private clue delivery
append-only turn logging
split LLM routing with fast local models plus Gemma 4 26B A4B
MVP excludes:
Mini App dependency
advanced side-channel UI
live maps
scenario authoring suite
real-time combat
25. Success Criteria
A four-player party can complete a session without turn-order confusion.
Private awareness results are delivered correctly without leaking.
A missed player response does not stall the session.
NPC continuity remains coherent across many turns.
Combat rounds remain readable and timely.
Small-model routing reduces cost and latency for simple requests.
Gemma 4 26B A4B provides noticeably better gameplay narration and arbitration quality than the fast tier for complex turns.
26. Risks
The largest risk is letting the LLM act as the game engine.
The second risk is failing to scope knowledge tightly enough.
The third risk is chat clutter in group combat.
The fourth risk is overusing the main gameplay model for tasks that should stay in the fast tier.
The fifth risk is overbuilding UI before the core turn loop is proven.
