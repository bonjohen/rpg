"""Response dataclasses for the Mini App REST API."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuthResult:
    valid: bool = False
    player_id: str = ""
    display_name: str = ""
    error: str = ""


@dataclass
class PlayerResponse:
    player_id: str = ""
    display_name: str = ""
    character_id: str = ""
    current_scene_id: str = ""
    is_active: bool = True


@dataclass
class CharacterResponse:
    character_id: str = ""
    name: str = ""
    stats: dict = field(default_factory=dict)
    status_effects: list[str] = field(default_factory=list)
    is_alive: bool = True
    scene_id: str = ""


@dataclass
class ItemResponse:
    item_id: str = ""
    name: str = ""
    description: str = ""
    quantity: int = 1
    properties: dict = field(default_factory=dict)


@dataclass
class InventoryResponse:
    character_id: str = ""
    items: list[ItemResponse] = field(default_factory=list)


@dataclass
class SceneResponse:
    scene_id: str = ""
    name: str = ""
    description: str = ""
    exits: dict[str, str] = field(default_factory=dict)
    players_present: list[str] = field(default_factory=list)
    npcs_present: list[str] = field(default_factory=list)


@dataclass
class RecapEntry:
    turn_number: int = 0
    scene_name: str = ""
    narration: str = ""
    committed_at: str = ""


@dataclass
class RecapResponse:
    campaign_id: str = ""
    entries: list[RecapEntry] = field(default_factory=list)


# -----------------------------------------------------------------------
# Phase 18: Scene context, action builder, inbox, channels, quests, map
# -----------------------------------------------------------------------


@dataclass
class ExitInfo:
    direction: str = ""
    target_scene_name: str = ""
    is_locked: bool = False


@dataclass
class TargetInfo:
    target_id: str = ""
    name: str = ""
    target_type: str = ""  # "npc" | "monster_group" | "player"


@dataclass
class ObjectInfo:
    object_id: str = ""
    name: str = ""
    state: str = ""


@dataclass
class SceneContextResponse:
    scene_id: str = ""
    scene_name: str = ""
    description: str = ""
    exits: list[ExitInfo] = field(default_factory=list)
    targets: list[TargetInfo] = field(default_factory=list)
    objects: list[ObjectInfo] = field(default_factory=list)
    inventory_items: list[ItemResponse] = field(default_factory=list)
    active_turn_window_id: str = ""


@dataclass
class ActionSubmitResponse:
    accepted: bool = False
    action_id: str = ""
    rejection_reason: str = ""


@dataclass
class DraftResponse:
    player_id: str = ""
    turn_window_id: str = ""
    action_type: str = ""
    target_id: str = ""
    public_text: str = ""
    private_ref_text: str = ""
    has_draft: bool = False


@dataclass
class InboxMessage:
    fact_id: str = ""
    fact_type: str = ""
    payload: str = ""
    scene_id: str = ""
    scene_name: str = ""
    revealed_at: str = ""
    is_read: bool = False


@dataclass
class InboxResponse:
    player_id: str = ""
    messages: list[InboxMessage] = field(default_factory=list)
    unread_count: int = 0


@dataclass
class ChannelInfo:
    channel_id: str = ""
    label: str = ""
    members: list[str] = field(default_factory=list)
    message_count: int = 0
    is_open: bool = True


@dataclass
class ChannelListResponse:
    channels: list[ChannelInfo] = field(default_factory=list)


@dataclass
class ChannelMessage:
    sender_name: str = ""
    text: str = ""
    sent_at: str = ""


@dataclass
class ChannelMessagesResponse:
    channel_id: str = ""
    messages: list[ChannelMessage] = field(default_factory=list)


@dataclass
class CreateChannelResponse:
    success: bool = False
    channel_id: str = ""
    rejection_reason: str = ""


@dataclass
class SendMessageResponse:
    success: bool = False
    error: str = ""


@dataclass
class LeaveChannelResponse:
    success: bool = False
    error: str = ""


@dataclass
class QuestInfo:
    quest_id: str = ""
    title: str = ""
    description: str = ""
    status: str = ""
    objectives: list[str] = field(default_factory=list)
    player_progress: dict[str, str] = field(default_factory=dict)


@dataclass
class QuestListResponse:
    quests: list[QuestInfo] = field(default_factory=list)


@dataclass
class ClueInfo:
    fact_id: str = ""
    payload: str = ""
    scene_name: str = ""
    discovered_at: str = ""


@dataclass
class ClueListResponse:
    clues: list[ClueInfo] = field(default_factory=list)


@dataclass
class MapNode:
    scene_id: str = ""
    name: str = ""
    discovered: bool = False


@dataclass
class MapEdge:
    from_scene_id: str = ""
    to_scene_id: str = ""
    direction: str = ""
    discovered: bool = False


@dataclass
class MapResponse:
    nodes: list[MapNode] = field(default_factory=list)
    edges: list[MapEdge] = field(default_factory=list)
    current_scene_id: str = ""
