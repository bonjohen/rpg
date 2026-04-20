This contains an example transformation to help convert plan.md into refinedplan.md
Each phase duplicates some line items. we will remove these to common sections.

EXAMPLE of existing structure:
## Phase 0: Repository Foundation and Startup Context

[ ] Read STARTUP.md and restore working context | Started (PST): | Completed (PST):
[ ] Sync repo and review branch status | Started (PST): | Completed (PST):
[ ] Review previous phase notes, known defects, and current priorities | Started (PST): | Completed (PST):
[ ] Confirm exit criteria for Phase 0 in phase log | Started (PST): | Completed (PST):
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
[ ] Update phase notes and record Phase 0 completion state | Started (PST): | Completed (PST):
[ ] Run relevant tests and repair failures | Started (PST): | Completed (PST):
[ ] Commit Phase 0 work locally without pushing | Started (PST): | Completed (PST):

## Phase 1: Core Domain Model and Persistence

[ ] Read STARTUP.md and restore working context | Started (PST): | Completed (PST):
[ ] Sync repo and review branch status | Started (PST): | Completed (PST):
[ ] Review previous phase notes, known defects, and current priorities | Started (PST): | Completed (PST):
[ ] Confirm exit criteria for Phase 1 in phase log | Started (PST): | Completed (PST):
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
[ ] Update phase notes and record Phase 1 completion state | Started (PST): | Completed (PST):
[ ] Run relevant tests and repair failures | Started (PST): | Completed (PST):
[ ] Commit Phase 1 work locally without pushing | Started (PST): | Completed (PST):

// This extends for 20 phases. 

#####   revise as follows   #####
Follow this progression pattern with the statuses of each task:
[ ] (Open)  ──>  [X] (Started)  ──>  [#] (Completed)
        │
        └──> [!] (Blocked)  ──>  [X] (Started)  ──>  [#] (Completed)
Update Started and Completed datetimes when starting or completing a task.

At the beginning of each phase perform the following:
Phase Startup
* Sync repo and review branch status
* Read STARTUP.md and restore working context
* Review previous phase notes, known defects, and current priorities

At the end of each phase perform teh following:
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

// This extends for 20 phases. 
