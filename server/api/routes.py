"""FastAPI route handlers for the Mini App REST API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from server.api.auth import validate_init_data
from server.api.responses import (
    ActionSubmitResponse,
    ChannelInfo,
    ChannelListResponse,
    ChannelMessage,
    ChannelMessagesResponse,
    CharacterResponse,
    ClueInfo,
    ClueListResponse,
    CreateChannelResponse,
    DraftResponse,
    ExitInfo,
    InboxMessage,
    InboxResponse,
    InventoryResponse,
    ItemResponse,
    LeaveChannelResponse,
    MapEdge,
    MapNode,
    MapResponse,
    PlayerResponse,
    QuestInfo,
    QuestListResponse,
    RecapEntry,
    RecapResponse,
    SceneContextResponse,
    SceneResponse,
    SendMessageResponse,
    TargetInfo,
)
from server.domain.enums import ActionType, ScopeType, TurnWindowState

if TYPE_CHECKING:
    from server.orchestrator.game_loop import GameOrchestrator

router = APIRouter()

# Startup-injection pattern: the orchestrator is set once at app creation
# time via set_orchestrator() (called by create_api_app in app.py).  Route
# handlers retrieve it through _orch(), which raises 503 if the app was
# not properly initialised.  Tests create a fresh TestClient per test via
# create_api_app(), so the module-level global is overwritten each time
# without state leakage.
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
    player = orch.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found.")

    character = orch.get_player_character(player_id)
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
    char = orch._get_character(character_id)
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
    char = orch._get_character(character_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    with orch._session_scope() as session:
        from server.storage.repository import InventoryItemRepo

        db_items = InventoryItemRepo(session).list_for_character(character_id)

    items: list[ItemResponse] = [
        ItemResponse(
            item_id=item.item_id,
            name=item.name,
            description=item.properties.get("description", ""),
            quantity=item.quantity,
            properties=dict(item.properties),
        )
        for item in db_items
    ]

    resp = InventoryResponse(character_id=character_id, items=items)
    return asdict(resp)


# -----------------------------------------------------------------------
# Scene (basic)
# -----------------------------------------------------------------------


@router.get("/api/scene/{scene_id}")
async def get_scene(scene_id: str) -> dict:
    orch = _orch()
    scene = orch.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")

    # Collect player display names present in scene
    scene_players = orch.get_scene_players(scene_id)
    players_present = [p.display_name for p in scene_players]

    # Collect NPC names present in scene
    npcs_present: list[str] = []
    for npc_id in scene.npc_ids:
        npc = orch.get_npc(npc_id)
        if npc and npc.is_visible:
            npcs_present.append(npc.name)

    # Build exit labels: direction -> target scene name
    exit_labels: dict[str, str] = {}
    for direction, target_id in scene.exits.items():
        target = orch.get_scene(target_id)
        exit_labels[direction] = target.name if target else target_id

    resp = SceneResponse(
        scene_id=scene.scene_id,
        name=scene.name,
        description=scene.description,
        exits=exit_labels,
        players_present=players_present,
        npcs_present=npcs_present,
    )
    return asdict(resp)


# -----------------------------------------------------------------------
# Scene context (for action builder)
# -----------------------------------------------------------------------


@router.get("/api/scene/{scene_id}/context")
async def get_scene_context(scene_id: str) -> dict:
    orch = _orch()
    scene = orch.get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")

    # Exits — non-hidden only
    exits: list[ExitInfo] = []
    for direction, target_id in scene.exits.items():
        target = orch.get_scene(target_id)
        target_name = target.name if target else target_id
        exits.append(
            ExitInfo(
                direction=direction, target_scene_name=target_name, is_locked=False
            )
        )

    # Targets — visible NPCs and monster groups
    targets: list[TargetInfo] = []
    for npc_id in scene.npc_ids:
        npc = orch.get_npc(npc_id)
        if npc and npc.is_visible:
            targets.append(
                TargetInfo(target_id=npc_id, name=npc.name, target_type="npc")
            )
    for mg_id in scene.monster_group_ids:
        mg = orch.get_monster_group(mg_id)
        if mg and mg.is_visible:
            targets.append(
                TargetInfo(
                    target_id=mg_id, name=mg.unit_type, target_type="monster_group"
                )
            )

    # Active turn window
    tw_id = scene.active_turn_window_id or ""

    resp = SceneContextResponse(
        scene_id=scene.scene_id,
        scene_name=scene.name,
        description=scene.description,
        exits=exits,
        targets=targets,
        objects=[],
        inventory_items=[],
        active_turn_window_id=tw_id,
    )
    return asdict(resp)


# -----------------------------------------------------------------------
# Action submission
# -----------------------------------------------------------------------


class ActionSubmissionRequest(BaseModel):
    player_id: str
    turn_window_id: str
    action_type: str
    target_id: str = ""
    item_id: str = ""
    public_text: str = ""
    private_ref_text: str = ""
    movement_target: str = ""


@router.post("/api/action/submit")
async def submit_action(req: ActionSubmissionRequest) -> dict:
    orch = _orch()

    # Validate turn window
    tw = orch.turn_windows.get(req.turn_window_id)
    if tw is None:
        return asdict(
            ActionSubmitResponse(
                accepted=False, rejection_reason="Turn window not found."
            )
        )
    if tw.state != TurnWindowState.open:
        return asdict(
            ActionSubmitResponse(
                accepted=False, rejection_reason="Turn window is not open."
            )
        )

    # Validate action type
    try:
        action_type = ActionType(req.action_type)
    except ValueError:
        return asdict(
            ActionSubmitResponse(
                accepted=False,
                rejection_reason=f"Invalid action type: {req.action_type}",
            )
        )

    target_ids = [req.target_id] if req.target_id else []
    item_ids = [req.item_id] if req.item_id else []

    action = orch.submit_action(
        player_id=req.player_id,
        action_type=action_type,
        public_text=req.public_text,
        private_ref_text=req.private_ref_text,
        target_ids=target_ids,
        item_ids=item_ids,
        movement_target=req.movement_target or None,
    )

    if action:
        # Clear any draft for this player
        orch.drafts.pop(req.player_id, None)
        return asdict(ActionSubmitResponse(accepted=True, action_id=action.action_id))
    return asdict(
        ActionSubmitResponse(
            accepted=False,
            rejection_reason="Could not submit action. No active turn or already submitted.",
        )
    )


# -----------------------------------------------------------------------
# Draft
# -----------------------------------------------------------------------


@router.get("/api/action/draft/{player_id}")
async def get_draft(player_id: str) -> dict:
    orch = _orch()
    draft = orch.drafts.get(player_id)
    if draft is None:
        return asdict(DraftResponse(player_id=player_id, has_draft=False))
    return asdict(
        DraftResponse(
            player_id=player_id,
            turn_window_id=draft.get("turn_window_id", ""),
            action_type=draft.get("action_type", ""),
            target_id=draft.get("target_id", ""),
            public_text=draft.get("public_text", ""),
            private_ref_text=draft.get("private_ref_text", ""),
            has_draft=True,
        )
    )


# -----------------------------------------------------------------------
# Recap
# -----------------------------------------------------------------------


@router.get("/api/campaign/{campaign_id}/recap")
async def get_recap(
    campaign_id: str, limit: int = Query(default=10, ge=1, le=100)
) -> dict:
    orch = _orch()
    if orch.campaign_id is None or orch.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # Get log entries sorted by turn number descending
    entries = sorted(orch.turn_log, key=lambda e: e.turn_number, reverse=True)[:limit]

    recap_entries: list[RecapEntry] = []
    for entry in entries:
        scene = orch.get_scene(entry.scene_id)
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


# -----------------------------------------------------------------------
# Inbox
# -----------------------------------------------------------------------


@router.get("/api/player/{player_id}/inbox")
async def get_inbox(player_id: str, since: str = "") -> dict:
    orch = _orch()
    player = orch.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found.")

    # Find the player's private-referee scope(s)
    private_scope_ids: set[str] = set()
    for scope in orch.get_scopes():
        if (
            scope.scope_type == ScopeType.private_referee
            and scope.player_id == player_id
        ):
            private_scope_ids.add(scope.scope_id)

    read_facts = orch.inbox_read.get(player_id, set())
    messages: list[InboxMessage] = []
    for fact in orch.get_knowledge_facts():
        if fact.owner_scope_id not in private_scope_ids:
            continue
        scene = orch.get_scene(fact.scene_id)
        scene_name = scene.name if scene else fact.scene_id
        messages.append(
            InboxMessage(
                fact_id=fact.fact_id,
                fact_type=fact.fact_type.value,
                payload=fact.payload,
                scene_id=fact.scene_id,
                scene_name=scene_name,
                revealed_at=fact.revealed_at.isoformat() if fact.revealed_at else "",
                is_read=fact.fact_id in read_facts,
            )
        )

    # Sort chronologically
    messages.sort(key=lambda m: m.revealed_at)
    unread = sum(1 for m in messages if not m.is_read)

    # Mark all as read
    if player_id not in orch.inbox_read:
        orch.inbox_read[player_id] = set()
    orch.inbox_read[player_id].update(m.fact_id for m in messages)

    resp = InboxResponse(player_id=player_id, messages=messages, unread_count=unread)
    return asdict(resp)


# -----------------------------------------------------------------------
# Channels (side_channels still loaded via DB in Phase 5; for now use
# in-memory channel_messages + DB-backed SideChannelRepo)
# -----------------------------------------------------------------------


@router.get("/api/player/{player_id}/channels")
async def get_channels(player_id: str) -> dict:
    orch = _orch()
    channels: list[ChannelInfo] = []

    with orch._session_scope() as session:
        from server.storage.repository import SideChannelRepo

        if orch.campaign_id:
            all_channels = SideChannelRepo(session).list_for_campaign(orch.campaign_id)
        else:
            all_channels = []

    for ch in all_channels:
        if player_id not in ch.member_player_ids:
            continue
        member_names = []
        for mid in ch.member_player_ids:
            p = orch.get_player(mid)
            member_names.append(p.display_name if p else mid)
        msg_count = len(orch.channel_messages.get(ch.side_channel_id, []))
        channels.append(
            ChannelInfo(
                channel_id=ch.side_channel_id,
                label=ch.label,
                members=member_names,
                message_count=msg_count,
                is_open=ch.is_open,
            )
        )
    return asdict(ChannelListResponse(channels=channels))


@router.get("/api/channel/{channel_id}/messages")
async def get_channel_messages(channel_id: str) -> dict:
    orch = _orch()

    with orch._session_scope() as session:
        from server.storage.repository import SideChannelRepo

        ch = SideChannelRepo(session).get(channel_id)

    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found.")

    raw_msgs = orch.channel_messages.get(channel_id, [])
    messages: list[ChannelMessage] = []
    for msg in raw_msgs:
        sender = orch.get_player(msg.get("sender_id", ""))
        sender_name = sender.display_name if sender else msg.get("sender_id", "")
        messages.append(
            ChannelMessage(
                sender_name=sender_name,
                text=msg.get("text", ""),
                sent_at=msg.get("sent_at", ""),
            )
        )
    return asdict(ChannelMessagesResponse(channel_id=channel_id, messages=messages))


class CreateChannelRequest(BaseModel):
    creator_player_id: str
    member_player_ids: list[str]
    label: str


@router.post("/api/channel/create")
async def create_channel(req: CreateChannelRequest) -> dict:
    orch = _orch()
    if orch.campaign_id is None:
        return asdict(
            CreateChannelResponse(success=False, rejection_reason="No campaign loaded.")
        )

    # Validate all members exist
    all_players = orch.get_players()
    player_ids = {p.player_id for p in all_players}
    for mid in req.member_player_ids:
        if mid not in player_ids:
            return asdict(
                CreateChannelResponse(
                    success=False, rejection_reason=f"Player {mid} not found."
                )
            )

    from server.scope.side_channel_engine import SideChannelEngine

    engine = SideChannelEngine()
    result = engine.create_channel(
        creator_player_id=req.creator_player_id,
        member_player_ids=req.member_player_ids,
        campaign_id=orch.campaign_id,
        all_campaign_player_ids=list(player_ids),
        label=req.label,
    )
    if not result.success:
        return asdict(
            CreateChannelResponse(
                success=False, rejection_reason=result.rejection_reason
            )
        )

    # Store the channel and scope in DB
    ch = result.channel
    with orch._session_scope() as session:
        from server.storage.repository import ConversationScopeRepo, SideChannelRepo

        SideChannelRepo(session).save(ch)
        if result.scope:
            ConversationScopeRepo(session).save(result.scope)
    orch.channel_messages[ch.side_channel_id] = []

    return asdict(CreateChannelResponse(success=True, channel_id=ch.side_channel_id))


class SendMessageRequest(BaseModel):
    sender_player_id: str
    text: str


@router.post("/api/channel/{channel_id}/send")
async def send_channel_message(channel_id: str, req: SendMessageRequest) -> dict:
    orch = _orch()

    with orch._session_scope() as session:
        from server.storage.repository import SideChannelRepo

        ch = SideChannelRepo(session).get(channel_id)

    if ch is None:
        return asdict(SendMessageResponse(success=False, error="Channel not found."))
    if not ch.is_open:
        return asdict(SendMessageResponse(success=False, error="Channel is closed."))
    if req.sender_player_id not in ch.member_player_ids:
        return asdict(
            SendMessageResponse(success=False, error="Not a member of this channel.")
        )

    msg = {
        "sender_id": req.sender_player_id,
        "text": req.text,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    if channel_id not in orch.channel_messages:
        orch.channel_messages[channel_id] = []
    orch.channel_messages[channel_id].append(msg)

    return asdict(SendMessageResponse(success=True))


class LeaveChannelRequest(BaseModel):
    player_id: str


@router.post("/api/channel/{channel_id}/leave")
async def leave_channel(channel_id: str, req: LeaveChannelRequest) -> dict:
    orch = _orch()

    with orch._session_scope() as session:
        from server.storage.repository import SideChannelRepo

        ch = SideChannelRepo(session).get(channel_id)
        if ch is None:
            return asdict(
                LeaveChannelResponse(success=False, error="Channel not found.")
            )
        if req.player_id not in ch.member_player_ids:
            return asdict(
                LeaveChannelResponse(
                    success=False, error="Not a member of this channel."
                )
            )

        ch.member_player_ids.remove(req.player_id)
        if len(ch.member_player_ids) < 2:
            ch.is_open = False
        SideChannelRepo(session).save(ch)

    return asdict(LeaveChannelResponse(success=True))


# -----------------------------------------------------------------------
# Quests
# -----------------------------------------------------------------------


@router.get("/api/campaign/{campaign_id}/quests")
async def get_quests(campaign_id: str) -> dict:
    orch = _orch()
    if orch.campaign_id is None or orch.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    quests: list[QuestInfo] = []
    for quest in orch.get_quests():
        quests.append(
            QuestInfo(
                quest_id=quest.quest_id,
                title=quest.quest_id,
                description="",
                status=quest.status.value,
                objectives=[],
                player_progress=dict(quest.player_progress),
            )
        )
    return asdict(QuestListResponse(quests=quests))


# -----------------------------------------------------------------------
# Clues
# -----------------------------------------------------------------------


@router.get("/api/player/{player_id}/clues")
async def get_clues(player_id: str) -> dict:
    orch = _orch()
    player = orch.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found.")

    from server.domain.enums import KnowledgeFactType

    # Find the player's private-referee scope(s) + public scopes
    accessible_scope_ids: set[str] = set()
    for scope in orch.get_scopes():
        if scope.scope_type == ScopeType.public:
            accessible_scope_ids.add(scope.scope_id)
        elif (
            scope.scope_type == ScopeType.private_referee
            and scope.player_id == player_id
        ):
            accessible_scope_ids.add(scope.scope_id)

    clues: list[ClueInfo] = []
    for fact in orch.get_knowledge_facts():
        if fact.fact_type != KnowledgeFactType.clue:
            continue
        if fact.owner_scope_id not in accessible_scope_ids:
            continue
        scene = orch.get_scene(fact.scene_id)
        scene_name = scene.name if scene else fact.scene_id
        clues.append(
            ClueInfo(
                fact_id=fact.fact_id,
                payload=fact.payload,
                scene_name=scene_name,
                discovered_at=fact.revealed_at.isoformat() if fact.revealed_at else "",
            )
        )

    return asdict(ClueListResponse(clues=clues))


# -----------------------------------------------------------------------
# Map
# -----------------------------------------------------------------------


@router.get("/api/campaign/{campaign_id}/map")
async def get_map(campaign_id: str, player_id: str = Query(default="")) -> dict:
    orch = _orch()
    if orch.campaign_id is None or orch.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    # Determine which scenes the player has visited
    char = orch.get_player_character(player_id) if player_id else None
    current_scene_id = char.scene_id or "" if char else ""

    # For simplicity, treat any scene that has or had the player's character
    # as "discovered". Without persistent visit records in the orchestrator,
    # we consider the current scene plus scenes connected to it.
    discovered_ids: set[str] = set()
    if current_scene_id:
        discovered_ids.add(current_scene_id)
        scene = orch.get_scene(current_scene_id)
        if scene:
            for target_id in scene.exits.values():
                discovered_ids.add(target_id)

    nodes: list[MapNode] = []
    seen_node_ids: set[str] = set()

    # Add discovered nodes
    for sid in discovered_ids:
        scene = orch.get_scene(sid)
        if scene and sid not in seen_node_ids:
            is_current = sid == current_scene_id
            nodes.append(
                MapNode(
                    scene_id=sid,
                    name=scene.name
                    if is_current or sid == current_scene_id
                    else scene.name,
                    discovered=sid == current_scene_id,
                )
            )
            seen_node_ids.add(sid)

    # Add undiscovered adjacent nodes as "?" for scenes connected from discovered
    for sid in list(discovered_ids):
        scene = orch.get_scene(sid)
        if scene:
            for target_id in scene.exits.values():
                if target_id not in seen_node_ids:
                    target = orch.get_scene(target_id)
                    nodes.append(
                        MapNode(
                            scene_id=target_id,
                            name=target.name if target else "?",
                            discovered=False,
                        )
                    )
                    seen_node_ids.add(target_id)

    # Build edges
    edges: list[MapEdge] = []
    for sid in discovered_ids:
        scene = orch.get_scene(sid)
        if scene:
            for direction, target_id in scene.exits.items():
                if target_id in seen_node_ids:
                    edges.append(
                        MapEdge(
                            from_scene_id=sid,
                            to_scene_id=target_id,
                            direction=direction,
                            discovered=target_id in discovered_ids,
                        )
                    )

    return asdict(
        MapResponse(nodes=nodes, edges=edges, current_scene_id=current_scene_id)
    )
