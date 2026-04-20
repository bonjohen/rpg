"""Pure domain entities — no ORM, no DB imports.

All IDs are strings (UUIDs). Timestamps are UTC datetimes.
Lists and dicts default to empty via field(default_factory=...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

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


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


@dataclass
class Campaign:
    """Top-level container for a game session.

    Owns one Telegram supergroup, multiple scenes, and all players.
    """

    campaign_id: str
    name: str
    telegram_group_id: int
    main_topic_id: Optional[int]  # message_thread_id for the play topic
    created_at: datetime
    is_active: bool = True
    description: str = ""
    gm_telegram_user_id: Optional[int] = None  # human GM, if any


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


@dataclass
class Player:
    """Telegram user participating in a campaign."""

    player_id: str
    campaign_id: str
    telegram_user_id: int
    telegram_username: Optional[str]
    display_name: str
    joined_at: datetime
    has_dm_open: bool = False  # True once user has /started the bot DM
    is_active: bool = True


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------


@dataclass
class Character:
    """A player's in-game character."""

    character_id: str
    player_id: str
    campaign_id: str
    name: str
    created_at: datetime
    # Core stats (game-system agnostic; stored as a JSON-serialisable dict)
    stats: dict = field(default_factory=dict)
    # Current scene membership
    scene_id: Optional[str] = None
    # Status effects applied to this character
    status_effects: list[str] = field(default_factory=list)
    is_alive: bool = True
    # Fallback action if the player times out
    timeout_fallback_action: str = "hold"


# ---------------------------------------------------------------------------
# ConversationScope
# ---------------------------------------------------------------------------


@dataclass
class ConversationScope:
    """Explicit scope record; every message and fact has one."""

    scope_id: str
    campaign_id: str
    scope_type: ScopeType
    # For private_referee: the one player this scope belongs to
    player_id: Optional[str] = None
    # For side_channel: the set of players in the channel
    side_channel_id: Optional[str] = None
    # For public scopes: the scene this scope is for (per-scene public scopes)
    scene_id: Optional[str] = None


# ---------------------------------------------------------------------------
# SideChannel
# ---------------------------------------------------------------------------


@dataclass
class SideChannel:
    """A private subset-of-players channel.

    Not backed by a separate Telegram group; delivered via DM relay.
    """

    side_channel_id: str
    campaign_id: str
    created_at: datetime
    created_by_player_id: str
    member_player_ids: list[str] = field(default_factory=list)
    is_open: bool = True
    label: str = ""  # optional human label ("heist crew")


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------


@dataclass
class Scene:
    """An active location within a campaign."""

    scene_id: str
    campaign_id: str
    name: str
    description: str  # public narrative description
    created_at: datetime
    state: SceneState = SceneState.idle
    # IDs of players/characters currently in this scene
    player_ids: list[str] = field(default_factory=list)
    character_ids: list[str] = field(default_factory=list)
    # IDs of active NPCs and monster groups
    npc_ids: list[str] = field(default_factory=list)
    monster_group_ids: list[str] = field(default_factory=list)
    # IDs of items present in the scene (not in any inventory)
    item_ids: list[str] = field(default_factory=list)
    # Currently open turn window, if any
    active_turn_window_id: Optional[str] = None
    # Scenario-defined exits: {direction: scene_id}
    exits: dict[str, str] = field(default_factory=dict)
    # Hidden (referee-only) description appended to scoped prompts
    hidden_description: str = ""


# ---------------------------------------------------------------------------
# TurnWindow
# ---------------------------------------------------------------------------


@dataclass
class TurnWindow:
    """One turn cycle within a scene."""

    turn_window_id: str
    campaign_id: str
    scene_id: str
    public_scope_id: str
    opened_at: datetime
    expires_at: datetime
    state: TurnWindowState = TurnWindowState.open
    locked_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    committed_at: Optional[datetime] = None
    # IDs of committed action packets for this window (one per player)
    committed_action_ids: list[str] = field(default_factory=list)
    # Telegram message ID of the turn-control message (for editing/updating)
    control_message_id: Optional[int] = None
    # Timeout policy label (e.g. "hold", "defend")
    timeout_policy: str = "hold"
    turn_number: int = 0
    version: int = 1


# ---------------------------------------------------------------------------
# CommittedAction
# ---------------------------------------------------------------------------


@dataclass
class CommittedAction:
    """One player's authoritative action packet for a turn.

    Only one per player per TurnWindow is canonical.
    """

    action_id: str
    turn_window_id: str
    player_id: str
    character_id: str
    scope_id: str
    declared_action_type: ActionType
    public_text: str = ""
    private_ref_text: str = ""  # visible only to referee
    target_ids: list[str] = field(default_factory=list)
    movement_target: Optional[str] = None
    item_ids: list[str] = field(default_factory=list)
    ability_ids: list[str] = field(default_factory=list)
    ready_state: ReadyState = ReadyState.not_ready
    submitted_at: Optional[datetime] = None
    state: ActionState = ActionState.draft
    validation_status: ValidationStatus = ValidationStatus.pending
    rejection_reason: str = ""
    # True if applied via timeout fallback rather than player submission
    is_timeout_fallback: bool = False


# ---------------------------------------------------------------------------
# TurnLogEntry
# ---------------------------------------------------------------------------


@dataclass
class TurnLogEntry:
    """Append-only record of a resolved turn.

    Never modified after creation.
    """

    log_entry_id: str
    campaign_id: str
    scene_id: str
    turn_window_id: str
    turn_number: int
    committed_at: datetime
    # Snapshot of all committed action IDs that were resolved
    action_ids: list[str] = field(default_factory=list)
    # Official narration produced by the gameplay model
    narration: str = ""
    # Full state snapshot at commit (for replay)
    state_snapshot: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------


@dataclass
class NPC:
    """Non-player character with hard state and durable mind.

    Hard state is code-owned. Durable mind is structured data the server
    may update based on validated model proposals.
    """

    npc_id: str
    campaign_id: str
    name: str
    created_at: datetime
    # Hard state
    scene_id: Optional[str] = None
    health_state: str = "healthy"  # "healthy", "injured", "incapacitated", "dead"
    inventory_item_ids: list[str] = field(default_factory=list)
    faction_id: Optional[str] = None
    status_effects: list[str] = field(default_factory=list)
    is_visible: bool = True  # visible to players in the scene
    # Durable mind
    stance_to_party: str = "neutral"  # "friendly", "neutral", "hostile", "fearful"
    trust_by_player: dict[str, int] = field(
        default_factory=dict
    )  # player_id → -100..100
    goal_tags: list[str] = field(default_factory=list)
    fear_tags: list[str] = field(default_factory=list)
    personality_tags: list[str] = field(default_factory=list)
    memory_tags: list[str] = field(default_factory=list)
    knowledge_fact_ids: list[str] = field(default_factory=list)
    # Tactical
    current_behavior_mode: BehaviorMode = BehaviorMode.idle


# ---------------------------------------------------------------------------
# MonsterGroup
# ---------------------------------------------------------------------------


@dataclass
class MonsterGroup:
    """A grouped tactical actor (one or more monsters treated as a unit)."""

    monster_group_id: str
    campaign_id: str
    scene_id: str
    unit_type: str  # e.g. "goblin", "skeleton_warrior"
    count: int
    created_at: datetime
    behavior_mode: BehaviorMode = BehaviorMode.patrol
    awareness_state: AwarenessState = AwarenessState.unaware
    morale_state: str = "steady"  # "steady", "shaken", "routed"
    # threat_table: player_id → threat score
    threat_table: dict[str, int] = field(default_factory=dict)
    formation_state: str = "grouped"
    territory_id: Optional[str] = None
    special_rules: list[str] = field(default_factory=list)
    health_state: str = "healthy"
    is_visible: bool = False  # hidden until spotted


# ---------------------------------------------------------------------------
# InventoryItem
# ---------------------------------------------------------------------------


@dataclass
class InventoryItem:
    """An item instance owned by a character or present in a scene."""

    item_id: str
    campaign_id: str
    item_type: str  # e.g. "sword", "potion_healing"
    name: str
    created_at: datetime
    # Owner: either a character or a scene (exactly one should be set)
    owner_character_id: Optional[str] = None
    owner_scene_id: Optional[str] = None
    quantity: int = 1
    properties: dict = field(default_factory=dict)  # game-system specific
    is_hidden: bool = False  # hidden from public scene description


# ---------------------------------------------------------------------------
# QuestState
# ---------------------------------------------------------------------------


@dataclass
class QuestState:
    """Progress tracker for a quest within a campaign."""

    quest_state_id: str
    campaign_id: str
    quest_id: str  # references scenario quest definition
    status: QuestStatus = QuestStatus.inactive
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Player-specific progress notes keyed by player_id
    player_progress: dict[str, str] = field(default_factory=dict)
    # Arbitrary key-value flags for scenario logic
    flags: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PuzzleState
# ---------------------------------------------------------------------------


@dataclass
class PuzzleState:
    """State of a puzzle within a scene."""

    puzzle_state_id: str
    campaign_id: str
    scene_id: str
    puzzle_id: str  # references scenario puzzle definition
    status: PuzzleStatus = PuzzleStatus.unsolved
    # Players who have interacted with the puzzle
    interacting_player_ids: list[str] = field(default_factory=list)
    # Arbitrary state slots for puzzle logic (e.g. {"lever_a": True})
    state_slots: dict[str, bool] = field(default_factory=dict)
    attempts: int = 0
    solved_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# KnowledgeFact
# ---------------------------------------------------------------------------


@dataclass
class KnowledgeFact:
    """A scoped fact — who knows what.

    The server creates facts; the LLM never writes facts directly.
    """

    fact_id: str
    campaign_id: str
    scene_id: str
    owner_scope_id: str  # the ConversationScope that owns this fact
    fact_type: KnowledgeFactType
    payload: str  # the fact content (text or JSON string)
    revealed_at: datetime
    source_event_id: Optional[str] = None  # e.g. the turn_window_id that revealed it


# ---------------------------------------------------------------------------
# VisibilityGrant
# ---------------------------------------------------------------------------


@dataclass
class VisibilityGrant:
    """Explicit grant of a KnowledgeFact to an additional scope.

    Used when a fact starts private then becomes shared (e.g. a player
    announces a private discovery publicly).
    """

    grant_id: str
    fact_id: str
    campaign_id: str
    granted_to_scope_id: str
    granted_at: datetime
    granted_by_player_id: Optional[str] = None
