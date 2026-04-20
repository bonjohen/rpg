"""Repository layer: converts between domain entities and ORM rows.

Each repository handles one entity type. All public methods accept and
return pure domain dataclasses, not ORM rows.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

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
    VisibilityGrant,
)
from server.domain.enums import (
    ActionState,
    ActionType,
    AwarenessState,
    BehaviorMode,
    KnowledgeFactType,
    PuzzleStatus,
    QuestStatus,
    ReadyState,
    SceneState,
    ScopeType,
    TurnWindowState,
    ValidationStatus,
)
from server.storage.models import (
    CampaignRow,
    CharacterRow,
    CommittedActionRow,
    ConversationScopeRow,
    InventoryItemRow,
    KnowledgeFactRow,
    MonsterGroupRow,
    NPCRow,
    PlayerRow,
    PuzzleStateRow,
    QuestStateRow,
    SceneRow,
    SideChannelRow,
    TurnLogEntryRow,
    TurnWindowRow,
    VisibilityGrantRow,
)


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------


def _campaign_from_row(r: CampaignRow) -> Campaign:
    return Campaign(
        campaign_id=r.campaign_id,
        name=r.name,
        telegram_group_id=r.telegram_group_id,
        main_topic_id=r.main_topic_id,
        created_at=r.created_at,
        is_active=r.is_active,
        description=r.description,
        gm_telegram_user_id=r.gm_telegram_user_id,
    )


def _player_from_row(r: PlayerRow) -> Player:
    return Player(
        player_id=r.player_id,
        campaign_id=r.campaign_id,
        telegram_user_id=r.telegram_user_id,
        telegram_username=r.telegram_username,
        display_name=r.display_name,
        joined_at=r.joined_at,
        has_dm_open=r.has_dm_open,
        is_active=r.is_active,
    )


def _character_from_row(r: CharacterRow) -> Character:
    return Character(
        character_id=r.character_id,
        player_id=r.player_id,
        campaign_id=r.campaign_id,
        name=r.name,
        created_at=r.created_at,
        stats=r.stats or {},
        scene_id=r.scene_id,
        status_effects=r.status_effects or [],
        is_alive=r.is_alive,
        timeout_fallback_action=r.timeout_fallback_action,
    )


def _scene_from_row(r: SceneRow) -> Scene:
    return Scene(
        scene_id=r.scene_id,
        campaign_id=r.campaign_id,
        name=r.name,
        description=r.description,
        created_at=r.created_at,
        state=SceneState(r.state),
        player_ids=r.player_ids or [],
        character_ids=r.character_ids or [],
        npc_ids=r.npc_ids or [],
        monster_group_ids=r.monster_group_ids or [],
        item_ids=r.item_ids or [],
        active_turn_window_id=r.active_turn_window_id,
        exits=r.exits or {},
        hidden_description=r.hidden_description,
    )


def _scope_from_row(r: ConversationScopeRow) -> ConversationScope:
    return ConversationScope(
        scope_id=r.scope_id,
        campaign_id=r.campaign_id,
        scope_type=ScopeType(r.scope_type),
        player_id=r.player_id,
        side_channel_id=r.side_channel_id,
        scene_id=r.scene_id,
    )


def _side_channel_from_row(r: SideChannelRow) -> SideChannel:
    return SideChannel(
        side_channel_id=r.side_channel_id,
        campaign_id=r.campaign_id,
        created_at=r.created_at,
        created_by_player_id=r.created_by_player_id,
        member_player_ids=r.member_player_ids or [],
        is_open=r.is_open,
        label=r.label,
    )


def _turn_window_from_row(r: TurnWindowRow) -> TurnWindow:
    return TurnWindow(
        turn_window_id=r.turn_window_id,
        campaign_id=r.campaign_id,
        scene_id=r.scene_id,
        public_scope_id=r.public_scope_id,
        opened_at=r.opened_at,
        expires_at=r.expires_at,
        state=TurnWindowState(r.state),
        locked_at=r.locked_at,
        resolved_at=r.resolved_at,
        committed_at=r.committed_at,
        committed_action_ids=r.committed_action_ids or [],
        control_message_id=r.control_message_id,
        timeout_policy=r.timeout_policy,
        turn_number=r.turn_number,
        version=r.version,
    )


def _committed_action_from_row(r: CommittedActionRow) -> CommittedAction:
    return CommittedAction(
        action_id=r.action_id,
        turn_window_id=r.turn_window_id,
        player_id=r.player_id,
        character_id=r.character_id,
        scope_id=r.scope_id,
        declared_action_type=ActionType(r.declared_action_type),
        public_text=r.public_text,
        private_ref_text=r.private_ref_text,
        target_ids=r.target_ids or [],
        movement_target=r.movement_target,
        item_ids=r.item_ids or [],
        ability_ids=r.ability_ids or [],
        ready_state=ReadyState(r.ready_state),
        submitted_at=r.submitted_at,
        state=ActionState(r.state),
        validation_status=ValidationStatus(r.validation_status),
        rejection_reason=r.rejection_reason,
        is_timeout_fallback=r.is_timeout_fallback,
    )


def _turn_log_entry_from_row(r: TurnLogEntryRow) -> TurnLogEntry:
    return TurnLogEntry(
        log_entry_id=r.log_entry_id,
        campaign_id=r.campaign_id,
        scene_id=r.scene_id,
        turn_window_id=r.turn_window_id,
        turn_number=r.turn_number,
        committed_at=r.committed_at,
        action_ids=r.action_ids or [],
        narration=r.narration,
        state_snapshot=r.state_snapshot or {},
    )


def _npc_from_row(r: NPCRow) -> NPC:
    return NPC(
        npc_id=r.npc_id,
        campaign_id=r.campaign_id,
        name=r.name,
        created_at=r.created_at,
        scene_id=r.scene_id,
        health_state=r.health_state,
        inventory_item_ids=r.inventory_item_ids or [],
        faction_id=r.faction_id,
        status_effects=r.status_effects or [],
        is_visible=r.is_visible,
        stance_to_party=r.stance_to_party,
        trust_by_player=r.trust_by_player or {},
        goal_tags=r.goal_tags or [],
        fear_tags=r.fear_tags or [],
        personality_tags=r.personality_tags or [],
        memory_tags=r.memory_tags or [],
        knowledge_fact_ids=r.knowledge_fact_ids or [],
        current_behavior_mode=BehaviorMode(r.current_behavior_mode),
    )


def _monster_group_from_row(r: MonsterGroupRow) -> MonsterGroup:
    return MonsterGroup(
        monster_group_id=r.monster_group_id,
        campaign_id=r.campaign_id,
        scene_id=r.scene_id,
        unit_type=r.unit_type,
        count=r.count,
        created_at=r.created_at,
        behavior_mode=BehaviorMode(r.behavior_mode),
        awareness_state=AwarenessState(r.awareness_state),
        morale_state=r.morale_state,
        threat_table=r.threat_table or {},
        formation_state=r.formation_state,
        territory_id=r.territory_id,
        special_rules=r.special_rules or [],
        health_state=r.health_state,
        is_visible=r.is_visible,
    )


def _inventory_item_from_row(r: InventoryItemRow) -> InventoryItem:
    return InventoryItem(
        item_id=r.item_id,
        campaign_id=r.campaign_id,
        item_type=r.item_type,
        name=r.name,
        created_at=r.created_at,
        owner_character_id=r.owner_character_id,
        owner_scene_id=r.owner_scene_id,
        quantity=r.quantity,
        properties=r.properties or {},
        is_hidden=r.is_hidden,
    )


def _quest_state_from_row(r: QuestStateRow) -> QuestState:
    return QuestState(
        quest_state_id=r.quest_state_id,
        campaign_id=r.campaign_id,
        quest_id=r.quest_id,
        status=QuestStatus(r.status),
        started_at=r.started_at,
        completed_at=r.completed_at,
        player_progress=r.player_progress or {},
        flags=r.flags or {},
    )


def _puzzle_state_from_row(r: PuzzleStateRow) -> PuzzleState:
    return PuzzleState(
        puzzle_state_id=r.puzzle_state_id,
        campaign_id=r.campaign_id,
        scene_id=r.scene_id,
        puzzle_id=r.puzzle_id,
        status=PuzzleStatus(r.status),
        interacting_player_ids=r.interacting_player_ids or [],
        state_slots=r.state_slots or {},
        attempts=r.attempts,
        solved_at=r.solved_at,
    )


def _knowledge_fact_from_row(r: KnowledgeFactRow) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=r.fact_id,
        campaign_id=r.campaign_id,
        scene_id=r.scene_id or "",
        owner_scope_id=r.owner_scope_id,
        fact_type=KnowledgeFactType(r.fact_type),
        payload=r.payload,
        revealed_at=r.revealed_at,
        source_event_id=r.source_event_id,
    )


def _visibility_grant_from_row(r: VisibilityGrantRow) -> VisibilityGrant:
    return VisibilityGrant(
        grant_id=r.grant_id,
        fact_id=r.fact_id,
        campaign_id=r.campaign_id,
        granted_to_scope_id=r.granted_to_scope_id,
        granted_at=r.granted_at,
        granted_by_player_id=r.granted_by_player_id,
    )


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class CampaignRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, c: Campaign) -> None:
        row = self._s.get(CampaignRow, c.campaign_id)
        if row is None:
            row = CampaignRow(campaign_id=c.campaign_id)
            self._s.add(row)
        row.name = c.name
        row.telegram_group_id = c.telegram_group_id
        row.main_topic_id = c.main_topic_id
        row.created_at = c.created_at
        row.is_active = c.is_active
        row.description = c.description
        row.gm_telegram_user_id = c.gm_telegram_user_id
        self._s.flush()

    def get(self, campaign_id: str) -> Campaign | None:
        row = self._s.get(CampaignRow, campaign_id)
        return _campaign_from_row(row) if row else None

    def get_by_telegram_group(self, telegram_group_id: int) -> Campaign | None:
        row = (
            self._s.query(CampaignRow)
            .filter_by(telegram_group_id=telegram_group_id)
            .first()
        )
        return _campaign_from_row(row) if row else None

    def list_active(self) -> list[Campaign]:
        rows = self._s.query(CampaignRow).filter_by(is_active=True).all()
        return [_campaign_from_row(r) for r in rows]


class PlayerRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, p: Player) -> None:
        row = self._s.get(PlayerRow, p.player_id)
        if row is None:
            row = PlayerRow(player_id=p.player_id)
            self._s.add(row)
        row.campaign_id = p.campaign_id
        row.telegram_user_id = p.telegram_user_id
        row.telegram_username = p.telegram_username
        row.display_name = p.display_name
        row.joined_at = p.joined_at
        row.has_dm_open = p.has_dm_open
        row.is_active = p.is_active
        self._s.flush()

    def get(self, player_id: str) -> Player | None:
        row = self._s.get(PlayerRow, player_id)
        return _player_from_row(row) if row else None

    def get_by_telegram_user(
        self, campaign_id: str, telegram_user_id: int
    ) -> Player | None:
        row = (
            self._s.query(PlayerRow)
            .filter_by(campaign_id=campaign_id, telegram_user_id=telegram_user_id)
            .first()
        )
        return _player_from_row(row) if row else None

    def list_for_campaign(self, campaign_id: str) -> list[Player]:
        rows = (
            self._s.query(PlayerRow)
            .filter_by(campaign_id=campaign_id, is_active=True)
            .all()
        )
        return [_player_from_row(r) for r in rows]


class CharacterRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, c: Character) -> None:
        row = self._s.get(CharacterRow, c.character_id)
        if row is None:
            row = CharacterRow(character_id=c.character_id)
            self._s.add(row)
        row.player_id = c.player_id
        row.campaign_id = c.campaign_id
        row.name = c.name
        row.created_at = c.created_at
        row.stats = c.stats
        row.scene_id = c.scene_id
        row.status_effects = c.status_effects
        row.is_alive = c.is_alive
        row.timeout_fallback_action = c.timeout_fallback_action
        self._s.flush()

    def get(self, character_id: str) -> Character | None:
        row = self._s.get(CharacterRow, character_id)
        return _character_from_row(row) if row else None

    def get_for_player(self, player_id: str) -> Character | None:
        row = self._s.query(CharacterRow).filter_by(player_id=player_id).first()
        return _character_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[Character]:
        rows = self._s.query(CharacterRow).filter_by(scene_id=scene_id).all()
        return [_character_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[Character]:
        rows = self._s.query(CharacterRow).filter_by(campaign_id=campaign_id).all()
        return [_character_from_row(r) for r in rows]


class SceneRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, s: Scene) -> None:
        row = self._s.get(SceneRow, s.scene_id)
        if row is None:
            row = SceneRow(scene_id=s.scene_id)
            self._s.add(row)
        row.campaign_id = s.campaign_id
        row.name = s.name
        row.description = s.description
        row.created_at = s.created_at
        row.state = s.state.value
        row.player_ids = s.player_ids
        row.character_ids = s.character_ids
        row.npc_ids = s.npc_ids
        row.monster_group_ids = s.monster_group_ids
        row.item_ids = s.item_ids
        row.active_turn_window_id = s.active_turn_window_id
        row.exits = s.exits
        row.hidden_description = s.hidden_description
        self._s.flush()

    def get(self, scene_id: str) -> Scene | None:
        row = self._s.get(SceneRow, scene_id)
        return _scene_from_row(row) if row else None

    def list_for_campaign(self, campaign_id: str) -> list[Scene]:
        rows = self._s.query(SceneRow).filter_by(campaign_id=campaign_id).all()
        return [_scene_from_row(r) for r in rows]


class ConversationScopeRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, sc: ConversationScope) -> None:
        row = self._s.get(ConversationScopeRow, sc.scope_id)
        if row is None:
            row = ConversationScopeRow(scope_id=sc.scope_id)
            self._s.add(row)
        row.campaign_id = sc.campaign_id
        row.scope_type = sc.scope_type.value
        row.player_id = sc.player_id
        row.side_channel_id = sc.side_channel_id
        row.scene_id = sc.scene_id
        self._s.flush()

    def get(self, scope_id: str) -> ConversationScope | None:
        row = self._s.get(ConversationScopeRow, scope_id)
        return _scope_from_row(row) if row else None

    def get_public_scope(self, campaign_id: str) -> ConversationScope | None:
        row = (
            self._s.query(ConversationScopeRow)
            .filter_by(campaign_id=campaign_id, scope_type=ScopeType.public.value)
            .first()
        )
        return _scope_from_row(row) if row else None

    def get_public_scope_for_scene(
        self, campaign_id: str, scene_id: str
    ) -> ConversationScope | None:
        row = (
            self._s.query(ConversationScopeRow)
            .filter_by(
                campaign_id=campaign_id,
                scope_type=ScopeType.public.value,
                scene_id=scene_id,
            )
            .first()
        )
        return _scope_from_row(row) if row else None

    def list_for_campaign(self, campaign_id: str) -> list[ConversationScope]:
        rows = (
            self._s.query(ConversationScopeRow).filter_by(campaign_id=campaign_id).all()
        )
        return [_scope_from_row(r) for r in rows]

    def get_private_scope_for_player(
        self, campaign_id: str, player_id: str
    ) -> ConversationScope | None:
        row = (
            self._s.query(ConversationScopeRow)
            .filter_by(
                campaign_id=campaign_id,
                scope_type=ScopeType.private_referee.value,
                player_id=player_id,
            )
            .first()
        )
        return _scope_from_row(row) if row else None


class SideChannelRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, sc: SideChannel) -> None:
        row = self._s.get(SideChannelRow, sc.side_channel_id)
        if row is None:
            row = SideChannelRow(side_channel_id=sc.side_channel_id)
            self._s.add(row)
        row.campaign_id = sc.campaign_id
        row.created_at = sc.created_at
        row.created_by_player_id = sc.created_by_player_id
        row.member_player_ids = sc.member_player_ids
        row.is_open = sc.is_open
        row.label = sc.label
        self._s.flush()

    def get(self, side_channel_id: str) -> SideChannel | None:
        row = self._s.get(SideChannelRow, side_channel_id)
        return _side_channel_from_row(row) if row else None

    def list_for_campaign(self, campaign_id: str) -> list[SideChannel]:
        rows = self._s.query(SideChannelRow).filter_by(campaign_id=campaign_id).all()
        return [_side_channel_from_row(r) for r in rows]


class TurnWindowRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, tw: TurnWindow) -> None:
        row = self._s.get(TurnWindowRow, tw.turn_window_id)
        if row is None:
            row = TurnWindowRow(turn_window_id=tw.turn_window_id)
            self._s.add(row)
        row.campaign_id = tw.campaign_id
        row.scene_id = tw.scene_id
        row.public_scope_id = tw.public_scope_id
        row.opened_at = tw.opened_at
        row.expires_at = tw.expires_at
        row.state = tw.state.value
        row.locked_at = tw.locked_at
        row.resolved_at = tw.resolved_at
        row.committed_at = tw.committed_at
        row.committed_action_ids = tw.committed_action_ids
        row.control_message_id = tw.control_message_id
        row.timeout_policy = tw.timeout_policy
        row.turn_number = tw.turn_number
        row.version = tw.version
        self._s.flush()

    def save_with_version_check(self, tw: TurnWindow, expected_version: int) -> None:
        """Save a TurnWindow only if its version matches expected_version.

        Increments the version on success. Raises StaleStateError if the
        row has been modified by another session since it was loaded.
        """
        from server.storage.errors import StaleStateError

        count = (
            self._s.query(TurnWindowRow)
            .filter_by(turn_window_id=tw.turn_window_id, version=expected_version)
            .update(
                {
                    TurnWindowRow.campaign_id: tw.campaign_id,
                    TurnWindowRow.scene_id: tw.scene_id,
                    TurnWindowRow.public_scope_id: tw.public_scope_id,
                    TurnWindowRow.opened_at: tw.opened_at,
                    TurnWindowRow.expires_at: tw.expires_at,
                    TurnWindowRow.state: tw.state.value,
                    TurnWindowRow.locked_at: tw.locked_at,
                    TurnWindowRow.resolved_at: tw.resolved_at,
                    TurnWindowRow.committed_at: tw.committed_at,
                    TurnWindowRow.committed_action_ids: tw.committed_action_ids,
                    TurnWindowRow.control_message_id: tw.control_message_id,
                    TurnWindowRow.timeout_policy: tw.timeout_policy,
                    TurnWindowRow.turn_number: tw.turn_number,
                    TurnWindowRow.version: expected_version + 1,
                },
                synchronize_session="fetch",
            )
        )
        if count == 0:
            raise StaleStateError(
                f"TurnWindow {tw.turn_window_id} version mismatch: "
                f"expected {expected_version}"
            )
        self._s.flush()

    def get(self, turn_window_id: str) -> TurnWindow | None:
        row = self._s.get(TurnWindowRow, turn_window_id)
        return _turn_window_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[TurnWindow]:
        rows = self._s.query(TurnWindowRow).filter_by(scene_id=scene_id).all()
        return [_turn_window_from_row(r) for r in rows]

    def list_open(self) -> list[TurnWindow]:
        """Return all TurnWindows not in a terminal state."""
        terminal = {
            TurnWindowState.committed.value,
            TurnWindowState.aborted.value,
        }
        rows = (
            self._s.query(TurnWindowRow)
            .filter(TurnWindowRow.state.notin_(terminal))
            .all()
        )
        return [_turn_window_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[TurnWindow]:
        rows = self._s.query(TurnWindowRow).filter_by(campaign_id=campaign_id).all()
        return [_turn_window_from_row(r) for r in rows]


class CommittedActionRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, a: CommittedAction) -> None:
        row = self._s.get(CommittedActionRow, a.action_id)
        if row is None:
            row = CommittedActionRow(action_id=a.action_id)
            self._s.add(row)
        row.turn_window_id = a.turn_window_id
        row.player_id = a.player_id
        row.character_id = a.character_id
        row.scope_id = a.scope_id
        row.declared_action_type = a.declared_action_type.value
        row.public_text = a.public_text
        row.private_ref_text = a.private_ref_text
        row.target_ids = a.target_ids
        row.movement_target = a.movement_target
        row.item_ids = a.item_ids
        row.ability_ids = a.ability_ids
        row.ready_state = a.ready_state.value
        row.submitted_at = a.submitted_at
        row.state = a.state.value
        row.validation_status = a.validation_status.value
        row.rejection_reason = a.rejection_reason
        row.is_timeout_fallback = a.is_timeout_fallback
        self._s.flush()

    def get(self, action_id: str) -> CommittedAction | None:
        row = self._s.get(CommittedActionRow, action_id)
        return _committed_action_from_row(row) if row else None

    def get_for_player_in_window(
        self, turn_window_id: str, player_id: str
    ) -> CommittedAction | None:
        row = (
            self._s.query(CommittedActionRow)
            .filter_by(turn_window_id=turn_window_id, player_id=player_id)
            .first()
        )
        return _committed_action_from_row(row) if row else None

    def list_for_window(self, turn_window_id: str) -> list[CommittedAction]:
        rows = (
            self._s.query(CommittedActionRow)
            .filter_by(turn_window_id=turn_window_id)
            .all()
        )
        return [_committed_action_from_row(r) for r in rows]


class TurnLogRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def append(self, entry: TurnLogEntry) -> None:
        """Append a new log entry. Never updates existing entries."""
        row = TurnLogEntryRow(
            log_entry_id=entry.log_entry_id,
            campaign_id=entry.campaign_id,
            scene_id=entry.scene_id,
            turn_window_id=entry.turn_window_id,
            turn_number=entry.turn_number,
            committed_at=entry.committed_at,
            action_ids=entry.action_ids,
            narration=entry.narration,
            state_snapshot=entry.state_snapshot,
        )
        self._s.add(row)
        self._s.flush()

    def get(self, log_entry_id: str) -> TurnLogEntry | None:
        row = self._s.get(TurnLogEntryRow, log_entry_id)
        return _turn_log_entry_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[TurnLogEntry]:
        rows = (
            self._s.query(TurnLogEntryRow)
            .filter_by(scene_id=scene_id)
            .order_by(TurnLogEntryRow.turn_number)
            .all()
        )
        return [_turn_log_entry_from_row(r) for r in rows]

    def count_for_scene(self, scene_id: str) -> int:
        return self._s.query(TurnLogEntryRow).filter_by(scene_id=scene_id).count()

    def list_for_campaign(
        self, campaign_id: str, limit: int = 100
    ) -> list[TurnLogEntry]:
        rows = (
            self._s.query(TurnLogEntryRow)
            .filter_by(campaign_id=campaign_id)
            .order_by(TurnLogEntryRow.turn_number)
            .limit(limit)
            .all()
        )
        return [_turn_log_entry_from_row(r) for r in rows]


class NPCRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, npc: NPC) -> None:
        row = self._s.get(NPCRow, npc.npc_id)
        if row is None:
            row = NPCRow(npc_id=npc.npc_id)
            self._s.add(row)
        row.campaign_id = npc.campaign_id
        row.name = npc.name
        row.created_at = npc.created_at
        row.scene_id = npc.scene_id
        row.health_state = npc.health_state
        row.inventory_item_ids = npc.inventory_item_ids
        row.faction_id = npc.faction_id
        row.status_effects = npc.status_effects
        row.is_visible = npc.is_visible
        row.stance_to_party = npc.stance_to_party
        row.trust_by_player = npc.trust_by_player
        row.goal_tags = npc.goal_tags
        row.fear_tags = npc.fear_tags
        row.personality_tags = npc.personality_tags
        row.memory_tags = npc.memory_tags
        row.knowledge_fact_ids = npc.knowledge_fact_ids
        row.current_behavior_mode = npc.current_behavior_mode.value
        self._s.flush()

    def get(self, npc_id: str) -> NPC | None:
        row = self._s.get(NPCRow, npc_id)
        return _npc_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[NPC]:
        rows = self._s.query(NPCRow).filter_by(scene_id=scene_id).all()
        return [_npc_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[NPC]:
        rows = self._s.query(NPCRow).filter_by(campaign_id=campaign_id).all()
        return [_npc_from_row(r) for r in rows]


class MonsterGroupRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, mg: MonsterGroup) -> None:
        row = self._s.get(MonsterGroupRow, mg.monster_group_id)
        if row is None:
            row = MonsterGroupRow(monster_group_id=mg.monster_group_id)
            self._s.add(row)
        row.campaign_id = mg.campaign_id
        row.scene_id = mg.scene_id
        row.unit_type = mg.unit_type
        row.count = mg.count
        row.created_at = mg.created_at
        row.behavior_mode = mg.behavior_mode.value
        row.awareness_state = mg.awareness_state.value
        row.morale_state = mg.morale_state
        row.threat_table = mg.threat_table
        row.formation_state = mg.formation_state
        row.territory_id = mg.territory_id
        row.special_rules = mg.special_rules
        row.health_state = mg.health_state
        row.is_visible = mg.is_visible
        self._s.flush()

    def get(self, monster_group_id: str) -> MonsterGroup | None:
        row = self._s.get(MonsterGroupRow, monster_group_id)
        return _monster_group_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[MonsterGroup]:
        rows = self._s.query(MonsterGroupRow).filter_by(scene_id=scene_id).all()
        return [_monster_group_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[MonsterGroup]:
        rows = self._s.query(MonsterGroupRow).filter_by(campaign_id=campaign_id).all()
        return [_monster_group_from_row(r) for r in rows]


class InventoryItemRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, item: InventoryItem) -> None:
        row = self._s.get(InventoryItemRow, item.item_id)
        if row is None:
            row = InventoryItemRow(item_id=item.item_id)
            self._s.add(row)
        row.campaign_id = item.campaign_id
        row.item_type = item.item_type
        row.name = item.name
        row.created_at = item.created_at
        row.owner_character_id = item.owner_character_id
        row.owner_scene_id = item.owner_scene_id
        row.quantity = item.quantity
        row.properties = item.properties
        row.is_hidden = item.is_hidden
        self._s.flush()

    def get(self, item_id: str) -> InventoryItem | None:
        row = self._s.get(InventoryItemRow, item_id)
        return _inventory_item_from_row(row) if row else None

    def list_for_character(self, character_id: str) -> list[InventoryItem]:
        rows = (
            self._s.query(InventoryItemRow)
            .filter_by(owner_character_id=character_id)
            .all()
        )
        return [_inventory_item_from_row(r) for r in rows]

    def list_for_scene(self, scene_id: str) -> list[InventoryItem]:
        rows = self._s.query(InventoryItemRow).filter_by(owner_scene_id=scene_id).all()
        return [_inventory_item_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[InventoryItem]:
        rows = self._s.query(InventoryItemRow).filter_by(campaign_id=campaign_id).all()
        return [_inventory_item_from_row(r) for r in rows]


class QuestStateRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, qs: QuestState) -> None:
        row = self._s.get(QuestStateRow, qs.quest_state_id)
        if row is None:
            row = QuestStateRow(quest_state_id=qs.quest_state_id)
            self._s.add(row)
        row.campaign_id = qs.campaign_id
        row.quest_id = qs.quest_id
        row.status = qs.status.value
        row.started_at = qs.started_at
        row.completed_at = qs.completed_at
        row.player_progress = qs.player_progress
        row.flags = qs.flags
        self._s.flush()

    def get(self, quest_state_id: str) -> QuestState | None:
        row = self._s.get(QuestStateRow, quest_state_id)
        return _quest_state_from_row(row) if row else None

    def list_for_campaign(self, campaign_id: str) -> list[QuestState]:
        rows = self._s.query(QuestStateRow).filter_by(campaign_id=campaign_id).all()
        return [_quest_state_from_row(r) for r in rows]


class PuzzleStateRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, ps: PuzzleState) -> None:
        row = self._s.get(PuzzleStateRow, ps.puzzle_state_id)
        if row is None:
            row = PuzzleStateRow(puzzle_state_id=ps.puzzle_state_id)
            self._s.add(row)
        row.campaign_id = ps.campaign_id
        row.scene_id = ps.scene_id
        row.puzzle_id = ps.puzzle_id
        row.status = ps.status.value
        row.interacting_player_ids = ps.interacting_player_ids
        row.state_slots = ps.state_slots
        row.attempts = ps.attempts
        row.solved_at = ps.solved_at
        self._s.flush()

    def get(self, puzzle_state_id: str) -> PuzzleState | None:
        row = self._s.get(PuzzleStateRow, puzzle_state_id)
        return _puzzle_state_from_row(row) if row else None

    def list_for_scene(self, scene_id: str) -> list[PuzzleState]:
        rows = self._s.query(PuzzleStateRow).filter_by(scene_id=scene_id).all()
        return [_puzzle_state_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[PuzzleState]:
        rows = self._s.query(PuzzleStateRow).filter_by(campaign_id=campaign_id).all()
        return [_puzzle_state_from_row(r) for r in rows]


class KnowledgeFactRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, kf: KnowledgeFact) -> None:
        row = self._s.get(KnowledgeFactRow, kf.fact_id)
        if row is None:
            row = KnowledgeFactRow(fact_id=kf.fact_id)
            self._s.add(row)
        row.campaign_id = kf.campaign_id
        row.scene_id = kf.scene_id or None
        row.owner_scope_id = kf.owner_scope_id
        row.fact_type = kf.fact_type.value
        row.payload = kf.payload
        row.revealed_at = kf.revealed_at
        row.source_event_id = kf.source_event_id
        self._s.flush()

    def get(self, fact_id: str) -> KnowledgeFact | None:
        row = self._s.get(KnowledgeFactRow, fact_id)
        return _knowledge_fact_from_row(row) if row else None

    def list_for_scope(self, owner_scope_id: str) -> list[KnowledgeFact]:
        rows = (
            self._s.query(KnowledgeFactRow)
            .filter_by(owner_scope_id=owner_scope_id)
            .all()
        )
        return [_knowledge_fact_from_row(r) for r in rows]

    def list_for_scene(self, scene_id: str) -> list[KnowledgeFact]:
        rows = self._s.query(KnowledgeFactRow).filter_by(scene_id=scene_id).all()
        return [_knowledge_fact_from_row(r) for r in rows]

    def list_for_campaign(self, campaign_id: str) -> list[KnowledgeFact]:
        rows = self._s.query(KnowledgeFactRow).filter_by(campaign_id=campaign_id).all()
        return [_knowledge_fact_from_row(r) for r in rows]


class VisibilityGrantRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, vg: VisibilityGrant) -> None:
        row = self._s.get(VisibilityGrantRow, vg.grant_id)
        if row is None:
            row = VisibilityGrantRow(grant_id=vg.grant_id)
            self._s.add(row)
        row.fact_id = vg.fact_id
        row.campaign_id = vg.campaign_id
        row.granted_to_scope_id = vg.granted_to_scope_id
        row.granted_at = vg.granted_at
        row.granted_by_player_id = vg.granted_by_player_id
        self._s.flush()

    def list_for_fact(self, fact_id: str) -> list[VisibilityGrant]:
        rows = self._s.query(VisibilityGrantRow).filter_by(fact_id=fact_id).all()
        return [_visibility_grant_from_row(r) for r in rows]

    def list_for_scope(self, granted_to_scope_id: str) -> list[VisibilityGrant]:
        rows = (
            self._s.query(VisibilityGrantRow)
            .filter_by(granted_to_scope_id=granted_to_scope_id)
            .all()
        )
        return [_visibility_grant_from_row(r) for r in rows]
