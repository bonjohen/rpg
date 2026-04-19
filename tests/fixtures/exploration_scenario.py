"""Exploration scenario fixture — three connected rooms for testing.

Layout:
  [Entrance Hall] --east--> [Guard Room] --east--> [Treasure Vault]
                                   ^                       |
                                   +-------west------------+
  The Guard Room has a locked east door (portcullis).
  The Treasure Vault contains a hidden chest with a clue inside.
  The Guard Room has a pressure-plate trap.

This is a pure-data fixture: no DB, no I/O, no async.
All IDs are fixed strings so tests can be written against them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from server.domain.entities import (
    Campaign,
    Character,
    ConversationScope,
    InventoryItem,
    Player,
    Scene,
)
from server.domain.enums import (
    KnowledgeFactType,
    SceneState,
    ScopeType,
)
from server.exploration.actions import ObjectState
from server.exploration.clues import (
    ClueDefinition,
    ClueDiscoveryMethod,
    ClueScopePolicy,
)
from server.exploration.triggers import (
    TriggerCondition,
    TriggerDefinition,
    TriggerEffect,
    TriggerKind,
)


# ---------------------------------------------------------------------------
# Fixed IDs  (all tests may reference these by name)
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-dungeon-001"

# Scene IDs
ENTRANCE_HALL_ID = "scene-entrance-hall"
GUARD_ROOM_ID = "scene-guard-room"
TREASURE_VAULT_ID = "scene-treasure-vault"

# Player / Character IDs
PLAYER_ARAGORN_ID = "player-aragorn"
PLAYER_LEGOLAS_ID = "player-legolas"
CHARACTER_ARAGORN_ID = "char-aragorn"
CHARACTER_LEGOLAS_ID = "char-legolas"

# Item IDs
HIDDEN_CHEST_ID = "item-hidden-chest"
KEY_ITEM_ID = "item-iron-key"
TORCH_ITEM_ID = "item-torch"

# Object IDs (interactive scene objects)
PORTCULLIS_ID = "obj-portcullis-guard-room"
CHEST_LID_ID = "obj-chest-lid-vault"
PRESSURE_PLATE_ID = "obj-pressure-plate-guard-room"

# Scope IDs (public scope per scene, private scopes per player)
PUBLIC_SCOPE_ID = "scope-public"
ARAGORN_PRIVATE_SCOPE_ID = "scope-private-aragorn"
LEGOLAS_PRIVATE_SCOPE_ID = "scope-private-legolas"
REFEREE_SCOPE_ID = "scope-referee"

# Clue IDs
CLUE_VAULT_SECRET_ID = "clue-vault-secret"
CLUE_PLATE_WARNING_ID = "clue-plate-warning"

# Trigger IDs
TRIGGER_TRAP_PLATE_ID = "trigger-trap-pressure-plate"
TRIGGER_ENTER_VAULT_ID = "trigger-enter-vault"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Scenario factory
# ---------------------------------------------------------------------------


def make_dungeon_campaign() -> Campaign:
    return Campaign(
        campaign_id=CAMPAIGN_ID,
        name="The Dungeon Below",
        telegram_group_id=9001,
        main_topic_id=None,
        created_at=_now(),
        description="A short three-room dungeon for exploration testing.",
    )


def make_entrance_hall() -> Scene:
    return Scene(
        scene_id=ENTRANCE_HALL_ID,
        campaign_id=CAMPAIGN_ID,
        name="Entrance Hall",
        description=(
            "A broad stone corridor with mossy walls. "
            "Torchlight flickers from the east."
        ),
        created_at=_now(),
        state=SceneState.idle,
        exits={"east": GUARD_ROOM_ID},
        hidden_description="Scratch marks on the floor suggest something was dragged east recently.",
    )


def make_guard_room() -> Scene:
    return Scene(
        scene_id=GUARD_ROOM_ID,
        campaign_id=CAMPAIGN_ID,
        name="Guard Room",
        description=(
            "An austere guardroom. An iron portcullis blocks the eastern passage. "
            "A worn pressure plate sits in the centre of the floor."
        ),
        created_at=_now(),
        state=SceneState.idle,
        exits={"east": TREASURE_VAULT_ID, "west": ENTRANCE_HALL_ID},
        hidden_description=(
            "The pressure plate connects to a crossbow trap in the ceiling. "
            "Stepping on it while the portcullis is closed fires a bolt."
        ),
    )


def make_treasure_vault() -> Scene:
    return Scene(
        scene_id=TREASURE_VAULT_ID,
        campaign_id=CAMPAIGN_ID,
        name="Treasure Vault",
        description=(
            "A small vault carved from solid rock. Dust-covered shelves line the walls."
        ),
        created_at=_now(),
        state=SceneState.idle,
        exits={"west": GUARD_ROOM_ID},
        hidden_description=(
            "Behind the eastmost shelf is a loose stone. "
            "Behind the stone: a note written in old common."
        ),
    )


def make_player_aragorn() -> Player:
    return Player(
        player_id=PLAYER_ARAGORN_ID,
        campaign_id=CAMPAIGN_ID,
        telegram_user_id=10001,
        telegram_username="aragorn_ttk",
        display_name="Aragorn",
        joined_at=_now(),
        has_dm_open=True,
    )


def make_player_legolas() -> Player:
    return Player(
        player_id=PLAYER_LEGOLAS_ID,
        campaign_id=CAMPAIGN_ID,
        telegram_user_id=10002,
        telegram_username="legolas_ttk",
        display_name="Legolas",
        joined_at=_now(),
        has_dm_open=True,
    )


def make_character_aragorn(scene_id: str = ENTRANCE_HALL_ID) -> Character:
    return Character(
        character_id=CHARACTER_ARAGORN_ID,
        player_id=PLAYER_ARAGORN_ID,
        campaign_id=CAMPAIGN_ID,
        name="Aragorn",
        created_at=_now(),
        scene_id=scene_id,
    )


def make_character_legolas(scene_id: str = ENTRANCE_HALL_ID) -> Character:
    return Character(
        character_id=CHARACTER_LEGOLAS_ID,
        player_id=PLAYER_LEGOLAS_ID,
        campaign_id=CAMPAIGN_ID,
        name="Legolas",
        created_at=_now(),
        scene_id=scene_id,
    )


def make_entrance_hall_with_chars() -> tuple[Scene, Character, Character]:
    """Return Entrance Hall with both characters already in it."""
    hall = make_entrance_hall()
    aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
    legolas = make_character_legolas(ENTRANCE_HALL_ID)
    hall.character_ids = [CHARACTER_ARAGORN_ID, CHARACTER_LEGOLAS_ID]
    hall.player_ids = [PLAYER_ARAGORN_ID, PLAYER_LEGOLAS_ID]
    return hall, aragorn, legolas


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def make_hidden_chest_item() -> InventoryItem:
    return InventoryItem(
        item_id=HIDDEN_CHEST_ID,
        campaign_id=CAMPAIGN_ID,
        item_type="chest",
        name="Old Iron Chest",
        created_at=_now(),
        owner_scene_id=TREASURE_VAULT_ID,
        is_hidden=True,
        properties={
            "inspect_note": "The chest is tarnished with age. The lock looks weak.",
            "found_note": "You discover a hidden iron chest behind the eastern shelf!",
            "private_inspect_note": "The lock mechanism is corroded — it could be forced.",
        },
    )


def make_iron_key_item() -> InventoryItem:
    return InventoryItem(
        item_id=KEY_ITEM_ID,
        campaign_id=CAMPAIGN_ID,
        item_type="key",
        name="Iron Key",
        created_at=_now(),
        owner_scene_id=GUARD_ROOM_ID,
        is_hidden=False,
        properties={"inspect_note": "A heavy key stamped with a portcullis emblem."},
    )


def make_torch_item() -> InventoryItem:
    return InventoryItem(
        item_id=TORCH_ITEM_ID,
        campaign_id=CAMPAIGN_ID,
        item_type="torch",
        name="Torch",
        created_at=_now(),
        owner_scene_id=ENTRANCE_HALL_ID,
        is_hidden=False,
    )


# ---------------------------------------------------------------------------
# Object states (interactive objects)
# ---------------------------------------------------------------------------


def make_portcullis_state(state: str = "closed") -> ObjectState:
    return ObjectState(
        object_id=PORTCULLIS_ID,
        scene_id=GUARD_ROOM_ID,
        state_label=state,
    )


def make_chest_lid_state(state: str = "closed") -> ObjectState:
    return ObjectState(
        object_id=CHEST_LID_ID,
        scene_id=TREASURE_VAULT_ID,
        state_label=state,
    )


def make_pressure_plate_state(state: str = "armed") -> ObjectState:
    return ObjectState(
        object_id=PRESSURE_PLATE_ID,
        scene_id=GUARD_ROOM_ID,
        state_label=state,
    )


# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------


def make_public_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=PUBLIC_SCOPE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.public,
    )


def make_aragorn_private_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.private_referee,
        player_id=PLAYER_ARAGORN_ID,
    )


def make_legolas_private_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=LEGOLAS_PRIVATE_SCOPE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.private_referee,
        player_id=PLAYER_LEGOLAS_ID,
    )


def make_referee_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=REFEREE_SCOPE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.referee_only,
    )


# ---------------------------------------------------------------------------
# Clue definitions
# ---------------------------------------------------------------------------


def make_vault_secret_clue() -> ClueDefinition:
    """A clue discoverable by searching the Treasure Vault."""
    return ClueDefinition(
        clue_id=CLUE_VAULT_SECRET_ID,
        scene_id=TREASURE_VAULT_ID,
        campaign_id=CAMPAIGN_ID,
        fact_type=KnowledgeFactType.clue,
        payload=(
            "The note reads: 'The vault key lies with the sleeping guard. "
            "The plate is a gift for the unwary.'"
        ),
        discovery_method=ClueDiscoveryMethod.search,
        scope_policy=ClueScopePolicy.private,
        label="vault_secret_note",
    )


def make_plate_warning_clue() -> ClueDefinition:
    """A clue discoverable by inspecting the pressure plate."""
    return ClueDefinition(
        clue_id=CLUE_PLATE_WARNING_ID,
        scene_id=GUARD_ROOM_ID,
        campaign_id=CAMPAIGN_ID,
        fact_type=KnowledgeFactType.trap,
        payload=(
            "On closer inspection the plate is mechanically linked to a "
            "ceiling-mounted crossbow. Stepping on it will fire a bolt."
        ),
        discovery_method=ClueDiscoveryMethod.inspect,
        scope_policy=ClueScopePolicy.private,
        target_id=PRESSURE_PLATE_ID,
        label="plate_trap_warning",
    )


# ---------------------------------------------------------------------------
# Trigger definitions
# ---------------------------------------------------------------------------


def make_trap_trigger(public_scope_id: str = PUBLIC_SCOPE_ID) -> TriggerDefinition:
    """Pressure plate trap — fires on move or interact when plate is armed."""
    return TriggerDefinition(
        trigger_id=TRIGGER_TRAP_PLATE_ID,
        scene_id=GUARD_ROOM_ID,
        kind=TriggerKind.trap,
        condition=TriggerCondition.if_object_open,  # "armed" == trigger fires
        effect=TriggerEffect(
            public_narrative=(
                "A bolt fires from the ceiling! The pressure plate was a trap!"
            ),
            apply_status_effects=["hit_crossbow_bolt"],
            trap_damage="1d6 piercing",
        ),
        label="pressure_plate_trap",
        condition_object_id=PRESSURE_PLATE_ID,
        public_scope_id=public_scope_id,
        campaign_id=CAMPAIGN_ID,
    )


def make_enter_vault_trigger(
    public_scope_id: str = PUBLIC_SCOPE_ID,
) -> TriggerDefinition:
    """Fires once when a character enters the vault for the first time."""
    return TriggerDefinition(
        trigger_id=TRIGGER_ENTER_VAULT_ID,
        scene_id=TREASURE_VAULT_ID,
        kind=TriggerKind.on_enter,
        condition=TriggerCondition.once,
        effect=TriggerEffect(
            public_narrative=(
                "As you step into the vault, dust motes swirl around your feet "
                "and the air smells of old copper."
            ),
        ),
        label="first_enter_vault",
        public_scope_id=public_scope_id,
        campaign_id=CAMPAIGN_ID,
    )
