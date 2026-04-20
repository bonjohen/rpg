"""Top-level coordinator that wires bot gateway, turn engine, model adapters,
scope engine, timer, and all game loop subsystems into a single runnable loop.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from typing import TypeVar

    from sqlalchemy.orm import Session, sessionmaker

    T = TypeVar("T")

from bot.config import BotConfig
from bot.mapping import BotRegistry
from models.contracts.context_assembly import ContextAssembler
from models.contracts.output_repair import RepairPipeline
from models.fast.adapter import OllamaFastAdapter
from models.fast.tasks import classify_intent, extract_action_packet
from models.protocol import MainAdapter
from scenarios.loader import ScenarioLoader
from server.combat.conditions import CombatConditionEngine
from server.domain.entities import (
    Campaign,
    Character,
    CommittedAction,
    ConversationScope,
    InventoryItem,
    KnowledgeFact,
    MonsterGroup,
    NPC,
    Player,
    PuzzleState,
    QuestState,
    Scene,
    SideChannel,
    TurnLogEntry,
    TurnWindow,
)
from server.domain.enums import (
    ActionState,
    ActionType,
    ReadyState,
    SceneState,
    ScopeType,
    TurnWindowState,
    ValidationStatus,
)
from server.engine.turn_engine import TurnEngine
from server.exploration.actions import ExplorationEngine
from server.exploration.movement import MovementEngine
from server.exploration.triggers import TriggerEngine
from server.npc.social import SocialEngine
from server.npc.trust import TrustEngine
from server.observability.diagnostics import DiagnosticsEngine
from server.observability.metrics import MetricsCollector
from server.reliability.idempotency import IdempotencyStore
from server.scene.membership import SceneMembershipEngine
from server.domain.helpers import new_id, utc_now
from server.scope.engine import ScopeEngine
from server.timer.controller import TimerController


@dataclass
class DispatchResult:
    """Result of processing a player message through the orchestrator."""

    handled: bool = False
    response_text: str = ""
    scope: str = "public"
    action_submitted: bool = False
    error: str = ""


class GameOrchestrator:
    """Wires all subsystems into a runnable game loop.

    Accepts an optional ``session_factory`` for database-backed persistence.
    When provided, ``_session_scope()`` and ``_run_in_session()`` become
    available for transactional access.  In-memory dicts are still used
    during the migration; they will be removed phase-by-phase.
    """

    def __init__(
        self,
        fast_adapter: OllamaFastAdapter | None = None,
        main_adapter: MainAdapter | None = None,
        bot_registry: BotRegistry | None = None,
        config: BotConfig | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.fast_adapter = fast_adapter
        self.main_adapter = main_adapter
        self.bot_registry = bot_registry or BotRegistry()
        self.config = config
        self.session_factory = session_factory

        # Game state dicts
        self.campaign: Campaign | None = None
        self.scenes: dict[str, Scene] = {}
        self.characters: dict[str, Character] = {}
        self.players: dict[str, Player] = {}
        self.npcs: dict[str, NPC] = {}
        self.monster_groups: dict[str, MonsterGroup] = {}
        self.items: dict[str, InventoryItem] = {}
        self.puzzles: dict[str, PuzzleState] = {}
        self.quests: dict[str, QuestState] = {}
        self.knowledge_facts: dict[str, KnowledgeFact] = {}
        self.scopes: dict[str, ConversationScope] = {}
        self.triggers: list = []
        self.turn_windows: dict[str, TurnWindow] = {}
        self.committed_actions: dict[str, CommittedAction] = {}
        self.turn_log: list[TurnLogEntry] = []
        self.side_channels: dict[str, SideChannel] = {}

        # Phase 18: in-memory draft and inbox-read tracking
        self.drafts: dict[str, dict] = {}  # player_id -> draft dict
        self.inbox_read: dict[str, set[str]] = {}  # player_id -> set of read fact_ids
        self.channel_messages: dict[str, list[dict]] = {}  # channel_id -> messages

        # Engines (all stateless, instantiated once)
        self.turn_engine = TurnEngine()
        self.scope_engine = ScopeEngine()
        self.movement_engine = MovementEngine()
        self.exploration_engine = ExplorationEngine()
        self.trigger_engine = TriggerEngine()
        self.combat_condition_engine = CombatConditionEngine()
        self.social_engine = SocialEngine()
        self.trust_engine = TrustEngine()
        self.membership_engine = SceneMembershipEngine()
        self.timer_controller = TimerController()
        self.diagnostics_engine = DiagnosticsEngine()
        self.context_assembler = ContextAssembler()
        self.repair_pipeline = RepairPipeline(fast_adapter=fast_adapter)
        self.scenario_loader = ScenarioLoader()
        self.metrics = MetricsCollector()
        self.idempotency = IdempotencyStore()

        # Timer state (timer_id -> TimerRecord)
        self.timers: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Database session helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _session_scope(self) -> Generator[Session, None, None]:
        """Yield a database session; commit on clean exit, rollback on error.

        Raises RuntimeError if no session_factory is configured.
        """
        if self.session_factory is None:
            raise RuntimeError("No session_factory configured on GameOrchestrator")
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    async def _run_in_session(self, fn: Callable[[Session], T]) -> T:
        """Run *fn* with a database session in a thread-pool executor.

        The callable receives a ``Session`` that is committed on success
        and rolled back on failure, mirroring ``_session_scope`` semantics.
        """
        loop = asyncio.get_running_loop()

        def _wrapper() -> T:
            with self._session_scope() as session:
                return fn(session)

        return await loop.run_in_executor(None, _wrapper)

    # ------------------------------------------------------------------
    # Scenario loading
    # ------------------------------------------------------------------

    def load_scenario(self, yaml_path: str, campaign_name: str = "Playtest") -> bool:
        """Load a scenario from YAML, populate all state dicts."""
        result = self.scenario_loader.load_from_yaml(yaml_path)
        if not result.success:
            return False

        campaign_id = result.campaign_id
        self.campaign = Campaign(
            campaign_id=campaign_id,
            name=campaign_name,
            telegram_group_id=0,
            main_topic_id=None,
            created_at=utc_now(),
        )

        for scene in result.scenes:
            self.scenes[scene.scene_id] = scene
        for npc in result.npcs:
            self.npcs[npc.npc_id] = npc
        for mg in result.monster_groups:
            self.monster_groups[mg.monster_group_id] = mg
        for item in result.items:
            self.items[item.item_id] = item
        for puzzle in result.puzzles:
            self.puzzles[puzzle.puzzle_state_id] = puzzle
        for quest in result.quests:
            self.quests[quest.quest_state_id] = quest
        for fact in result.knowledge_facts:
            self.knowledge_facts[fact.fact_id] = fact
        for scope in result.scopes:
            self.scopes[scope.scope_id] = scope
        self.triggers = list(result.triggers)

        return True

    # ------------------------------------------------------------------
    # Player management
    # ------------------------------------------------------------------

    def add_player(
        self,
        player_id: str,
        display_name: str,
        telegram_user_id: int = 0,
        starting_scene_id: str | None = None,
    ) -> tuple[Player, Character]:
        """Register a player and create a character in the starting scene."""
        if self.campaign is None:
            raise RuntimeError("No campaign loaded")

        campaign_id = self.campaign.campaign_id
        now = utc_now()

        player = Player(
            player_id=player_id,
            campaign_id=campaign_id,
            telegram_user_id=telegram_user_id,
            telegram_username=None,
            display_name=display_name,
            joined_at=now,
            has_dm_open=True,
        )
        self.players[player_id] = player

        # Determine starting scene
        if starting_scene_id is None:
            starting_scene_id = self._find_starting_scene_id()

        char_id = new_id()
        character = Character(
            character_id=char_id,
            player_id=player_id,
            campaign_id=campaign_id,
            name=display_name,
            created_at=now,
            scene_id=starting_scene_id,
            stats={"hp": 20, "attack": 5, "defense": 3},
        )
        self.characters[char_id] = character

        # Add to scene membership
        if starting_scene_id and starting_scene_id in self.scenes:
            scene = self.scenes[starting_scene_id]
            result = self.membership_engine.add_character(scene, character)
            if result.success:
                self.scenes[starting_scene_id] = result.scene

        # Create private-referee scope for this player
        private_scope = ConversationScope(
            scope_id=new_id(),
            campaign_id=campaign_id,
            scope_type=ScopeType.private_referee,
            player_id=player_id,
        )
        self.scopes[private_scope.scope_id] = private_scope

        return player, character

    def _find_starting_scene_id(self) -> str | None:
        """Find the starting scene — first scene in the dict."""
        if self.scenes:
            return next(iter(self.scenes))
        return None

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def open_turn(self, scene_id: str, duration_seconds: int = 90) -> TurnWindow | None:
        """Create a new TurnWindow for a scene."""
        if self.campaign is None:
            return None
        scene = self.scenes.get(scene_id)
        if scene is None:
            return None

        # Find or create public scope for this scene
        public_scope_id = self._get_or_create_public_scope(scene_id)

        # Determine turn number
        scene_turns = [e for e in self.turn_log if e.scene_id == scene_id]
        turn_number = len(scene_turns) + 1

        now = utc_now()
        tw = TurnWindow(
            turn_window_id=new_id(),
            campaign_id=self.campaign.campaign_id,
            scene_id=scene_id,
            public_scope_id=public_scope_id,
            opened_at=now,
            expires_at=datetime.fromtimestamp(
                now.timestamp() + duration_seconds, tz=timezone.utc
            ),
            state=TurnWindowState.open,
            turn_number=turn_number,
        )
        self.turn_windows[tw.turn_window_id] = tw

        # Update scene
        scene.active_turn_window_id = tw.turn_window_id
        scene.state = SceneState.awaiting_actions

        # Create timer
        timer = self.timer_controller.create_timer(
            tw.turn_window_id, self.campaign.campaign_id, duration_seconds
        )
        timer = self.timer_controller.start(timer, now)
        self.timers[timer.timer_id] = timer

        return tw

    def submit_action(
        self,
        player_id: str,
        action_type: ActionType,
        public_text: str = "",
        private_ref_text: str = "",
        target_ids: list[str] | None = None,
        movement_target: str | None = None,
        item_ids: list[str] | None = None,
    ) -> CommittedAction | None:
        """Submit an action for a player in their current scene's turn window."""
        character = self.get_player_character(player_id)
        if character is None or character.scene_id is None:
            return None

        scene = self.scenes.get(character.scene_id)
        if scene is None or scene.active_turn_window_id is None:
            return None

        tw = self.turn_windows.get(scene.active_turn_window_id)
        if tw is None or tw.state != TurnWindowState.open:
            return None

        # Find player's private scope
        private_scope_id = self._get_private_scope_id(player_id)

        action = CommittedAction(
            action_id=new_id(),
            turn_window_id=tw.turn_window_id,
            player_id=player_id,
            character_id=character.character_id,
            scope_id=private_scope_id or "",
            declared_action_type=action_type,
            public_text=public_text,
            private_ref_text=private_ref_text,
            target_ids=target_ids or [],
            movement_target=movement_target,
            item_ids=item_ids or [],
            ready_state=ReadyState.ready,
            submitted_at=utc_now(),
            state=ActionState.submitted,
            validation_status=ValidationStatus.valid,
        )

        # Get existing actions for this turn
        existing = [
            a
            for a in self.committed_actions.values()
            if a.turn_window_id == tw.turn_window_id
        ]
        result = self.turn_engine.submit_action(tw, action, existing)
        if not result.accepted:
            return None

        self.committed_actions[action.action_id] = action

        # Check if all players ready
        expected_player_ids = self._get_scene_player_ids(scene)
        all_actions = [
            a
            for a in self.committed_actions.values()
            if a.turn_window_id == tw.turn_window_id
        ]
        updated_tw = self.turn_engine.check_all_ready(
            self.turn_windows[tw.turn_window_id], all_actions, expected_player_ids
        )
        self.turn_windows[tw.turn_window_id] = updated_tw

        return action

    def resolve_turn(self, turn_window_id: str) -> TurnLogEntry | None:
        """Lock, resolve actions, generate narration, and commit a turn."""
        tw = self.turn_windows.get(turn_window_id)
        if tw is None:
            return None

        scene = self.scenes.get(tw.scene_id)
        if scene is None:
            return None

        # Gather actions
        actions = [
            a
            for a in self.committed_actions.values()
            if a.turn_window_id == turn_window_id
        ]

        # Build characters_by_player map
        expected_player_ids = self._get_scene_player_ids(scene)
        chars_by_player = {}
        for pid in expected_player_ids:
            char = self.get_player_character(pid)
            if char:
                chars_by_player[pid] = char.character_id

        # Synthesize fallback actions for missing players
        submitted_players = {a.player_id for a in actions}
        timeout_players = [
            pid for pid in expected_player_ids if pid not in submitted_players
        ]
        for pid in timeout_players:
            char = self.get_player_character(pid)
            if char is None:
                continue
            fallback = CommittedAction(
                action_id=new_id(),
                turn_window_id=turn_window_id,
                player_id=pid,
                character_id=char.character_id,
                scope_id="",
                declared_action_type=ActionType.hold,
                public_text="",
                private_ref_text="",
                ready_state=ReadyState.ready,
                submitted_at=utc_now(),
                state=ActionState.submitted,
                validation_status=ValidationStatus.valid,
                is_timeout_fallback=True,
            )
            self.committed_actions[fallback.action_id] = fallback
            actions.append(fallback)

        # Lock
        if tw.state == TurnWindowState.open or tw.state == TurnWindowState.all_ready:
            lock_result = self.turn_engine.lock_window(tw)
            if not lock_result.locked:
                return None
            tw = lock_result.window
            self.turn_windows[turn_window_id] = tw

        # Resolve
        resolve_result = self.turn_engine.resolve_window(
            tw, actions, chars_by_player, timeout_players or None
        )
        if not resolve_result.resolved:
            return None
        tw = resolve_result.window
        self.turn_windows[turn_window_id] = tw

        # Apply action effects and collect narration fragments
        narration_parts = [f"In {scene.name}:"]
        for action in resolve_result.ordered_actions:
            char = self.characters.get(action.character_id)
            char_name = char.name if char else "Unknown"
            if action.is_timeout_fallback:
                narration_parts.append(f"{char_name} hesitates, unsure what to do.")
            else:
                effect_text = self._apply_action_effects(action, scene)
                if effect_text:
                    narration_parts.append(effect_text)
                else:
                    narration_parts.append(
                        f"{char_name} performs {action.declared_action_type.value}."
                    )
        narration = " ".join(narration_parts)

        # Build state snapshot
        state_snapshot = {
            "scene_id": scene.scene_id,
            "player_count": len(expected_player_ids),
            "action_count": len(actions),
        }

        # Commit
        commit_result = self.turn_engine.commit_window(
            tw, resolve_result.ordered_actions, narration, state_snapshot
        )
        if not commit_result.committed:
            return None

        tw = commit_result.window
        self.turn_windows[turn_window_id] = tw
        log_entry = commit_result.log_entry
        if log_entry:
            self.turn_log.append(log_entry)

        # Clean up scene state
        scene.active_turn_window_id = None
        scene.state = SceneState.narrated

        return log_entry

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_player_message(
        self, player_id: str, text: str, is_private: bool
    ) -> DispatchResult:
        """Process a player message through intent classification and routing."""
        result = DispatchResult()

        # Check idempotency (keyed on player_id + text hash for simplicity)
        idem_key = f"msg:{player_id}:{hash(text)}"
        if not self.idempotency.mark_seen(idem_key):
            result.handled = True
            result.response_text = ""
            return result

        # If no fast adapter, treat everything as a custom action
        if self.fast_adapter is None:
            return await self._handle_as_action(player_id, text, is_private)

        # Classify intent via fast model
        intent_result, _ = await classify_intent(
            self.fast_adapter, text, trace_id=new_id()
        )

        intent = intent_result.intent.lower()

        if intent == "action":
            return await self._handle_as_action(player_id, text, is_private)
        elif intent == "question":
            result.handled = True
            result.scope = "private"
            result.response_text = (
                "Your question has been noted. The referee will respond."
            )
            return result
        elif intent == "command":
            result.handled = True
            result.response_text = f"Command received: {text}"
            return result
        else:
            # Chat — log but don't process
            result.handled = True
            result.response_text = ""
            return result

    async def _handle_as_action(
        self, player_id: str, text: str, is_private: bool
    ) -> DispatchResult:
        """Extract action packet and submit."""
        result = DispatchResult()

        character = self.get_player_character(player_id)
        if character is None:
            result.error = "No character found."
            return result

        # Try to extract action packet via fast model
        available_types = [at.value for at in ActionType]
        if self.fast_adapter:
            packet, _ = await extract_action_packet(
                self.fast_adapter, text, available_types, trace_id=new_id()
            )
            try:
                action_type = ActionType(packet.action_type)
            except ValueError:
                action_type = ActionType.custom
            target_ids = [packet.target] if packet.target else []
            item_ids = packet.item_ids
        else:
            action_type = ActionType.custom
            target_ids = []
            item_ids = []

        action = self.submit_action(
            player_id=player_id,
            action_type=action_type,
            public_text=text,
            target_ids=target_ids,
            item_ids=item_ids,
        )

        if action:
            result.handled = True
            result.action_submitted = True
            result.response_text = (
                f"Action submitted: {action.declared_action_type.value}"
            )
        else:
            result.error = (
                "Could not submit action. No active turn or already submitted."
            )

        return result

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_player_scene(self, player_id: str) -> Scene | None:
        """Look up which scene a player's character is in."""
        char = self.get_player_character(player_id)
        if char is None or char.scene_id is None:
            return None
        return self.scenes.get(char.scene_id)

    def get_scene_players(self, scene_id: str) -> list[Player]:
        """Return all players whose characters are in this scene."""
        player_ids = self._get_scene_player_ids(
            self.scenes.get(
                scene_id,
                Scene(
                    scene_id="",
                    campaign_id="",
                    name="",
                    description="",
                    created_at=utc_now(),
                    state=SceneState.idle,
                ),
            )
        )
        return [self.players[pid] for pid in player_ids if pid in self.players]

    def get_turn_log_for_scene(self, scene_id: str) -> list[TurnLogEntry]:
        """Get all turn log entries for a scene, ordered by turn number."""
        entries = [e for e in self.turn_log if e.scene_id == scene_id]
        entries.sort(key=lambda e: e.turn_number)
        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def get_player_character(self, player_id: str) -> Character | None:
        for char in self.characters.values():
            if char.player_id == player_id:
                return char
        return None

    def _get_scene_player_ids(self, scene: Scene) -> list[str]:
        """Get player IDs for characters in a scene."""
        player_ids = []
        for char in self.characters.values():
            if char.scene_id == scene.scene_id and char.is_alive:
                player_ids.append(char.player_id)
        return player_ids

    def _get_private_scope_id(self, player_id: str) -> str | None:
        for scope in self.scopes.values():
            if (
                scope.scope_type == ScopeType.private_referee
                and scope.player_id == player_id
            ):
                return scope.scope_id
        return None

    def _get_or_create_public_scope(self, scene_id: str) -> str:
        """Get or create a public scope for a scene."""
        for scope in self.scopes.values():
            if scope.scope_type == ScopeType.public:
                return scope.scope_id
        scope = ConversationScope(
            scope_id=new_id(),
            campaign_id=self.campaign.campaign_id if self.campaign else "",
            scope_type=ScopeType.public,
        )
        self.scopes[scope.scope_id] = scope
        return scope.scope_id

    def _apply_action_effects(self, action: CommittedAction, scene: Scene) -> str:
        """Apply resolved action effects to game state. Returns effect text."""
        character = self.characters.get(action.character_id)
        if character is None:
            return ""

        action_type = action.declared_action_type

        if action_type == ActionType.move:
            return self._apply_move(character, scene, action)
        elif action_type == ActionType.inspect:
            return self._apply_inspect(character, scene, action)
        elif action_type == ActionType.search:
            return self._apply_search(character, scene, action)
        elif action_type == ActionType.attack:
            return self._apply_attack(character, scene, action)
        elif action_type in (
            ActionType.question,
            ActionType.persuade,
            ActionType.threaten,
            ActionType.lie,
            ActionType.bargain,
        ):
            return self._apply_social(character, scene, action)
        elif action_type in (ActionType.hold, ActionType.pass_turn):
            return f"{character.name} holds position."
        else:
            return f"{character.name} performs {action_type.value}."

    def _apply_move(
        self, character: Character, scene: Scene, action: CommittedAction
    ) -> str:
        direction = action.movement_target or ""
        if not direction and action.target_ids:
            direction = action.target_ids[0]
        if not direction:
            return f"{character.name} stays put."

        dest_scene_id = scene.exits.get(direction)
        if dest_scene_id is None:
            return f"{character.name} cannot go {direction}."

        dest_scene = self.scenes.get(dest_scene_id)
        if dest_scene is None:
            return f"{character.name} cannot go {direction} — unknown area."

        result = self.membership_engine.transfer_character(scene, dest_scene, character)
        if result.success:
            self.scenes[scene.scene_id] = scene
            self.scenes[dest_scene_id] = result.scene
            character.scene_id = dest_scene_id
            return f"{character.name} moves {direction} to {dest_scene.name}."
        return f"{character.name} cannot move {direction}."

    def _apply_inspect(
        self, character: Character, scene: Scene, action: CommittedAction
    ) -> str:
        target = action.public_text or "surroundings"
        return f"{character.name} inspects {target}."

    def _apply_search(
        self, character: Character, scene: Scene, action: CommittedAction
    ) -> str:
        return f"{character.name} searches the area."

    def _apply_attack(
        self, character: Character, scene: Scene, action: CommittedAction
    ) -> str:
        if action.target_ids:
            target_id = action.target_ids[0]
            # Check if target is a monster group
            mg = self.monster_groups.get(target_id)
            if mg:
                return f"{character.name} attacks the {mg.unit_type}!"
            # Check if target is an NPC
            npc = self.npcs.get(target_id)
            if npc:
                return f"{character.name} attacks {npc.name}!"
        return f"{character.name} attacks!"

    def _apply_social(
        self, character: Character, scene: Scene, action: CommittedAction
    ) -> str:
        action_name = action.declared_action_type.value
        if action.target_ids:
            npc = self.npcs.get(action.target_ids[0])
            if npc:
                return f"{character.name} attempts to {action_name} {npc.name}."
        return f"{character.name} attempts to {action_name}."
