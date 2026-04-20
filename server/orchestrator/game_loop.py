"""Top-level coordinator that wires bot gateway, turn engine, model adapters,
scope engine, timer, and all game loop subsystems into a single runnable loop.
"""

from __future__ import annotations

import asyncio
import hashlib
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
from server.reliability.turn_recovery import TurnRecoveryEngine
from server.scene.membership import SceneMembershipEngine
from server.domain.helpers import new_id, utc_now
from server.scope.engine import ScopeEngine
from server.storage.repository import (
    CampaignRepo,
    CharacterRepo,
    CommittedActionRepo,
    ConversationScopeRepo,
    InventoryItemRepo,
    KnowledgeFactRepo,
    MonsterGroupRepo,
    NPCRepo,
    PlayerRepo,
    PuzzleStateRepo,
    QuestStateRepo,
    SceneRepo,
    TurnLogRepo,
    TurnWindowRepo,
)
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

    All entity and turn-lifecycle state is persisted via the repository layer.
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

        # Campaign ID (full entity is loaded from the repo when needed)
        self.campaign_id: str | None = None

        # Triggers loaded from scenario (not persisted)
        self.triggers: list = []

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
        self.turn_recovery_engine = TurnRecoveryEngine()

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
    # Startup / recovery
    # ------------------------------------------------------------------

    def startup(self) -> list[str]:
        """Initialise database tables and recover state from prior runs.

        Creates all ORM tables (idempotent), loads active campaigns,
        reconstructs timers for open turn windows, and recovers stuck turns.

        Returns a list of human-readable recovery notes (empty if nothing
        needed recovery).
        """
        from server.storage.db import create_all_tables

        if self.session_factory is None:
            raise RuntimeError("No session_factory configured on GameOrchestrator")

        # Ensure tables exist
        engine = (
            self.session_factory.kw.get("bind") or self.session_factory().get_bind()
        )
        create_all_tables(engine)

        notes: list[str] = []

        with self._session_scope() as session:
            campaigns = CampaignRepo(session).list_active()

        if not campaigns:
            return notes

        # For now, single-campaign: pick the first active campaign.
        # Multi-campaign support is structural — the orchestrator holds one
        # campaign_id; callers route by campaign via the bot registry.
        campaign = campaigns[0]
        self.campaign_id = campaign.campaign_id

        # Register campaign→chat mapping in bot registry
        if campaign.telegram_group_id:
            self.bot_registry.register_campaign(
                campaign.telegram_group_id, campaign.campaign_id
            )

        # Reconstruct timers for open turn windows
        with self._session_scope() as session:
            open_tws = TurnWindowRepo(session).list_open()

        now = utc_now()
        for tw in open_tws:
            if tw.campaign_id != self.campaign_id:
                continue
            if tw.expires_at is not None and tw.expires_at > now:
                remaining = int((tw.expires_at - now).total_seconds())
                timer = self.timer_controller.create_timer(
                    tw.turn_window_id, tw.campaign_id, remaining
                )
                timer = self.timer_controller.start(timer, now)
                self.timers[timer.timer_id] = timer
                notes.append(
                    f"Reconstructed timer for TurnWindow {tw.turn_window_id} "
                    f"({remaining}s remaining)"
                )

        # Recover stuck turns
        with self._session_scope() as session:
            all_tws = TurnWindowRepo(session).list_for_campaign(self.campaign_id)

        stuck = self.turn_recovery_engine.find_stuck_turns(all_tws)
        for tw in stuck:
            scene = self.get_scene(tw.scene_id)
            if scene is None:
                continue
            players = self.get_scene_players(tw.scene_id)
            actions = self.get_committed_actions_for_window(tw.turn_window_id)
            result = self.turn_recovery_engine.recover(
                turn_window=tw,
                scene=scene,
                players=players,
                committed_actions=actions,
            )
            if result.success:
                # Persist the recovered turn window state
                with self._session_scope() as session:
                    TurnWindowRepo(session).save(result.turn_window)
                notes.append(
                    f"Recovered stuck TurnWindow {tw.turn_window_id} "
                    f"(action={result.recovery_action})"
                )

        return notes

    # ------------------------------------------------------------------
    # Scenario loading
    # ------------------------------------------------------------------

    def load_scenario(
        self,
        yaml_path: str,
        campaign_name: str = "Playtest",
        telegram_group_id: int = 0,
    ) -> bool:
        """Load a scenario from YAML, persist all entities via repos."""
        result = self.scenario_loader.load_from_yaml(yaml_path)
        if not result.success:
            return False

        campaign_id = result.campaign_id
        campaign = Campaign(
            campaign_id=campaign_id,
            name=campaign_name,
            telegram_group_id=telegram_group_id,
            main_topic_id=None,
            created_at=utc_now(),
        )

        with self._session_scope() as session:
            CampaignRepo(session).save(campaign)
            for scene in result.scenes:
                SceneRepo(session).save(scene)
            for npc in result.npcs:
                NPCRepo(session).save(npc)
            for mg in result.monster_groups:
                MonsterGroupRepo(session).save(mg)
            for item in result.items:
                InventoryItemRepo(session).save(item)
            for puzzle in result.puzzles:
                PuzzleStateRepo(session).save(puzzle)
            for quest in result.quests:
                QuestStateRepo(session).save(quest)
            for fact in result.knowledge_facts:
                KnowledgeFactRepo(session).save(fact)
            for scope in result.scopes:
                ConversationScopeRepo(session).save(scope)

        self.campaign_id = campaign_id
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
        if self.campaign_id is None:
            raise RuntimeError("No campaign loaded")

        campaign_id = self.campaign_id
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

        # Create private-referee scope for this player
        private_scope = ConversationScope(
            scope_id=new_id(),
            campaign_id=campaign_id,
            scope_type=ScopeType.private_referee,
            player_id=player_id,
        )

        with self._session_scope() as session:
            PlayerRepo(session).save(player)
            CharacterRepo(session).save(character)
            ConversationScopeRepo(session).save(private_scope)

            # Add to scene membership
            if starting_scene_id:
                scene = SceneRepo(session).get(starting_scene_id)
                if scene is not None:
                    result = self.membership_engine.add_character(scene, character)
                    if result.success:
                        SceneRepo(session).save(result.scene)

        return player, character

    def _find_starting_scene_id(self) -> str | None:
        """Find the starting scene — first scene for the campaign."""
        if self.campaign_id is None:
            return None
        with self._session_scope() as session:
            scenes = SceneRepo(session).list_for_campaign(self.campaign_id)
        if scenes:
            return scenes[0].scene_id
        return None

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def open_turn(self, scene_id: str, duration_seconds: int = 90) -> TurnWindow | None:
        """Create a new TurnWindow for a scene and persist it."""
        if self.campaign_id is None:
            return None

        with self._session_scope() as session:
            scene = SceneRepo(session).get(scene_id)
            if scene is None:
                return None

            # Find or create public scope for this scene
            public_scope_id = self._get_or_create_public_scope_in_session(
                session, scene_id
            )

            # Determine turn number from persisted log
            turn_number = TurnLogRepo(session).count_for_scene(scene_id) + 1

            now = utc_now()
            tw = TurnWindow(
                turn_window_id=new_id(),
                campaign_id=self.campaign_id,
                scene_id=scene_id,
                public_scope_id=public_scope_id,
                opened_at=now,
                expires_at=datetime.fromtimestamp(
                    now.timestamp() + duration_seconds, tz=timezone.utc
                ),
                state=TurnWindowState.open,
                turn_number=turn_number,
            )
            TurnWindowRepo(session).save(tw)

            # Update scene
            scene.active_turn_window_id = tw.turn_window_id
            scene.state = SceneState.awaiting_actions
            SceneRepo(session).save(scene)

        # Create timer
        timer = self.timer_controller.create_timer(
            tw.turn_window_id, self.campaign_id, duration_seconds
        )
        timer = self.timer_controller.start(timer, utc_now())
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

        with self._session_scope() as session:
            scene = SceneRepo(session).get(character.scene_id)
            if scene is None or scene.active_turn_window_id is None:
                return None

            tw = TurnWindowRepo(session).get(scene.active_turn_window_id)
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

            # Get existing actions for this turn from DB
            existing = CommittedActionRepo(session).list_for_window(tw.turn_window_id)
            result = self.turn_engine.submit_action(tw, action, existing)
            if not result.accepted:
                return None

            CommittedActionRepo(session).save(action)

            # Check if all players ready
            expected_player_ids = self._get_scene_player_ids(scene)
            all_actions = existing + [action]
            updated_tw = self.turn_engine.check_all_ready(
                tw, all_actions, expected_player_ids
            )
            TurnWindowRepo(session).save(updated_tw)

        return action

    def resolve_turn(self, turn_window_id: str) -> TurnLogEntry | None:
        """Lock, resolve actions, generate narration, and commit a turn.

        Uses the split-session pattern:
        - Session 1: load TurnWindow (with version), actions, scene, characters,
          NPCs, monster groups, destination scenes into a working set.
        - Compute: engine logic + narration on the working set (no session).
        - Session 2: version-checked commit of TurnWindow, save all mutated
          entities, append TurnLogEntry.
        """
        from server.storage.errors import StaleStateError

        # --- Session 1: Load working set ---
        with self._session_scope() as session:
            tw = TurnWindowRepo(session).get(turn_window_id)
            if tw is None:
                return None
            tw_version = tw.version

            scene = SceneRepo(session).get(tw.scene_id)
            if scene is None:
                return None

            actions = CommittedActionRepo(session).list_for_window(turn_window_id)

            # Characters in scene
            chars = CharacterRepo(session).list_for_scene(scene.scene_id)
            chars_by_id: dict[str, Character] = {c.character_id: c for c in chars}
            expected_player_ids = [c.player_id for c in chars if c.is_alive]
            chars_by_player = {c.player_id: c.character_id for c in chars if c.is_alive}

            # NPCs and monster groups for narration
            npcs = NPCRepo(session).list_for_scene(scene.scene_id)
            npcs_by_id: dict[str, NPC] = {n.npc_id: n for n in npcs}
            mgs = MonsterGroupRepo(session).list_for_scene(scene.scene_id)
            mgs_by_id: dict[str, MonsterGroup] = {m.monster_group_id: m for m in mgs}

            # Destination scenes for movement
            scenes_ws: dict[str, Scene] = {scene.scene_id: scene}
            for dest_id in scene.exits.values():
                dest = SceneRepo(session).get(dest_id)
                if dest:
                    scenes_ws[dest_id] = dest

        # --- Compute phase (no session) ---

        # Synthesize fallback actions for missing players
        submitted_players = {a.player_id for a in actions}
        timeout_players = [
            pid for pid in expected_player_ids if pid not in submitted_players
        ]
        for pid in timeout_players:
            char_id = chars_by_player.get(pid)
            char = chars_by_id.get(char_id) if char_id else None
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
            actions.append(fallback)

        # Lock
        if tw.state in (TurnWindowState.open, TurnWindowState.all_ready):
            lock_result = self.turn_engine.lock_window(tw)
            if not lock_result.locked:
                return None
            tw = lock_result.window

        # Resolve
        resolve_result = self.turn_engine.resolve_window(
            tw, actions, chars_by_player, timeout_players or None
        )
        if not resolve_result.resolved:
            return None
        tw = resolve_result.window

        # Apply action effects and collect narration fragments
        narration_parts = [f"In {scene.name}:"]
        for action in resolve_result.ordered_actions:
            char = chars_by_id.get(action.character_id)
            char_name = char.name if char else "Unknown"
            if action.is_timeout_fallback:
                narration_parts.append(f"{char_name} hesitates, unsure what to do.")
            else:
                effect_text = self._apply_action_effects_ws(
                    action, scene, chars_by_id, scenes_ws, npcs_by_id, mgs_by_id
                )
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

        # Commit via engine
        commit_result = self.turn_engine.commit_window(
            tw, resolve_result.ordered_actions, narration, state_snapshot
        )
        if not commit_result.committed:
            return None

        tw = commit_result.window
        log_entry = commit_result.log_entry

        # --- Session 2: Version-checked persist ---
        try:
            with self._session_scope() as session:
                TurnWindowRepo(session).save_with_version_check(tw, tw_version)

                # Save all actions (including fallbacks)
                action_repo = CommittedActionRepo(session)
                for action in resolve_result.ordered_actions:
                    action_repo.save(action)

                # Append turn log entry
                if log_entry:
                    TurnLogRepo(session).append(log_entry)

                # Save mutated characters (movement may have changed scene_id)
                char_repo = CharacterRepo(session)
                for char in chars_by_id.values():
                    char_repo.save(char)

                # Save mutated scenes
                scene_repo = SceneRepo(session)
                for s in scenes_ws.values():
                    scene_repo.save(s)

                # Clean up scene state
                scene_fresh = scenes_ws.get(scene.scene_id, scene)
                scene_fresh.active_turn_window_id = None
                scene_fresh.state = SceneState.narrated
                scene_repo.save(scene_fresh)
        except StaleStateError:
            # Concurrent modification — retry once from scratch
            return self.resolve_turn(turn_window_id)

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
        idem_key = f"msg:{player_id}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
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
    # Query helpers (public API)
    # ------------------------------------------------------------------

    def get_campaign(self) -> Campaign | None:
        """Load the active campaign from the database."""
        if self.campaign_id is None:
            return None
        with self._session_scope() as session:
            return CampaignRepo(session).get(self.campaign_id)

    def get_scene(self, scene_id: str) -> Scene | None:
        """Load a scene from the database."""
        with self._session_scope() as session:
            return SceneRepo(session).get(scene_id)

    def get_scenes(self) -> list[Scene]:
        """Load all scenes for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return SceneRepo(session).list_for_campaign(self.campaign_id)

    def get_player(self, player_id: str) -> Player | None:
        """Load a player from the database."""
        with self._session_scope() as session:
            return PlayerRepo(session).get(player_id)

    def get_players(self) -> list[Player]:
        """Load all players for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return PlayerRepo(session).list_for_campaign(self.campaign_id)

    def get_player_character(self, player_id: str) -> Character | None:
        """Load a player's character from the database."""
        with self._session_scope() as session:
            return CharacterRepo(session).get_for_player(player_id)

    def get_characters(self) -> list[Character]:
        """Load all characters for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return CharacterRepo(session).list_for_campaign(self.campaign_id)

    def get_player_scene(self, player_id: str) -> Scene | None:
        """Look up which scene a player's character is in."""
        char = self.get_player_character(player_id)
        if char is None or char.scene_id is None:
            return None
        return self.get_scene(char.scene_id)

    def get_scene_players(self, scene_id: str) -> list[Player]:
        """Return all players whose characters are in this scene."""
        with self._session_scope() as session:
            scene = SceneRepo(session).get(scene_id)
            if scene is None:
                return []
            chars = CharacterRepo(session).list_for_scene(scene_id)
            player_ids = [c.player_id for c in chars if c.is_alive]
            return [
                p
                for pid in player_ids
                if (p := PlayerRepo(session).get(pid)) is not None
            ]

    def get_npcs(self) -> list[NPC]:
        """Load all NPCs for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return NPCRepo(session).list_for_campaign(self.campaign_id)

    def get_npc(self, npc_id: str) -> NPC | None:
        """Load an NPC from the database."""
        with self._session_scope() as session:
            return NPCRepo(session).get(npc_id)

    def get_monster_groups(self) -> list[MonsterGroup]:
        """Load all monster groups for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return MonsterGroupRepo(session).list_for_campaign(self.campaign_id)

    def get_monster_group(self, mg_id: str) -> MonsterGroup | None:
        """Load a monster group from the database."""
        with self._session_scope() as session:
            return MonsterGroupRepo(session).get(mg_id)

    def get_items(self) -> list[InventoryItem]:
        """Load all items for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return InventoryItemRepo(session).list_for_campaign(self.campaign_id)

    def get_puzzles(self) -> list[PuzzleState]:
        """Load all puzzles for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return PuzzleStateRepo(session).list_for_campaign(self.campaign_id)

    def get_quests(self) -> list[QuestState]:
        """Load all quests for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return QuestStateRepo(session).list_for_campaign(self.campaign_id)

    def get_scopes(self) -> list[ConversationScope]:
        """Load all scopes for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return ConversationScopeRepo(session).list_for_campaign(self.campaign_id)

    def get_knowledge_facts(self) -> list[KnowledgeFact]:
        """Load all knowledge facts for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return KnowledgeFactRepo(session).list_for_campaign(self.campaign_id)

    def save_knowledge_fact(self, fact: KnowledgeFact) -> None:
        """Persist a knowledge fact to the database."""
        with self._session_scope() as session:
            KnowledgeFactRepo(session).save(fact)

    def get_turn_window(self, turn_window_id: str) -> TurnWindow | None:
        """Load a TurnWindow from the database."""
        with self._session_scope() as session:
            return TurnWindowRepo(session).get(turn_window_id)

    def get_turn_windows(self) -> list[TurnWindow]:
        """Load all turn windows for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return TurnWindowRepo(session).list_for_campaign(self.campaign_id)

    def get_committed_actions_for_window(
        self, turn_window_id: str
    ) -> list[CommittedAction]:
        """Load all committed actions for a turn window from the database."""
        with self._session_scope() as session:
            return CommittedActionRepo(session).list_for_window(turn_window_id)

    def get_turn_log(self, limit: int = 100) -> list[TurnLogEntry]:
        """Load turn log entries for the active campaign."""
        if self.campaign_id is None:
            return []
        with self._session_scope() as session:
            return TurnLogRepo(session).list_for_campaign(self.campaign_id, limit)

    def get_turn_log_for_scene(self, scene_id: str) -> list[TurnLogEntry]:
        """Get all turn log entries for a scene, ordered by turn number."""
        with self._session_scope() as session:
            return TurnLogRepo(session).list_for_scene(scene_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_character(self, character_id: str) -> Character | None:
        """Load a character by ID from the database."""
        with self._session_scope() as session:
            return CharacterRepo(session).get(character_id)

    def _get_scene_player_ids(self, scene: Scene) -> list[str]:
        """Get player IDs for characters in a scene."""
        with self._session_scope() as session:
            chars = CharacterRepo(session).list_for_scene(scene.scene_id)
        return [c.player_id for c in chars if c.is_alive]

    def _get_private_scope_id(self, player_id: str) -> str | None:
        """Find the private-referee scope for a player."""
        if self.campaign_id is None:
            return None
        with self._session_scope() as session:
            scope = ConversationScopeRepo(session).get_private_scope_for_player(
                self.campaign_id, player_id
            )
        return scope.scope_id if scope else None

    def _get_or_create_public_scope(self, scene_id: str) -> str:
        """Get or create a public scope for the campaign."""
        with self._session_scope() as session:
            return self._get_or_create_public_scope_in_session(session, scene_id)

    def _get_or_create_public_scope_in_session(
        self, session: Session, scene_id: str
    ) -> str:
        """Get or create a per-scene public scope within an existing session."""
        campaign_id = self.campaign_id or ""
        scope = ConversationScopeRepo(session).get_public_scope_for_scene(
            campaign_id, scene_id
        )
        if scope:
            return scope.scope_id
        new_scope = ConversationScope(
            scope_id=new_id(),
            campaign_id=campaign_id,
            scope_type=ScopeType.public,
            scene_id=scene_id,
        )
        ConversationScopeRepo(session).save(new_scope)
        return new_scope.scope_id

    def _apply_action_effects_ws(
        self,
        action: CommittedAction,
        scene: Scene,
        chars_by_id: dict[str, Character],
        scenes_ws: dict[str, Scene],
        npcs_by_id: dict[str, NPC],
        mgs_by_id: dict[str, MonsterGroup],
    ) -> str:
        """Apply resolved action effects using the working set. Returns effect text.

        All entity lookups use the pre-loaded dicts. Mutations (e.g. movement)
        update the working set in place; the caller persists in Session 2.
        """
        character = chars_by_id.get(action.character_id)
        if character is None:
            return ""

        action_type = action.declared_action_type

        if action_type == ActionType.move:
            return self._apply_move_ws(character, scene, action, scenes_ws, chars_by_id)
        elif action_type == ActionType.inspect:
            target = action.public_text or "surroundings"
            return f"{character.name} inspects {target}."
        elif action_type == ActionType.search:
            return f"{character.name} searches the area."
        elif action_type == ActionType.attack:
            return self._apply_attack_ws(character, action, npcs_by_id, mgs_by_id)
        elif action_type in (
            ActionType.question,
            ActionType.persuade,
            ActionType.threaten,
            ActionType.lie,
            ActionType.bargain,
        ):
            return self._apply_social_ws(character, action, npcs_by_id)
        elif action_type in (ActionType.hold, ActionType.pass_turn):
            return f"{character.name} holds position."
        else:
            return f"{character.name} performs {action_type.value}."

    def _apply_move_ws(
        self,
        character: Character,
        scene: Scene,
        action: CommittedAction,
        scenes_ws: dict[str, Scene],
        chars_by_id: dict[str, Character],
    ) -> str:
        direction = action.movement_target or ""
        if not direction and action.target_ids:
            direction = action.target_ids[0]
        if not direction:
            return f"{character.name} stays put."

        dest_scene_id = scene.exits.get(direction)
        if dest_scene_id is None:
            return f"{character.name} cannot go {direction}."

        dest_scene = scenes_ws.get(dest_scene_id)
        if dest_scene is None:
            return f"{character.name} cannot go {direction} — unknown area."

        result = self.membership_engine.transfer_character(scene, dest_scene, character)
        if result.success:
            scenes_ws[dest_scene_id] = result.scene
            character.scene_id = dest_scene_id
            return f"{character.name} moves {direction} to {dest_scene.name}."
        return f"{character.name} cannot move {direction}."

    def _apply_attack_ws(
        self,
        character: Character,
        action: CommittedAction,
        npcs_by_id: dict[str, NPC],
        mgs_by_id: dict[str, MonsterGroup],
    ) -> str:
        if action.target_ids:
            target_id = action.target_ids[0]
            mg = mgs_by_id.get(target_id)
            if mg:
                return f"{character.name} attacks the {mg.unit_type}!"
            npc = npcs_by_id.get(target_id)
            if npc:
                return f"{character.name} attacks {npc.name}!"
        return f"{character.name} attacks!"

    def _apply_social_ws(
        self,
        character: Character,
        action: CommittedAction,
        npcs_by_id: dict[str, NPC],
    ) -> str:
        action_name = action.declared_action_type.value
        if action.target_ids:
            npc = npcs_by_id.get(action.target_ids[0])
            if npc:
                return f"{character.name} attempts to {action_name} {npc.name}."
        return f"{character.name} attempts to {action_name}."
