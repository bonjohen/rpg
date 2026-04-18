"""SQLAlchemy ORM models.

One table per domain entity. JSON columns store lists and dicts.
All timestamps are UTC. IDs are VARCHAR(36) UUIDs.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class CampaignRow(Base):
    __tablename__ = "campaigns"

    campaign_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_group_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    main_topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gm_telegram_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PlayerRow(Base):
    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    has_dm_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CharacterRow(Base):
    __tablename__ = "characters"

    character_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.player_id"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=True
    )
    status_effects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_fallback_action: Mapped[str] = mapped_column(
        String(64), nullable=False, default="hold"
    )


class ConversationScopeRow(Base):
    __tablename__ = "conversation_scopes"

    scope_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    player_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("players.player_id"), nullable=True
    )
    side_channel_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("side_channels.side_channel_id"), nullable=True
    )


class SideChannelRow(Base):
    __tablename__ = "side_channels"

    side_channel_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by_player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.player_id"), nullable=False
    )
    member_player_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class SceneRow(Base):
    __tablename__ = "scenes"

    scene_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    player_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    character_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    npc_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    monster_group_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    item_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active_turn_window_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    exits: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    hidden_description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class TurnWindowRow(Base):
    __tablename__ = "turn_windows"

    turn_window_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=False
    )
    public_scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    committed_action_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    control_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_policy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="hold"
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CommittedActionRow(Base):
    __tablename__ = "committed_actions"

    action_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    turn_window_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("turn_windows.turn_window_id"), nullable=False
    )
    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.player_id"), nullable=False
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.character_id"), nullable=False
    )
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    declared_action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    public_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    private_ref_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    movement_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ability_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ready_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_ready"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    validation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_timeout_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class TurnLogEntryRow(Base):
    __tablename__ = "turn_log_entries"

    log_entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=False
    )
    turn_window_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("turn_windows.turn_window_id"), nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    action_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    narration: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class NPCRow(Base):
    __tablename__ = "npcs"

    npc_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=True
    )
    health_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="healthy"
    )
    inventory_item_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    faction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status_effects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stance_to_party: Mapped[str] = mapped_column(
        String(32), nullable=False, default="neutral"
    )
    trust_by_player: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    goal_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fear_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    personality_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    memory_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    knowledge_fact_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_behavior_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="idle"
    )


class MonsterGroupRow(Base):
    __tablename__ = "monster_groups"

    monster_group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=False
    )
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    behavior_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="patrol"
    )
    awareness_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unaware"
    )
    morale_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="steady"
    )
    threat_table: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    formation_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="grouped"
    )
    territory_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    special_rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    health_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="healthy"
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InventoryItemRow(Base):
    __tablename__ = "inventory_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    owner_character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("characters.character_id"), nullable=True
    )
    owner_scene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class QuestStateRow(Base):
    __tablename__ = "quest_states"

    quest_state_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="inactive")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    player_progress: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class PuzzleStateRow(Base):
    __tablename__ = "puzzle_states"

    puzzle_state_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=False
    )
    puzzle_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unsolved")
    interacting_player_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    state_slots: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KnowledgeFactRow(Base):
    __tablename__ = "knowledge_facts"

    fact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.scene_id"), nullable=False
    )
    owner_scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    revealed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class VisibilityGrantRow(Base):
    __tablename__ = "visibility_grants"

    grant_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_facts.fact_id"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.campaign_id"), nullable=False
    )
    granted_to_scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    granted_by_player_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
