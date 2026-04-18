Design Document: AI-Refereed Multiplayer Text Game on Telegram

1. Purpose

Build a multiplayer text-based adventure game that runs primarily through Telegram. The AI acts as referee, narrator, and arbitration assistant. The game server owns rules, state, timing, visibility, and turn commitment. Telegram is a workable foundation because bots can operate in private chats and groups, support commands and buttons, and can be extended with Mini Apps for richer UI. 

2. Core Product Idea

Players participate in a shared campaign in a Telegram group. The default experience is party chat in a public group thread. Secret information, referee questions, and player-specific discoveries are handled in private bot DMs. Later, a Mini App can add character sheets, inventories, maps, private inboxes, and action drafting without changing the core game loop. Telegram supports topic-aware bot messaging, inline keyboards, and multiple Mini App launch surfaces, so this staged approach fits the platform well. 

3. Design Principle

The AI is the referee voice. The server is the referee authority.

That means the AI can narrate, roleplay NPCs, summarize outcomes, and propose rulings for ambiguous actions. The server decides legality, timing, randomization, visibility, and all official state changes. This split is the main consistency safeguard. Without it, the model will eventually contradict itself, leak hidden information, or silently corrupt the game state.

4. Telegram Platform Model

Use one Telegram supergroup as the public campaign space. Enable forum topics and keep one main public topic for active play. Telegram’s Bot API supports sending to a specific topic using message_thread_id, which makes topic-based organization viable for party play, planning, loot review, or downtime scenes. 

Require every player to start a private chat with the bot before joining the game. Telegram bots always receive private messages from users, and sending a private message generally requires that the user has contacted the bot first and that the bot has the user ID saved. 

Use inline keyboards for common controls such as Ready, Pass, Ask Ref, Submit, Revise, and Open Sheet. Inline keyboards are attached directly to messages and can trigger callback behavior without posting extra messages to the chat, which makes them a strong fit for turn control and countdown handling. 

Use a Mini App later for state-heavy interfaces. Telegram Mini Apps can be launched from the bot menu, keyboard buttons, inline buttons, direct links, inline mode, and the attachment menu, so they are a practical upgrade path once the pure-chat version works. 

5. Conversation Scopes

Conversation scope should be explicit in the data model.

Public scope is visible to the full party. This is where scene narration, visible NPC dialogue, combat summaries, timer announcements, and shared planning happen.

Private referee scope is visible only to one player and the bot. This is for hidden clues, awareness results, rules questions, stealth outcomes, and personal objectives.

Private side-channel scope is visible to a selected subset of players and the bot. This supports cases like Player 1 and Player 4 keeping a quiet conversation open. This should be treated as an application-level construct, not as something inferred from the public group structure. In the first version, surface it through DM relay or defer it until the Mini App exists.

Referee-only scope is never shown directly. It includes hidden map state, trap triggers, unresolved checks, monster awareness, NPC intent, and secret quest logic.

This scope model resolves the tension between “party chat by default” and “private communication must exist.”

6. Turn Model

The game should run in response windows, not in uncontrolled message flow.

Each turn follows this sequence:

1. The server posts the current situation publicly.


2. The server sends any private facts to the affected players.


3. A countdown window opens.


4. Players discuss publicly or privately.


5. Each player submits one committed action packet.


6. The timer expires, or all players mark ready.


7. The server locks input.


8. The server resolves the turn.


9. The AI narrates the result.


10. The committed result is appended to the turn log.



This model prevents the fastest typist from dominating play and gives the server a clean point at which to resolve simultaneous actions.

7. Countdown Timer

The countdown timer should be owned entirely by the server.

Telegram supports inline keyboards and bot-driven message updates, so the bot can keep one turn-control message current while players respond through buttons and normal messages. Publicly, the timer creates shared urgency. Privately, it gives players a clear deadline for hidden questions and secret actions. 

Each player should have a default action for timeout, such as hold, defend, continue prior stance, or no additional contribution. That keeps the round moving and prevents one absent player from freezing the game.

8. Committed Action Packets

Players may talk freely during the response window, but only one committed action packet per player is authoritative for resolution.

A committed action packet should include:

declared action type

target or destination

item or ability use

optional public statement

optional private note to referee

readiness state

timestamp


The packet model separates social chatter from game resolution. That improves fairness, replayability, and debugging.

9. NPC Design

NPCs should be modeled in three layers.

Hard state is owned by code. It includes location, health, inventory, faction, status effects, and scene participation.

Durable mind is compact structured memory. It includes goals, loyalties, fears, trust by player, stance toward the party, and memory tags such as “Player 2 returned heirloom” or “Player 1 lied about identity.”

Presentation is owned by the AI. It includes dialogue, emotional tone, body language, and improvisation.

This separation makes NPCs feel alive without allowing the model to rewrite core facts.

10. Monster Design

Monsters should usually be tactical actors, not full conversational agents.

A monster or monster group should have:

behavior mode

awareness state

threat priorities

morale

formation or terrain state

special abilities

reinforcement behavior


Common behavior modes are patrol, ambush, defend, pursue, flee, guard, and call help. Weak enemies should usually be grouped into units rather than processed as fully separate minds, because messaging combat becomes unreadable if too many low-value enemy turns are narrated one by one.

11. Hidden Information

The server must explicitly scope what each actor and each player knows.

Do not let the AI infer knowledge from raw chat history alone. The server should send the AI a scoped knowledge packet for each resolution step. That is how you prevent omniscient monsters, leaking clues, and NPCs reacting to facts they were never given.

A passed awareness check should create a player-private fact. A hidden monster should remain hidden from the public scene. A suspicious NPC may privately distrust one player while publicly addressing the group politely.

12. Bot Permissions and Message Visibility

The bot must be configured so it can actually observe the messages it needs. Telegram bots always receive private messages. In groups, bot admins and bots with privacy mode disabled receive all messages except messages sent by other bots; bots with privacy mode enabled receive a narrower subset. This matters because your design assumes that the referee can see public player discussion in the party chat. 

The practical recommendation is to make the bot a group admin for the campaign group and keep the group structure simple.

13. Use Cases

Use Case 1: Standard exploration turn

The party is in the main play topic. The bot posts the room description and opens a 90-second timer. Player 1 inspects the altar. Player 2 watches the hallway. Player 3 asks the referee privately whether the markings match a known cult. Player 4 says nothing and times out. The server resolves all four states together, applies Player 4’s default action, and the AI posts one coherent scene update.

Use Case 2: Private awareness result

Player 2 passes an awareness check. The server creates a private fact and sends it only to Player 2 in DM: “You notice a thin draft from behind the west wall.” The public group does not see this. If Player 2 shares it in public chat, that becomes a normal player action in the next window.

Use Case 3: Private player-to-player coordination

Player 1 and Player 4 maintain a side-channel. They discuss hiding a relic from the party. The side-channel is visible only to them and the bot. Publicly, both still appear to be participating normally in the party thread. Their later public actions may reveal or conceal the private plan.

Use Case 4: Secret referee question

Player 3 privately asks, “Can I tell whether the merchant is lying?” The server checks whether this is free information or requires a roll. If a check is needed, it resolves that privately. The public scene remains uninterrupted.

Use Case 5: Group combat round

Combat begins. The bot posts a battlefield summary with inline controls. Each player submits one committed packet before the timer expires. The server resolves all player actions, enemy behavior, movement conflicts, and damage. The AI posts one readable combat summary instead of many fragmented micro-messages.

Use Case 6: Split party

Two players stay with the injured NPC while two move into the crypt. The server tracks two scene contexts. Each subgroup gets relevant prompts. The turn system still works because scope and scene state are explicit rather than assumed from a single linear chat history.

14. MVP Recommendation

The first release should include:

one Telegram supergroup

one public play topic

one bot DM per player

one countdown-controlled turn loop

one committed action packet per player per turn

one exploration loop

one social loop

one combat loop

basic NPC memory tags

grouped monster encounters

append-only turn log

player-private clue delivery


Do not build private player-to-player channels into the first release unless you need them immediately. They are valuable, but they add significant UI and state complexity. Start with public play plus private referee communication.

15. Phase 2 Recommendation

After the core loop works, add a Mini App for:

character sheet

inventory

action drafting

map

quest log

private inbox

side-channel management

recap and replay views


Mini Apps are the right place for this because Telegram already supports multiple launch surfaces and richer in-app interaction than pure chat. 
