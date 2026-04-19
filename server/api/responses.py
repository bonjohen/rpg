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
