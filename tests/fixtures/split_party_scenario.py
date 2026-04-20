"""Split-party scenario fixture for testing.

Two-scene scenario:
  SCENE_CAVE:    Alara + Bren exploring a cave.
  SCENE_VILLAGE: Corwin gathering supplies in a village.

Each scene has its own TurnWindow. Pure data, no DB, no I/O.
All IDs are fixed strings.
"""

from __future__ import annotations

from datetime import timedelta

from server.domain.helpers import utc_now as _now

from server.domain.entities import (
    Campaign,
    Character,
    CommittedAction,
    ConversationScope,
    KnowledgeFact,
    MonsterGroup,
    NPC,
    Scene,
    TurnWindow,
)
from server.domain.enums import (
    ActionState,
    ActionType,
    AwarenessState,
    BehaviorMode,
    KnowledgeFactType,
    SceneState,
    ScopeType,
    TurnWindowState,
)


# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-split-001"

SCENE_CAVE_ID = "scene-cave"
SCENE_VILLAGE_ID = "scene-village"

PLAYER_ALARA_ID = "player-alara"
PLAYER_BREN_ID = "player-bren"
PLAYER_CORWIN_ID = "player-corwin"

CHARACTER_ALARA_ID = "char-alara"
CHARACTER_BREN_ID = "char-bren"
CHARACTER_CORWIN_ID = "char-corwin"

TURN_WINDOW_CAVE_ID = "tw-cave-001"
TURN_WINDOW_VILLAGE_ID = "tw-village-001"

SCOPE_PUBLIC_ID = "scope-public-split"
SCOPE_PUBLIC_CAVE_ID = "scope-public-cave"
SCOPE_PUBLIC_VILLAGE_ID = "scope-public-village"

NPC_MERCHANT_ID = "npc-merchant"
MONSTER_BAT_SWARM_ID = "monster-bat-swarm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def make_campaign() -> Campaign:
    return Campaign(
        campaign_id=CAMPAIGN_ID,
        name="Split Party Test",
        telegram_group_id=9004,
        main_topic_id=None,
        created_at=_now(),
    )


def make_cave_scene() -> Scene:
    return Scene(
        scene_id=SCENE_CAVE_ID,
        campaign_id=CAMPAIGN_ID,
        name="Dark Cave",
        description="A damp cave stretching into darkness.",
        created_at=_now(),
        state=SceneState.awaiting_actions,
        player_ids=[PLAYER_ALARA_ID, PLAYER_BREN_ID],
        character_ids=[CHARACTER_ALARA_ID, CHARACTER_BREN_ID],
        monster_group_ids=[MONSTER_BAT_SWARM_ID],
        active_turn_window_id=TURN_WINDOW_CAVE_ID,
    )


def make_village_scene() -> Scene:
    return Scene(
        scene_id=SCENE_VILLAGE_ID,
        campaign_id=CAMPAIGN_ID,
        name="Quiet Village",
        description="A small village with a market square.",
        created_at=_now(),
        state=SceneState.awaiting_actions,
        player_ids=[PLAYER_CORWIN_ID],
        character_ids=[CHARACTER_CORWIN_ID],
        npc_ids=[NPC_MERCHANT_ID],
        active_turn_window_id=TURN_WINDOW_VILLAGE_ID,
    )


def make_idle_village_scene() -> Scene:
    """Village scene in idle state (for activation tests)."""
    s = make_village_scene()
    s.state = SceneState.idle
    s.active_turn_window_id = None
    return s


def make_alara() -> Character:
    return Character(
        character_id=CHARACTER_ALARA_ID,
        player_id=PLAYER_ALARA_ID,
        campaign_id=CAMPAIGN_ID,
        name="Alara",
        created_at=_now(),
        scene_id=SCENE_CAVE_ID,
        stats={"hp": 18, "max_hp": 18, "attack": 6, "defense": 2},
    )


def make_bren() -> Character:
    return Character(
        character_id=CHARACTER_BREN_ID,
        player_id=PLAYER_BREN_ID,
        campaign_id=CAMPAIGN_ID,
        name="Bren",
        created_at=_now(),
        scene_id=SCENE_CAVE_ID,
        stats={"hp": 22, "max_hp": 22, "attack": 7, "defense": 4},
    )


def make_corwin() -> Character:
    return Character(
        character_id=CHARACTER_CORWIN_ID,
        player_id=PLAYER_CORWIN_ID,
        campaign_id=CAMPAIGN_ID,
        name="Corwin",
        created_at=_now(),
        scene_id=SCENE_VILLAGE_ID,
        stats={"hp": 15, "max_hp": 15, "attack": 5, "defense": 1},
    )


def make_merchant() -> NPC:
    return NPC(
        npc_id=NPC_MERCHANT_ID,
        campaign_id=CAMPAIGN_ID,
        name="Old Gareth",
        created_at=_now(),
        scene_id=SCENE_VILLAGE_ID,
    )


def make_bat_swarm() -> MonsterGroup:
    return MonsterGroup(
        monster_group_id=MONSTER_BAT_SWARM_ID,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_CAVE_ID,
        unit_type="bat",
        count=6,
        created_at=_now(),
        behavior_mode=BehaviorMode.patrol,
        awareness_state=AwarenessState.engaged,
        morale_state="steady",
        health_state="healthy",
        is_visible=True,
    )


def make_cave_turn_window() -> TurnWindow:
    now = _now()
    return TurnWindow(
        turn_window_id=TURN_WINDOW_CAVE_ID,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_CAVE_ID,
        public_scope_id=SCOPE_PUBLIC_CAVE_ID,
        opened_at=now,
        expires_at=now + timedelta(minutes=5),
        state=TurnWindowState.open,
        turn_number=1,
    )


def make_village_turn_window() -> TurnWindow:
    now = _now()
    return TurnWindow(
        turn_window_id=TURN_WINDOW_VILLAGE_ID,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_VILLAGE_ID,
        public_scope_id=SCOPE_PUBLIC_VILLAGE_ID,
        opened_at=now,
        expires_at=now + timedelta(minutes=5),
        state=TurnWindowState.open,
        turn_number=1,
    )


def make_public_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_PUBLIC_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.public,
    )


def make_public_cave_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_PUBLIC_CAVE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.public,
    )


def make_public_village_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_PUBLIC_VILLAGE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.public,
    )


def make_cave_fact(fact_id: str = "fact-cave-001") -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=fact_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_CAVE_ID,
        owner_scope_id=SCOPE_PUBLIC_CAVE_ID,
        fact_type=KnowledgeFactType.lore,
        payload="Strange claw marks cover the cave walls.",
        revealed_at=_now(),
    )


def make_village_fact(fact_id: str = "fact-village-001") -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=fact_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_VILLAGE_ID,
        owner_scope_id=SCOPE_PUBLIC_VILLAGE_ID,
        fact_type=KnowledgeFactType.lore,
        payload="The merchant sells rope and torches.",
        revealed_at=_now(),
    )


def make_committed_action(
    player_id: str,
    character_id: str,
    turn_window_id: str,
    action_id: str = "",
) -> CommittedAction:
    return CommittedAction(
        action_id=action_id or f"action-{player_id}",
        turn_window_id=turn_window_id,
        player_id=player_id,
        character_id=character_id,
        scope_id=SCOPE_PUBLIC_ID,
        declared_action_type=ActionType.hold,
        state=ActionState.submitted,
        submitted_at=_now(),
    )
