"""Combat scenario fixture — forest clearing encounter for testing.

Layout:
  [Forest Clearing] — two players vs goblin patrol (and optional wolf pack).

This is a pure-data fixture: no DB, no I/O, no async.
All IDs are fixed strings so tests can reference them by name.
"""

from __future__ import annotations

from server.domain.helpers import utc_now as _now

from server.domain.entities import (
    Campaign,
    Character,
    InventoryItem,
    MonsterGroup,
    Scene,
)
from server.domain.enums import (
    AwarenessState,
    BehaviorMode,
    HealthState,
    MoraleState,
    SceneState,
)


# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-combat-001"

SCENE_CLEARING_ID = "scene-forest-clearing"
SCENE_RETREAT_ID = "scene-forest-trail"

PLAYER_KIRA_ID = "player-kira"
PLAYER_DAIN_ID = "player-dain"
CHARACTER_KIRA_ID = "char-kira"
CHARACTER_DAIN_ID = "char-dain"

GOBLIN_PATROL_ID = "monster-goblin-patrol"
WOLF_PACK_ID = "monster-wolf-pack"

HEALING_POTION_ID = "item-healing-potion"
EMPTY_FLASK_ID = "item-empty-flask"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------


def make_combat_campaign() -> Campaign:
    return Campaign(
        campaign_id=CAMPAIGN_ID,
        name="Forest Ambush",
        telegram_group_id=9002,
        main_topic_id=None,
        created_at=_now(),
        description="A combat encounter in a forest clearing.",
    )


def make_forest_clearing() -> Scene:
    return Scene(
        scene_id=SCENE_CLEARING_ID,
        campaign_id=CAMPAIGN_ID,
        name="Forest Clearing",
        description="A sunlit clearing in the dense forest. Birdsong echoes above.",
        created_at=_now(),
        state=SceneState.awaiting_actions,
        player_ids=[PLAYER_KIRA_ID, PLAYER_DAIN_ID],
        character_ids=[CHARACTER_KIRA_ID, CHARACTER_DAIN_ID],
        monster_group_ids=[GOBLIN_PATROL_ID],
        exits={"north": SCENE_RETREAT_ID},
    )


def make_forest_trail() -> Scene:
    return Scene(
        scene_id=SCENE_RETREAT_ID,
        campaign_id=CAMPAIGN_ID,
        name="Forest Trail",
        description="A narrow trail winding through ancient oaks.",
        created_at=_now(),
        state=SceneState.idle,
        exits={"south": SCENE_CLEARING_ID},
    )


def make_kira(scene_id: str = SCENE_CLEARING_ID) -> Character:
    return Character(
        character_id=CHARACTER_KIRA_ID,
        player_id=PLAYER_KIRA_ID,
        campaign_id=CAMPAIGN_ID,
        name="Kira",
        created_at=_now(),
        scene_id=scene_id,
        stats={"hp": 20, "max_hp": 20, "attack": 8, "defense": 3},
    )


def make_dain(scene_id: str = SCENE_CLEARING_ID) -> Character:
    return Character(
        character_id=CHARACTER_DAIN_ID,
        player_id=PLAYER_DAIN_ID,
        campaign_id=CAMPAIGN_ID,
        name="Dain",
        created_at=_now(),
        scene_id=scene_id,
        stats={"hp": 20, "max_hp": 20, "attack": 8, "defense": 3},
    )


def make_goblin_patrol(
    count: int = 3,
    awareness: AwarenessState = AwarenessState.engaged,
) -> MonsterGroup:
    return MonsterGroup(
        monster_group_id=GOBLIN_PATROL_ID,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_CLEARING_ID,
        unit_type="goblin",
        count=count,
        created_at=_now(),
        behavior_mode=BehaviorMode.patrol,
        awareness_state=awareness,
        morale_state=MoraleState.steady,
        threat_table={},
        health_state=HealthState.healthy,
        is_visible=True,
    )


def make_wolf_pack(
    count: int = 4,
    awareness: AwarenessState = AwarenessState.unaware,
) -> MonsterGroup:
    return MonsterGroup(
        monster_group_id=WOLF_PACK_ID,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_CLEARING_ID,
        unit_type="wolf",
        count=count,
        created_at=_now(),
        behavior_mode=BehaviorMode.ambush,
        awareness_state=awareness,
        morale_state=MoraleState.steady,
        threat_table={},
        health_state=HealthState.healthy,
        is_visible=False,
    )


def make_healing_potion() -> InventoryItem:
    return InventoryItem(
        item_id=HEALING_POTION_ID,
        campaign_id=CAMPAIGN_ID,
        item_type="potion",
        name="Healing Potion",
        created_at=_now(),
        owner_character_id=CHARACTER_KIRA_ID,
        quantity=1,
        properties={"effect": "heal", "amount": 10},
    )


def make_empty_flask() -> InventoryItem:
    return InventoryItem(
        item_id=EMPTY_FLASK_ID,
        campaign_id=CAMPAIGN_ID,
        item_type="flask",
        name="Empty Flask",
        created_at=_now(),
        owner_character_id=CHARACTER_KIRA_ID,
        quantity=1,
        properties={},
    )
