"""Fixture builders for core domain entities.

Each builder returns a fully-populated domain entity with sensible defaults.
Override any field by passing kwargs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
    AwarenessState,
    BehaviorMode,
    KnowledgeFactType,
    PuzzleStatus,
    QuestStatus,
    ReadyState,
    SceneState,
    ScopeType,
    TurnWindowState,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for SQLite


def _uuid() -> str:
    return str(uuid.uuid4())


def make_campaign(**kwargs) -> Campaign:
    return Campaign(
        campaign_id=kwargs.get("campaign_id", _uuid()),
        name=kwargs.get("name", "Test Campaign"),
        telegram_group_id=kwargs.get("telegram_group_id", 1001),
        main_topic_id=kwargs.get("main_topic_id", None),
        created_at=kwargs.get("created_at", _now()),
        is_active=kwargs.get("is_active", True),
        description=kwargs.get("description", ""),
        gm_telegram_user_id=kwargs.get("gm_telegram_user_id", None),
    )


def make_player(campaign_id: str | None = None, **kwargs) -> Player:
    return Player(
        player_id=kwargs.get("player_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        telegram_user_id=kwargs.get("telegram_user_id", 100001),
        telegram_username=kwargs.get("telegram_username", "testuser"),
        display_name=kwargs.get("display_name", "Test Player"),
        joined_at=kwargs.get("joined_at", _now()),
        has_dm_open=kwargs.get("has_dm_open", False),
        is_active=kwargs.get("is_active", True),
    )


def make_character(
    player_id: str | None = None, campaign_id: str | None = None, **kwargs
) -> Character:
    return Character(
        character_id=kwargs.get("character_id", _uuid()),
        player_id=player_id or kwargs.get("player_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        name=kwargs.get("name", "Test Character"),
        created_at=kwargs.get("created_at", _now()),
        stats=kwargs.get("stats", {}),
        scene_id=kwargs.get("scene_id", None),
        status_effects=kwargs.get("status_effects", []),
        is_alive=kwargs.get("is_alive", True),
        timeout_fallback_action=kwargs.get("timeout_fallback_action", "hold"),
    )


def make_scene(campaign_id: str | None = None, **kwargs) -> Scene:
    return Scene(
        scene_id=kwargs.get("scene_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        name=kwargs.get("name", "Test Scene"),
        description=kwargs.get("description", "A nondescript room."),
        created_at=kwargs.get("created_at", _now()),
        state=kwargs.get("state", SceneState.idle),
        player_ids=kwargs.get("player_ids", []),
        character_ids=kwargs.get("character_ids", []),
        npc_ids=kwargs.get("npc_ids", []),
        monster_group_ids=kwargs.get("monster_group_ids", []),
        item_ids=kwargs.get("item_ids", []),
        active_turn_window_id=kwargs.get("active_turn_window_id", None),
        exits=kwargs.get("exits", {}),
        hidden_description=kwargs.get("hidden_description", ""),
    )


def make_conversation_scope(
    campaign_id: str | None = None, **kwargs
) -> ConversationScope:
    return ConversationScope(
        scope_id=kwargs.get("scope_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scope_type=kwargs.get("scope_type", ScopeType.public),
        player_id=kwargs.get("player_id", None),
        side_channel_id=kwargs.get("side_channel_id", None),
    )


def make_side_channel(
    campaign_id: str | None = None, created_by_player_id: str | None = None, **kwargs
) -> SideChannel:
    return SideChannel(
        side_channel_id=kwargs.get("side_channel_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        created_at=kwargs.get("created_at", _now()),
        created_by_player_id=created_by_player_id
        or kwargs.get("created_by_player_id", _uuid()),
        member_player_ids=kwargs.get("member_player_ids", []),
        is_open=kwargs.get("is_open", True),
        label=kwargs.get("label", ""),
    )


def make_turn_window(
    campaign_id: str | None = None, scene_id: str | None = None, **kwargs
) -> TurnWindow:
    from datetime import timedelta

    now = _now()
    return TurnWindow(
        turn_window_id=kwargs.get("turn_window_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scene_id=scene_id or kwargs.get("scene_id", _uuid()),
        public_scope_id=kwargs.get("public_scope_id", _uuid()),
        opened_at=kwargs.get("opened_at", now),
        expires_at=kwargs.get("expires_at", now + timedelta(seconds=90)),
        state=kwargs.get("state", TurnWindowState.open),
        locked_at=kwargs.get("locked_at", None),
        resolved_at=kwargs.get("resolved_at", None),
        committed_at=kwargs.get("committed_at", None),
        committed_action_ids=kwargs.get("committed_action_ids", []),
        control_message_id=kwargs.get("control_message_id", None),
        timeout_policy=kwargs.get("timeout_policy", "hold"),
        turn_number=kwargs.get("turn_number", 1),
    )


def make_committed_action(
    turn_window_id: str | None = None,
    player_id: str | None = None,
    character_id: str | None = None,
    **kwargs,
) -> CommittedAction:
    return CommittedAction(
        action_id=kwargs.get("action_id", _uuid()),
        turn_window_id=turn_window_id or kwargs.get("turn_window_id", _uuid()),
        player_id=player_id or kwargs.get("player_id", _uuid()),
        character_id=character_id or kwargs.get("character_id", _uuid()),
        scope_id=kwargs.get("scope_id", _uuid()),
        declared_action_type=kwargs.get("declared_action_type", ActionType.move),
        public_text=kwargs.get("public_text", "I move north."),
        private_ref_text=kwargs.get("private_ref_text", ""),
        target_ids=kwargs.get("target_ids", []),
        movement_target=kwargs.get("movement_target", None),
        item_ids=kwargs.get("item_ids", []),
        ability_ids=kwargs.get("ability_ids", []),
        ready_state=kwargs.get("ready_state", ReadyState.not_ready),
        submitted_at=kwargs.get("submitted_at", _now()),
        state=kwargs.get("state", ActionState.draft),
    )


def make_turn_log_entry(
    campaign_id: str | None = None,
    scene_id: str | None = None,
    turn_window_id: str | None = None,
    **kwargs,
) -> TurnLogEntry:
    return TurnLogEntry(
        log_entry_id=kwargs.get("log_entry_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scene_id=scene_id or kwargs.get("scene_id", _uuid()),
        turn_window_id=turn_window_id or kwargs.get("turn_window_id", _uuid()),
        turn_number=kwargs.get("turn_number", 1),
        committed_at=kwargs.get("committed_at", _now()),
        action_ids=kwargs.get("action_ids", []),
        narration=kwargs.get("narration", "The party advances."),
        state_snapshot=kwargs.get("state_snapshot", {}),
    )


def make_npc(campaign_id: str | None = None, **kwargs) -> NPC:
    return NPC(
        npc_id=kwargs.get("npc_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        name=kwargs.get("name", "Innkeeper"),
        created_at=kwargs.get("created_at", _now()),
        scene_id=kwargs.get("scene_id", None),
        health_state=kwargs.get("health_state", "healthy"),
        inventory_item_ids=kwargs.get("inventory_item_ids", []),
        faction_id=kwargs.get("faction_id", None),
        status_effects=kwargs.get("status_effects", []),
        is_visible=kwargs.get("is_visible", True),
        stance_to_party=kwargs.get("stance_to_party", "neutral"),
        trust_by_player=kwargs.get("trust_by_player", {}),
        goal_tags=kwargs.get("goal_tags", []),
        fear_tags=kwargs.get("fear_tags", []),
        personality_tags=kwargs.get("personality_tags", []),
        memory_tags=kwargs.get("memory_tags", []),
        knowledge_fact_ids=kwargs.get("knowledge_fact_ids", []),
        current_behavior_mode=kwargs.get("current_behavior_mode", BehaviorMode.idle),
    )


def make_monster_group(
    campaign_id: str | None = None, scene_id: str | None = None, **kwargs
) -> MonsterGroup:
    return MonsterGroup(
        monster_group_id=kwargs.get("monster_group_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scene_id=scene_id or kwargs.get("scene_id", _uuid()),
        unit_type=kwargs.get("unit_type", "goblin"),
        count=kwargs.get("count", 3),
        created_at=kwargs.get("created_at", _now()),
        behavior_mode=kwargs.get("behavior_mode", BehaviorMode.patrol),
        awareness_state=kwargs.get("awareness_state", AwarenessState.unaware),
        morale_state=kwargs.get("morale_state", "steady"),
        threat_table=kwargs.get("threat_table", {}),
        formation_state=kwargs.get("formation_state", "grouped"),
        territory_id=kwargs.get("territory_id", None),
        special_rules=kwargs.get("special_rules", []),
        health_state=kwargs.get("health_state", "healthy"),
        is_visible=kwargs.get("is_visible", False),
    )


def make_inventory_item(campaign_id: str | None = None, **kwargs) -> InventoryItem:
    return InventoryItem(
        item_id=kwargs.get("item_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        item_type=kwargs.get("item_type", "sword"),
        name=kwargs.get("name", "Iron Sword"),
        created_at=kwargs.get("created_at", _now()),
        owner_character_id=kwargs.get("owner_character_id", None),
        owner_scene_id=kwargs.get("owner_scene_id", None),
        quantity=kwargs.get("quantity", 1),
        properties=kwargs.get("properties", {}),
        is_hidden=kwargs.get("is_hidden", False),
    )


def make_quest_state(campaign_id: str | None = None, **kwargs) -> QuestState:
    return QuestState(
        quest_state_id=kwargs.get("quest_state_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        quest_id=kwargs.get("quest_id", "starter_quest"),
        status=kwargs.get("status", QuestStatus.inactive),
        started_at=kwargs.get("started_at", None),
        completed_at=kwargs.get("completed_at", None),
        player_progress=kwargs.get("player_progress", {}),
        flags=kwargs.get("flags", {}),
    )


def make_puzzle_state(
    campaign_id: str | None = None, scene_id: str | None = None, **kwargs
) -> PuzzleState:
    return PuzzleState(
        puzzle_state_id=kwargs.get("puzzle_state_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scene_id=scene_id or kwargs.get("scene_id", _uuid()),
        puzzle_id=kwargs.get("puzzle_id", "lock_puzzle"),
        status=kwargs.get("status", PuzzleStatus.unsolved),
        interacting_player_ids=kwargs.get("interacting_player_ids", []),
        state_slots=kwargs.get("state_slots", {}),
        attempts=kwargs.get("attempts", 0),
        solved_at=kwargs.get("solved_at", None),
    )


def make_knowledge_fact(
    campaign_id: str | None = None,
    scene_id: str | None = None,
    owner_scope_id: str | None = None,
    **kwargs,
) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=kwargs.get("fact_id", _uuid()),
        campaign_id=campaign_id or kwargs.get("campaign_id", _uuid()),
        scene_id=scene_id or kwargs.get("scene_id", _uuid()),
        owner_scope_id=owner_scope_id or kwargs.get("owner_scope_id", _uuid()),
        fact_type=kwargs.get("fact_type", KnowledgeFactType.clue),
        payload=kwargs.get("payload", "There is a draft from behind the west wall."),
        revealed_at=kwargs.get("revealed_at", _now()),
        source_event_id=kwargs.get("source_event_id", None),
    )
