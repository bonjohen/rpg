"""FastAPI route handlers for the Mini App REST API."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.api.auth import validate_init_data
from server.api.responses import (
    CharacterResponse,
    InventoryResponse,
    ItemResponse,
    PlayerResponse,
    RecapEntry,
    RecapResponse,
    SceneResponse,
)

if TYPE_CHECKING:
    from server.orchestrator.game_loop import GameOrchestrator

router = APIRouter()

# The orchestrator is injected at app creation time and stored here.
_orchestrator: GameOrchestrator | None = None


def set_orchestrator(orchestrator: GameOrchestrator) -> None:
    """Inject the orchestrator dependency for route handlers."""
    global _orchestrator  # noqa: PLW0603
    _orchestrator = orchestrator


def _orch() -> GameOrchestrator:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Game server not initialized.")
    return _orchestrator


# -----------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------


class ValidateAuthRequest(BaseModel):
    init_data: str
    bot_token: str


@router.post("/api/auth/validate")
async def validate_auth(req: ValidateAuthRequest) -> dict:
    result = validate_init_data(req.init_data, req.bot_token)
    return asdict(result)


# -----------------------------------------------------------------------
# Player
# -----------------------------------------------------------------------


@router.get("/api/player/{player_id}")
async def get_player(player_id: str) -> dict:
    orch = _orch()
    player = orch.players.get(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found.")

    # Find the player's character
    character = orch._get_player_character(player_id)
    char_id = character.character_id if character else ""
    scene_id = character.scene_id or "" if character else ""

    resp = PlayerResponse(
        player_id=player.player_id,
        display_name=player.display_name,
        character_id=char_id,
        current_scene_id=scene_id,
        is_active=player.is_active,
    )
    return asdict(resp)


# -----------------------------------------------------------------------
# Character
# -----------------------------------------------------------------------


@router.get("/api/character/{character_id}")
async def get_character(character_id: str) -> dict:
    orch = _orch()
    char = orch.characters.get(character_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    resp = CharacterResponse(
        character_id=char.character_id,
        name=char.name,
        stats=dict(char.stats),
        status_effects=list(char.status_effects),
        is_alive=char.is_alive,
        scene_id=char.scene_id or "",
    )
    return asdict(resp)


# -----------------------------------------------------------------------
# Inventory
# -----------------------------------------------------------------------


@router.get("/api/character/{character_id}/inventory")
async def get_inventory(character_id: str) -> dict:
    orch = _orch()
    char = orch.characters.get(character_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    items: list[ItemResponse] = []
    for item in orch.items.values():
        if item.owner_character_id == character_id:
            items.append(
                ItemResponse(
                    item_id=item.item_id,
                    name=item.name,
                    description=item.properties.get("description", ""),
                    quantity=item.quantity,
                    properties=dict(item.properties),
                )
            )

    resp = InventoryResponse(character_id=character_id, items=items)
    return asdict(resp)


# -----------------------------------------------------------------------
# Scene
# -----------------------------------------------------------------------


@router.get("/api/scene/{scene_id}")
async def get_scene(scene_id: str) -> dict:
    orch = _orch()
    scene = orch.scenes.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")

    # Collect player display names present in scene
    players_present: list[str] = []
    for char in orch.characters.values():
        if char.scene_id == scene_id and char.is_alive:
            player = orch.players.get(char.player_id)
            if player:
                players_present.append(player.display_name)

    # Collect NPC names present in scene
    npcs_present: list[str] = []
    for npc_id in scene.npc_ids:
        npc = orch.npcs.get(npc_id)
        if npc and npc.is_visible:
            npcs_present.append(npc.name)

    # Build exit labels: direction -> target scene name
    exit_labels: dict[str, str] = {}
    for direction, target_id in scene.exits.items():
        target = orch.scenes.get(target_id)
        exit_labels[direction] = target.name if target else target_id

    resp = SceneResponse(
        scene_id=scene.scene_id,
        name=scene.name,
        description=scene.description,  # public only — hidden_description excluded
        exits=exit_labels,
        players_present=players_present,
        npcs_present=npcs_present,
    )
    return asdict(resp)


# -----------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------


@router.get("/api/campaign/{campaign_id}/recap")
async def get_recap(
    campaign_id: str, limit: int = Query(default=10, ge=1, le=100)
) -> dict:
    orch = _orch()
    if orch.campaign is None or orch.campaign.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # Get log entries sorted by turn number descending
    entries = sorted(orch.turn_log, key=lambda e: e.turn_number, reverse=True)[:limit]

    recap_entries: list[RecapEntry] = []
    for entry in entries:
        scene = orch.scenes.get(entry.scene_id)
        scene_name = scene.name if scene else entry.scene_id
        recap_entries.append(
            RecapEntry(
                turn_number=entry.turn_number,
                scene_name=scene_name,
                narration=entry.narration,
                committed_at=entry.committed_at.isoformat()
                if entry.committed_at
                else "",
            )
        )

    resp = RecapResponse(campaign_id=campaign_id, entries=recap_entries)
    return asdict(resp)
