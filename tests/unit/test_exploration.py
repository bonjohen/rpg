"""Tests for server/exploration/ — movement, interaction, triggers, and clue delivery.

All tests are self-contained: no live DB, no LLM calls. Uses fixtures from
tests/fixtures/exploration_scenario.py.
"""

from __future__ import annotations

from server.domain.enums import ActionType, KnowledgeFactType, ScopeType
from server.exploration.actions import ExplorationEngine, ObjectState
from server.exploration.clues import (
    ClueEngine,
    ClueScopePolicy,
)
from server.exploration.memory import MemoryEngine
from server.exploration.movement import MovementEngine
from server.exploration.objects import (
    CHEST_TRANSITIONS,
    DOOR_TRANSITIONS,
    LEVER_TRANSITIONS,
    ObjectStateEngine,
)
from server.exploration.triggers import (
    ExplorationContext,
    TriggerCondition,
    TriggerDefinition,
    TriggerEffect,
    TriggerEngine,
    TriggerKind,
)
from tests.fixtures.exploration_scenario import (
    ARAGORN_PRIVATE_SCOPE_ID,
    CAMPAIGN_ID,
    CHARACTER_ARAGORN_ID,
    CHARACTER_LEGOLAS_ID,
    CHEST_LID_ID,
    CLUE_VAULT_SECRET_ID,
    ENTRANCE_HALL_ID,
    GUARD_ROOM_ID,
    HIDDEN_CHEST_ID,
    KEY_ITEM_ID,
    LEGOLAS_PRIVATE_SCOPE_ID,
    PLAYER_ARAGORN_ID,
    PORTCULLIS_ID,
    PRESSURE_PLATE_ID,
    PUBLIC_SCOPE_ID,
    REFEREE_SCOPE_ID,
    TORCH_ITEM_ID,
    TREASURE_VAULT_ID,
    TRIGGER_ENTER_VAULT_ID,
    make_character_aragorn,
    make_character_legolas,
    make_chest_lid_state,
    make_enter_vault_trigger,
    make_entrance_hall,
    make_entrance_hall_with_chars,
    make_guard_room,
    make_hidden_chest_item,
    make_iron_key_item,
    make_plate_warning_clue,
    make_portcullis_state,
    make_torch_item,
    make_trap_trigger,
    make_treasure_vault,
    make_vault_secret_clue,
)


# ===========================================================================
# MovementEngine tests
# ===========================================================================


class TestMovementEngineCheckMove:
    """Unit tests for MovementEngine.check_move()."""

    def setup_method(self):
        self.engine = MovementEngine()

    def test_valid_move_is_allowed(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(aragorn, hall, "east", guard_room)

        assert result.allowed is True
        assert result.rejection_reason == ""

    def test_character_not_in_source_scene_is_rejected(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        # Aragorn is currently in guard room, not hall
        aragorn = make_character_aragorn(GUARD_ROOM_ID)

        result = self.engine.check_move(aragorn, hall, "east", guard_room)

        assert result.allowed is False
        assert CHARACTER_ARAGORN_ID in result.rejection_reason

    def test_nonexistent_exit_is_rejected(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(aragorn, hall, "north", guard_room)

        assert result.allowed is False
        assert "north" in result.rejection_reason

    def test_blocked_exit_is_rejected(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(
            aragorn, hall, "east", guard_room, blocked_exits={"east"}
        )

        assert result.allowed is False
        assert "blocked" in result.rejection_reason

    def test_unblocked_exit_not_in_blocked_set_is_allowed(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(
            aragorn, hall, "east", guard_room, blocked_exits={"north"}
        )

        assert result.allowed is True

    def test_destination_mismatch_is_rejected(self):
        """Exit leads to guard room but caller passes vault as destination."""
        hall = make_entrance_hall()
        vault = make_treasure_vault()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(aragorn, hall, "east", vault)

        assert result.allowed is False
        assert TREASURE_VAULT_ID in result.rejection_reason

    def test_no_blocked_exits_defaults_to_empty_set(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.check_move(
            aragorn, hall, "east", guard_room, blocked_exits=None
        )

        assert result.allowed is True


class TestMovementEngineMoveCharacter:
    """Unit tests for MovementEngine.move_character()."""

    def setup_method(self):
        self.engine = MovementEngine()

    def test_successful_move_updates_character_scene_id(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall.character_ids = [CHARACTER_ARAGORN_ID]
        hall.player_ids = [PLAYER_ARAGORN_ID]

        result = self.engine.move_character(aragorn, hall, "east", guard_room)

        assert result.moved is True
        assert aragorn.scene_id == GUARD_ROOM_ID

    def test_successful_move_removes_character_from_source(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall.character_ids = [CHARACTER_ARAGORN_ID]
        hall.player_ids = [PLAYER_ARAGORN_ID]

        result = self.engine.move_character(aragorn, hall, "east", guard_room)

        assert CHARACTER_ARAGORN_ID not in result.source_scene.character_ids
        assert PLAYER_ARAGORN_ID not in result.source_scene.player_ids

    def test_successful_move_adds_character_to_destination(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall.character_ids = [CHARACTER_ARAGORN_ID]
        hall.player_ids = [PLAYER_ARAGORN_ID]

        result = self.engine.move_character(aragorn, hall, "east", guard_room)

        assert CHARACTER_ARAGORN_ID in result.destination_scene.character_ids
        assert PLAYER_ARAGORN_ID in result.destination_scene.player_ids

    def test_failed_move_returns_moved_false(self):
        hall = make_entrance_hall()
        vault = make_treasure_vault()
        # Wrong direction: hall has no "north" exit
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)

        result = self.engine.move_character(aragorn, hall, "north", vault)

        assert result.moved is False
        assert result.rejection_reason != ""

    def test_failed_move_does_not_mutate_scenes(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        # Blocked
        result = self.engine.move_character(
            aragorn, hall, "east", guard_room, blocked_exits={"east"}
        )

        assert result.moved is False
        assert CHARACTER_ARAGORN_ID not in result.destination_scene.character_ids

    def test_move_does_not_add_duplicate_character_id(self):
        hall = make_entrance_hall()
        guard_room = make_guard_room()
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        # Pre-populate destination with character already in it
        guard_room.character_ids = [CHARACTER_ARAGORN_ID]

        result = self.engine.move_character(aragorn, hall, "east", guard_room)

        assert result.destination_scene.character_ids.count(CHARACTER_ARAGORN_ID) == 1

    def test_two_players_move_independently(self):
        hall, aragorn, legolas = make_entrance_hall_with_chars()
        guard_room = make_guard_room()

        # Move aragorn east
        r1 = self.engine.move_character(aragorn, hall, "east", guard_room)

        assert r1.moved is True
        assert CHARACTER_LEGOLAS_ID in r1.source_scene.character_ids
        assert CHARACTER_ARAGORN_ID not in r1.source_scene.character_ids

    def test_list_exits_returns_sorted_tuples(self):
        guard_room = make_guard_room()
        exits = self.engine.list_exits(guard_room)

        directions = [e[0] for e in exits]
        assert directions == sorted(directions)

    def test_list_exits_marks_blocked_correctly(self):
        guard_room = make_guard_room()
        exits = self.engine.list_exits(guard_room, blocked_exits={"east"})

        east_entries = [(d, dst, blocked) for d, dst, blocked in exits if d == "east"]
        assert east_entries[0][2] is True

        west_entries = [(d, dst, blocked) for d, dst, blocked in exits if d == "west"]
        assert west_entries[0][2] is False


# ===========================================================================
# ExplorationEngine tests
# ===========================================================================


class TestExplorationEngineInspect:
    """Unit tests for ExplorationEngine.inspect()."""

    def setup_method(self):
        self.engine = ExplorationEngine()

    def test_inspect_item_produces_public_description(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        key = make_iron_key_item()

        result = self.engine.inspect(
            aragorn,
            guard_room,
            target_item=key,
            campaign_id=CAMPAIGN_ID,
            public_scope_id=PUBLIC_SCOPE_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert "Iron Key" in result.public_description

    def test_inspect_item_with_private_note_creates_fact(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()

        result = self.engine.inspect(
            aragorn,
            vault,
            target_item=chest,
            campaign_id=CAMPAIGN_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert len(result.new_facts) == 1
        fact = result.new_facts[0]
        assert fact.owner_scope_id == ARAGORN_PRIVATE_SCOPE_ID
        assert "corroded" in fact.payload

    def test_inspect_item_without_private_note_creates_no_fact(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        key = make_iron_key_item()  # no private_inspect_note

        result = self.engine.inspect(
            aragorn,
            guard_room,
            target_item=key,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert result.new_facts == []

    def test_inspect_scene_feature_surfaces_hidden_description(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()

        result = self.engine.inspect(
            aragorn,
            vault,
            target_feature="loose stone",
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )

        assert result.success is True
        assert "loose stone" in vault.hidden_description or result.private_description

    def test_inspect_whole_scene_returns_scene_description(self):
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall = make_entrance_hall()

        result = self.engine.inspect(aragorn, hall)

        assert result.success is True
        assert hall.name in result.public_description

    def test_inspect_character_not_in_scene_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)  # in guard room
        hall = make_entrance_hall()

        result = self.engine.inspect(aragorn, hall)

        assert result.success is False
        assert CHARACTER_ARAGORN_ID in result.rejection_reason

    def test_inspect_item_not_in_scene_fails(self):
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall = make_entrance_hall()
        # Chest is in the vault, not the hall
        chest = make_hidden_chest_item()

        result = self.engine.inspect(aragorn, hall, target_item=chest)

        assert result.success is False
        assert HIDDEN_CHEST_ID in result.rejection_reason


class TestExplorationEngineSearch:
    """Unit tests for ExplorationEngine.search()."""

    def setup_method(self):
        self.engine = ExplorationEngine()

    def test_search_finds_hidden_items(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()
        torch = make_torch_item()
        torch.owner_scene_id = TREASURE_VAULT_ID  # put torch in vault too

        result = self.engine.search(
            aragorn,
            vault,
            scene_items=[chest, torch],
            campaign_id=CAMPAIGN_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert chest in result.found_items
        assert torch not in result.found_items  # not hidden

    def test_search_creates_private_fact_per_hidden_item(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()

        result = self.engine.search(
            aragorn,
            vault,
            scene_items=[chest],
            campaign_id=CAMPAIGN_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert len(result.new_facts) == 1
        assert result.new_facts[0].fact_type == KnowledgeFactType.hidden_object
        assert result.new_facts[0].owner_scope_id == ARAGORN_PRIVATE_SCOPE_ID

    def test_search_no_hidden_items_returns_nothing_found(self):
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        hall = make_entrance_hall()
        torch = make_torch_item()  # not hidden

        result = self.engine.search(
            aragorn,
            hall,
            scene_items=[torch],
            campaign_id=CAMPAIGN_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert result.found_items == []
        assert "nothing hidden" in result.public_description.lower()

    def test_search_character_not_in_scene_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()

        result = self.engine.search(aragorn, vault, scene_items=[chest])

        assert result.success is False
        assert CHARACTER_ARAGORN_ID in result.rejection_reason

    def test_search_uses_found_note_if_available(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()

        result = self.engine.search(
            aragorn,
            vault,
            scene_items=[chest],
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )

        # found_note is in chest.properties
        assert "hidden iron chest" in result.new_facts[0].payload.lower()


class TestExplorationEngineInteract:
    """Unit tests for ExplorationEngine.interact()."""

    def setup_method(self):
        self.engine = ExplorationEngine()

    def test_interact_changes_object_state(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        portcullis = make_portcullis_state("closed")

        result = self.engine.interact(
            aragorn,
            guard_room,
            portcullis,
            "open",
            campaign_id=CAMPAIGN_ID,
            public_scope_id=PUBLIC_SCOPE_ID,
        )

        assert result.success is True
        assert result.updated_object.state_label == "open"

    def test_interact_already_in_desired_state_succeeds(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        portcullis = make_portcullis_state("open")

        result = self.engine.interact(
            aragorn,
            guard_room,
            portcullis,
            "open",
        )

        assert result.success is True
        assert "already" in result.public_description.lower()

    def test_interact_blocked_transition_fails(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest_lid = make_chest_lid_state("locked")

        # Can't go from locked → open directly
        result = self.engine.interact(
            aragorn,
            vault,
            chest_lid,
            "open",
            allowed_transitions=CHEST_TRANSITIONS,
        )

        assert result.success is False
        assert "locked" in result.rejection_reason

    def test_interact_creates_public_fact(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest_lid = make_chest_lid_state("closed")

        result = self.engine.interact(
            aragorn,
            vault,
            chest_lid,
            "open",
            campaign_id=CAMPAIGN_ID,
            public_scope_id=PUBLIC_SCOPE_ID,
            allowed_transitions=CHEST_TRANSITIONS,
        )

        assert result.success is True
        assert len(result.new_facts) == 1
        assert result.new_facts[0].owner_scope_id == PUBLIC_SCOPE_ID

    def test_interact_character_not_in_scene_fails(self):
        aragorn = make_character_aragorn(ENTRANCE_HALL_ID)
        guard_room = make_guard_room()
        portcullis = make_portcullis_state("closed")

        result = self.engine.interact(aragorn, guard_room, portcullis, "open")

        assert result.success is False
        assert CHARACTER_ARAGORN_ID in result.rejection_reason

    def test_interact_object_not_in_scene_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        # chest_lid is in vault, not guard_room
        chest_lid = make_chest_lid_state("closed")

        result = self.engine.interact(aragorn, guard_room, chest_lid, "open")

        assert result.success is False
        assert CHEST_LID_ID in result.rejection_reason


# ===========================================================================
# ObjectStateEngine tests
# ===========================================================================


class TestObjectStateEngine:
    """Unit tests for ObjectStateEngine."""

    def setup_method(self):
        self.engine = ObjectStateEngine()

    def test_apply_change_valid_transition(self):
        portcullis = make_portcullis_state("closed")
        result = self.engine.apply_change(portcullis, "open", DOOR_TRANSITIONS)

        assert result.success is True
        assert result.new_state == "open"
        assert portcullis.state_label == "open"

    def test_apply_change_already_in_state(self):
        portcullis = make_portcullis_state("open")
        result = self.engine.apply_change(portcullis, "open", DOOR_TRANSITIONS)

        assert result.success is True
        assert result.old_state == "open"
        assert result.new_state == "open"

    def test_apply_change_invalid_transition_fails(self):
        portcullis = make_portcullis_state("locked")
        # locked → open is not allowed in DOOR_TRANSITIONS
        result = self.engine.apply_change(portcullis, "open", DOOR_TRANSITIONS)

        assert result.success is False
        assert "locked" in result.rejection_reason

    def test_apply_change_no_transition_table_allows_anything(self):
        obj = ObjectState(
            object_id="test-obj", scene_id=GUARD_ROOM_ID, state_label="unknown"
        )
        result = self.engine.apply_change(obj, "anything", allowed_transitions=None)

        assert result.success is True
        assert obj.state_label == "anything"

    def test_chest_transitions_locked_to_closed(self):
        chest = make_chest_lid_state("locked")
        result = self.engine.apply_change(chest, "closed", CHEST_TRANSITIONS)

        assert result.success is True

    def test_chest_transitions_locked_to_open_fails(self):
        chest = make_chest_lid_state("locked")
        result = self.engine.apply_change(chest, "open", CHEST_TRANSITIONS)

        assert result.success is False

    def test_lever_transitions_up_to_down(self):
        lever = ObjectState(object_id="lever", scene_id=GUARD_ROOM_ID, state_label="up")
        result = self.engine.apply_change(lever, "down", LEVER_TRANSITIONS)

        assert result.success is True

    def test_apply_batch_success(self):
        portcullis = make_portcullis_state("closed")
        chest = make_chest_lid_state("closed")
        objects_by_id = {PORTCULLIS_ID: portcullis, CHEST_LID_ID: chest}

        results = self.engine.apply_batch(
            objects_by_id,
            {PORTCULLIS_ID: "open", CHEST_LID_ID: "open"},
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_apply_batch_unknown_object_fails_that_entry(self):
        objects_by_id = {}
        results = self.engine.apply_batch(objects_by_id, {"nonexistent": "open"})

        assert len(results) == 1
        assert results[0].success is False
        assert "nonexistent" in results[0].rejection_reason

    def test_is_blocked_exit_returns_true_when_blocking(self):
        portcullis = make_portcullis_state("closed")
        blocked = self.engine.is_blocked_exit("east", {PORTCULLIS_ID: portcullis})

        assert blocked is True

    def test_is_blocked_exit_returns_false_when_open(self):
        portcullis = make_portcullis_state("open")
        blocked = self.engine.is_blocked_exit("east", {PORTCULLIS_ID: portcullis})

        assert blocked is False

    def test_derive_blocked_exits_from_object_states(self):
        portcullis = make_portcullis_state("closed")
        exit_guard_map = {"east": {PORTCULLIS_ID: portcullis}}

        blocked = self.engine.derive_blocked_exits(exit_guard_map)

        assert "east" in blocked

    def test_derive_blocked_exits_excludes_open_exits(self):
        portcullis = make_portcullis_state("open")
        exit_guard_map = {"east": {PORTCULLIS_ID: portcullis}}

        blocked = self.engine.derive_blocked_exits(exit_guard_map)

        assert "east" not in blocked


# ===========================================================================
# TriggerEngine tests
# ===========================================================================


class TestTriggerEngine:
    """Unit tests for TriggerEngine."""

    def setup_method(self):
        self.engine = TriggerEngine()

    def _make_ctx(
        self,
        scene_id: str,
        action_type: ActionType,
        interacted_object: ObjectState | None = None,
        object_states: dict | None = None,
        scene_item_ids: set | None = None,
    ) -> ExplorationContext:
        if scene_id == GUARD_ROOM_ID:
            scene = make_guard_room()
        elif scene_id == TREASURE_VAULT_ID:
            scene = make_treasure_vault()
        else:
            scene = make_entrance_hall()

        character = make_character_aragorn(scene_id)
        return ExplorationContext(
            character=character,
            scene=scene,
            action_type=action_type,
            interacted_object=interacted_object,
            object_states=object_states or {},
            scene_item_ids=scene_item_ids or set(),
        )

    def test_on_enter_trigger_fires_on_move(self):
        trigger = make_enter_vault_trigger()
        ctx = self._make_ctx(TREASURE_VAULT_ID, ActionType.move)

        firings = self.engine.evaluate(ctx, [trigger])

        assert len(firings) == 1
        assert firings[0].trigger_id == TRIGGER_ENTER_VAULT_ID

    def test_on_enter_trigger_does_not_fire_on_search(self):
        trigger = make_enter_vault_trigger()
        ctx = self._make_ctx(TREASURE_VAULT_ID, ActionType.search)

        firings = self.engine.evaluate(ctx, [trigger])

        assert firings == []

    def test_once_trigger_fires_only_once(self):
        trigger = make_enter_vault_trigger()
        ctx = self._make_ctx(TREASURE_VAULT_ID, ActionType.move)

        # First evaluation
        firings1 = self.engine.evaluate(ctx, [trigger])
        assert len(firings1) == 1
        assert trigger.has_fired is True

        # Second evaluation — should not fire
        firings2 = self.engine.evaluate(ctx, [trigger])
        assert firings2 == []

    def test_trap_fires_on_move_when_condition_met(self):
        # Trap fires when pressure plate is "open" (armed)
        trap = make_trap_trigger()
        ctx = self._make_ctx(
            GUARD_ROOM_ID,
            ActionType.move,
            object_states={PRESSURE_PLATE_ID: "open"},  # condition checks "open"
        )
        # Note: condition is if_object_open so needs state == "open"
        ctx.object_states[PRESSURE_PLATE_ID] = "open"

        firings = self.engine.evaluate(ctx, [trap])

        assert len(firings) == 1
        assert firings[0].trap_damage == "1d6 piercing"
        assert "hit_crossbow_bolt" in firings[0].apply_status_effects

    def test_trap_does_not_fire_when_condition_not_met(self):
        trap = make_trap_trigger()
        ctx = self._make_ctx(
            GUARD_ROOM_ID,
            ActionType.move,
            object_states={PRESSURE_PLATE_ID: "disarmed"},
        )

        firings = self.engine.evaluate(ctx, [trap])

        assert firings == []

    def test_trigger_for_different_scene_does_not_fire(self):
        trigger = make_enter_vault_trigger()
        # Character is in guard room, not vault
        ctx = self._make_ctx(GUARD_ROOM_ID, ActionType.move)

        firings = self.engine.evaluate(ctx, [trigger])

        assert firings == []

    def test_on_interact_trigger_with_target_object_fires_correctly(self):
        portcullis = make_portcullis_state("open")
        trigger = TriggerDefinition(
            trigger_id="test-interact-trigger",
            scene_id=GUARD_ROOM_ID,
            kind=TriggerKind.on_interact,
            condition=TriggerCondition.always,
            effect=TriggerEffect(public_narrative="The portcullis creaks open."),
            target_object_id=PORTCULLIS_ID,
            public_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        ctx = self._make_ctx(
            GUARD_ROOM_ID,
            ActionType.interact,
            interacted_object=portcullis,
        )

        firings = self.engine.evaluate(ctx, [trigger])

        assert len(firings) == 1
        assert "portcullis" in firings[0].public_narrative.lower()

    def test_on_interact_trigger_does_not_fire_for_wrong_object(self):
        chest_lid = make_chest_lid_state("open")
        trigger = TriggerDefinition(
            trigger_id="test-interact-trigger",
            scene_id=GUARD_ROOM_ID,
            kind=TriggerKind.on_interact,
            condition=TriggerCondition.always,
            effect=TriggerEffect(public_narrative="The portcullis creaks open."),
            target_object_id=PORTCULLIS_ID,  # wants portcullis, gets chest_lid
            public_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        ctx = self._make_ctx(
            GUARD_ROOM_ID,
            ActionType.interact,
            interacted_object=chest_lid,
        )

        firings = self.engine.evaluate(ctx, [trigger])

        assert firings == []

    def test_on_any_action_fires_for_all_action_types(self):
        trigger = TriggerDefinition(
            trigger_id="any-action-trigger",
            scene_id=GUARD_ROOM_ID,
            kind=TriggerKind.on_any_action,
            condition=TriggerCondition.always,
            effect=TriggerEffect(public_narrative="Something happens."),
            public_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        for action_type in (
            ActionType.move,
            ActionType.search,
            ActionType.inspect,
            ActionType.interact,
        ):
            ctx = self._make_ctx(GUARD_ROOM_ID, action_type)
            firings = self.engine.evaluate(ctx, [trigger])
            assert len(firings) == 1, f"on_any_action should fire for {action_type}"

    def test_trigger_with_fact_payloads_creates_facts(self):
        trigger = TriggerDefinition(
            trigger_id="fact-trigger",
            scene_id=ENTRANCE_HALL_ID,
            kind=TriggerKind.on_enter,
            condition=TriggerCondition.always,
            effect=TriggerEffect(
                public_narrative="You feel a chill.",
                new_fact_payloads=[(KnowledgeFactType.lore, "The hall is haunted.")],
            ),
            public_scope_id=PUBLIC_SCOPE_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        ctx = self._make_ctx(ENTRANCE_HALL_ID, ActionType.move)

        firings = self.engine.evaluate(ctx, [trigger])

        assert len(firings) == 1
        assert len(firings[0].new_facts) == 1
        assert firings[0].new_facts[0].fact_type == KnowledgeFactType.lore

    def test_if_item_present_condition(self):
        trigger = TriggerDefinition(
            trigger_id="item-condition-trigger",
            scene_id=GUARD_ROOM_ID,
            kind=TriggerKind.on_search,
            condition=TriggerCondition.if_item_present,
            condition_item_id=KEY_ITEM_ID,
            effect=TriggerEffect(public_narrative="The key glints in the light."),
            public_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        ctx_with_key = self._make_ctx(
            GUARD_ROOM_ID, ActionType.search, scene_item_ids={KEY_ITEM_ID}
        )
        ctx_without_key = self._make_ctx(
            GUARD_ROOM_ID, ActionType.search, scene_item_ids=set()
        )

        assert len(self.engine.evaluate(ctx_with_key, [trigger])) == 1
        assert len(self.engine.evaluate(ctx_without_key, [trigger])) == 0

    def test_multiple_triggers_all_evaluated(self):
        t1 = make_enter_vault_trigger()
        t2 = TriggerDefinition(
            trigger_id="second-vault-trigger",
            scene_id=TREASURE_VAULT_ID,
            kind=TriggerKind.on_enter,
            condition=TriggerCondition.always,
            effect=TriggerEffect(public_narrative="Dust falls from the ceiling."),
            public_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
        )
        ctx = self._make_ctx(TREASURE_VAULT_ID, ActionType.move)

        firings = self.engine.evaluate(ctx, [t1, t2])

        assert len(firings) == 2


# ===========================================================================
# ClueEngine tests
# ===========================================================================


class TestClueEngine:
    """Unit tests for ClueEngine."""

    def setup_method(self):
        self.engine = ClueEngine()

    def test_discover_search_clue_via_search_action(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is True
        assert result.fact is not None
        assert result.intended_scope_type == ScopeType.private_referee
        assert result.scope_id == ARAGORN_PRIVATE_SCOPE_ID

    def test_discover_search_clue_via_wrong_action_fails(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.inspect,  # wrong: clue requires search
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is False
        assert "search" in result.rejection_reason.lower()

    def test_discover_inspect_clue_for_correct_target(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        clue = make_plate_warning_clue()

        result = self.engine.discover(
            aragorn,
            guard_room,
            clue,
            ActionType.inspect,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            inspected_target=PRESSURE_PLATE_ID,
        )

        assert result.discovered is True
        assert "crossbow" in result.fact.payload.lower()

    def test_discover_inspect_clue_for_wrong_target_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        clue = make_plate_warning_clue()

        result = self.engine.discover(
            aragorn,
            guard_room,
            clue,
            ActionType.inspect,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            inspected_target="random_thing",
        )

        assert result.discovered is False
        assert PRESSURE_PLATE_ID in result.rejection_reason

    def test_discover_marks_clue_as_discovered(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()
        assert clue.has_been_discovered is False

        self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert clue.has_been_discovered is True

    def test_discover_character_not_in_scene_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)  # in guard room
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is False
        assert CHARACTER_ARAGORN_ID in result.rejection_reason

    def test_discover_clue_from_wrong_scene_fails(self):
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        clue = make_vault_secret_clue()  # clue is in vault

        result = self.engine.discover(
            aragorn,
            guard_room,
            clue,
            ActionType.search,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is False
        assert clue.clue_id in result.rejection_reason

    def test_discover_public_clue_uses_public_scope(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()
        clue.scope_policy = ClueScopePolicy.public

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            public_scope_id=PUBLIC_SCOPE_ID,
        )

        assert result.discovered is True
        assert result.intended_scope_type == ScopeType.public
        assert result.scope_id == PUBLIC_SCOPE_ID

    def test_discover_referee_clue_uses_referee_scope(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()
        clue.scope_policy = ClueScopePolicy.referee

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            referee_scope_id=REFEREE_SCOPE_ID,
        )

        assert result.discovered is True
        assert result.intended_scope_type == ScopeType.referee_only

    def test_discover_without_scope_id_fails(self):
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()
        # No scope_id provided

        result = self.engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
        )

        assert result.discovered is False
        assert "scope_id" in result.rejection_reason.lower()

    def test_share_clue_creates_visibility_grant(self):
        from server.domain.entities import KnowledgeFact
        from datetime import datetime, timezone
        import uuid

        fact = KnowledgeFact(
            fact_id=str(uuid.uuid4()),
            campaign_id=CAMPAIGN_ID,
            scene_id=TREASURE_VAULT_ID,
            owner_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            fact_type=KnowledgeFactType.clue,
            payload="A secret clue.",
            revealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        grant_result = self.engine.share_clue(
            fact,
            granted_to_scope_id=PUBLIC_SCOPE_ID,
            campaign_id=CAMPAIGN_ID,
            granted_by_player_id=PLAYER_ARAGORN_ID,
        )

        assert grant_result.granted is True
        assert grant_result.grant is not None
        assert grant_result.grant.fact_id == fact.fact_id
        assert grant_result.grant.granted_to_scope_id == PUBLIC_SCOPE_ID
        assert grant_result.grant.granted_by_player_id == PLAYER_ARAGORN_ID

    def test_share_clue_without_scope_id_fails(self):
        from server.domain.entities import KnowledgeFact
        from datetime import datetime, timezone
        import uuid

        fact = KnowledgeFact(
            fact_id=str(uuid.uuid4()),
            campaign_id=CAMPAIGN_ID,
            scene_id=TREASURE_VAULT_ID,
            owner_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            fact_type=KnowledgeFactType.clue,
            payload="A secret clue.",
            revealed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        grant_result = self.engine.share_clue(
            fact,
            granted_to_scope_id="",
            campaign_id=CAMPAIGN_ID,
        )

        assert grant_result.granted is False

    def test_filter_discoverable_clues_by_action(self):
        vault_clue = make_vault_secret_clue()  # requires search
        plate_clue = make_plate_warning_clue()  # requires inspect
        all_clues = [vault_clue, plate_clue]

        search_clues = self.engine.filter_discoverable(
            all_clues, TREASURE_VAULT_ID, ActionType.search
        )
        inspect_clues = self.engine.filter_discoverable(
            all_clues, GUARD_ROOM_ID, ActionType.inspect
        )

        assert vault_clue in search_clues
        assert plate_clue not in search_clues
        assert plate_clue in inspect_clues
        assert vault_clue not in inspect_clues

    def test_filter_discoverable_excludes_already_discovered(self):
        vault_clue = make_vault_secret_clue()

        filtered = self.engine.filter_discoverable(
            [vault_clue],
            TREASURE_VAULT_ID,
            ActionType.search,
            already_discovered_ids={CLUE_VAULT_SECRET_ID},
        )

        assert filtered == []


# ===========================================================================
# MemoryEngine tests
# ===========================================================================


class TestMemoryEngine:
    """Unit tests for MemoryEngine."""

    def setup_method(self):
        self.engine = MemoryEngine()

    def test_record_visit_first_time_creates_new_record(self):
        result = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="A stone corridor.",
            existing_record=None,
        )

        assert result.is_first_visit is True
        assert result.just_created is True
        assert result.record.visit_count == 1
        assert result.record.character_id == CHARACTER_ARAGORN_ID
        assert result.record.scene_id == ENTRANCE_HALL_ID

    def test_record_visit_second_time_updates_existing_record(self):
        first = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="A stone corridor.",
            existing_record=None,
        )
        second = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Still a stone corridor.",
            existing_record=first.record,
        )

        assert second.is_first_visit is False
        assert second.record.visit_count == 2
        assert second.record.last_visit_description == "Still a stone corridor."

    def test_first_visit_description_preserved_on_revisit(self):
        first = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Original description.",
            existing_record=None,
        )
        second = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Updated description.",
            existing_record=first.record,
        )

        assert second.record.first_visit_description == "Original description."
        assert second.record.last_visit_description == "Updated description."

    def test_recall_description_never_visited_returns_false(self):
        result = self.engine.recall_description(
            CHARACTER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            existing_record=None,
        )

        assert result.has_visited is False
        assert result.recall_text == ""
        assert result.visit_count == 0

    def test_recall_description_once_visited(self):
        visit = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="A dark room.",
            existing_record=None,
        )
        result = self.engine.recall_description(
            CHARACTER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            existing_record=visit.record,
        )

        assert result.has_visited is True
        assert "once" in result.recall_text.lower()
        assert "A dark room." in result.recall_text

    def test_recall_description_multiple_visits(self):
        first = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Visit 1.",
            existing_record=None,
        )
        second = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Visit 2.",
            existing_record=first.record,
        )
        third = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="Visit 3.",
            existing_record=second.record,
        )

        result = self.engine.recall_description(
            CHARACTER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            existing_record=third.record,
        )

        assert result.has_visited is True
        assert result.visit_count == 3
        assert "3" in result.recall_text

    def test_recall_description_wrong_character_returns_false(self):
        visit = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="A dark room.",
            existing_record=None,
        )
        result = self.engine.recall_description(
            CHARACTER_LEGOLAS_ID,  # wrong character
            ENTRANCE_HALL_ID,
            existing_record=visit.record,
        )

        assert result.has_visited is False

    def test_add_discovered_fact_appends_id(self):
        visit = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="desc",
            existing_record=None,
        )
        record = self.engine.add_discovered_fact(visit.record, "fact-001")

        assert "fact-001" in record.discovered_fact_ids

    def test_add_discovered_fact_no_duplicates(self):
        visit = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="desc",
            existing_record=None,
        )
        self.engine.add_discovered_fact(visit.record, "fact-001")
        self.engine.add_discovered_fact(visit.record, "fact-001")

        assert visit.record.discovered_fact_ids.count("fact-001") == 1

    def test_has_character_visited_true_when_record_exists(self):
        visit = self.engine.record_visit(
            character_id=CHARACTER_ARAGORN_ID,
            player_id=PLAYER_ARAGORN_ID,
            scene_id=ENTRANCE_HALL_ID,
            campaign_id=CAMPAIGN_ID,
            scene_description="desc",
            existing_record=None,
        )

        assert (
            self.engine.has_character_visited(
                CHARACTER_ARAGORN_ID, ENTRANCE_HALL_ID, [visit.record]
            )
            is True
        )

    def test_has_character_visited_false_when_no_record(self):
        assert (
            self.engine.has_character_visited(
                CHARACTER_ARAGORN_ID, ENTRANCE_HALL_ID, []
            )
            is False
        )

    def test_scenes_visited_by_character_returns_most_recent_first(self):
        r1 = self.engine.record_visit(
            CHARACTER_ARAGORN_ID,
            PLAYER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            CAMPAIGN_ID,
            "desc1",
            None,
        )
        r2 = self.engine.record_visit(
            CHARACTER_ARAGORN_ID,
            PLAYER_ARAGORN_ID,
            GUARD_ROOM_ID,
            CAMPAIGN_ID,
            "desc2",
            None,
        )
        # Force guard room to have a later timestamp by updating it
        r2.record.last_visited_at = r1.record.last_visited_at.replace(
            second=r1.record.last_visited_at.second + 1
            if r1.record.last_visited_at.second < 59
            else 0
        )

        scenes = self.engine.scenes_visited_by_character(
            CHARACTER_ARAGORN_ID, [r1.record, r2.record]
        )

        assert len(scenes) == 2
        assert GUARD_ROOM_ID in scenes
        assert ENTRANCE_HALL_ID in scenes

    def test_observed_item_ids_updated_on_revisit(self):
        first = self.engine.record_visit(
            CHARACTER_ARAGORN_ID,
            PLAYER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            CAMPAIGN_ID,
            "desc",
            None,
            observed_item_ids=[TORCH_ITEM_ID],
        )
        second = self.engine.record_visit(
            CHARACTER_ARAGORN_ID,
            PLAYER_ARAGORN_ID,
            ENTRANCE_HALL_ID,
            CAMPAIGN_ID,
            "desc",
            first.record,
            observed_item_ids=[TORCH_ITEM_ID, KEY_ITEM_ID],
        )

        assert KEY_ITEM_ID in second.record.observed_item_ids


# ===========================================================================
# Integration scenario: three-room dungeon
# ===========================================================================


class TestThreeRoomDungeonScenario:
    """Integration tests using the full three-room dungeon scenario fixture."""

    def setup_method(self):
        self.move_engine = MovementEngine()
        self.explore_engine = ExplorationEngine()
        self.trigger_engine = TriggerEngine()
        self.clue_engine = ClueEngine()
        self.object_engine = ObjectStateEngine()
        self.memory_engine = MemoryEngine()

    def test_full_path_entrance_to_guard_room(self):
        """Aragorn can move from Entrance Hall to Guard Room."""
        hall, aragorn, legolas = make_entrance_hall_with_chars()
        guard_room = make_guard_room()

        result = self.move_engine.move_character(aragorn, hall, "east", guard_room)

        assert result.moved is True
        assert aragorn.scene_id == GUARD_ROOM_ID

    def test_blocked_portcullis_prevents_guard_to_vault(self):
        """A closed portcullis blocks the east exit from Guard Room."""
        portcullis = make_portcullis_state("closed")
        guard_room = make_guard_room()
        vault = make_treasure_vault()
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room.character_ids = [CHARACTER_ARAGORN_ID]
        guard_room.player_ids = [PLAYER_ARAGORN_ID]

        # Derive blocked exits from object state
        blocked = self.object_engine.derive_blocked_exits(
            {"east": {PORTCULLIS_ID: portcullis}}
        )
        result = self.move_engine.move_character(
            aragorn, guard_room, "east", vault, blocked_exits=blocked
        )

        assert result.moved is False
        assert "blocked" in result.rejection_reason

    def test_open_portcullis_allows_guard_to_vault(self):
        """Opening the portcullis unblocks the east exit."""
        portcullis = make_portcullis_state("open")
        guard_room = make_guard_room()
        vault = make_treasure_vault()
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room.character_ids = [CHARACTER_ARAGORN_ID]
        guard_room.player_ids = [PLAYER_ARAGORN_ID]

        blocked = self.object_engine.derive_blocked_exits(
            {"east": {PORTCULLIS_ID: portcullis}}
        )
        result = self.move_engine.move_character(
            aragorn, guard_room, "east", vault, blocked_exits=blocked
        )

        assert result.moved is True
        assert aragorn.scene_id == TREASURE_VAULT_ID

    def test_enter_vault_trigger_fires_on_first_entry(self):
        """The once trigger fires when entering the vault for the first time."""
        vault = make_treasure_vault()
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        trigger = make_enter_vault_trigger()

        ctx = ExplorationContext(
            character=aragorn,
            scene=vault,
            action_type=ActionType.move,
        )
        firings = self.trigger_engine.evaluate(ctx, [trigger])

        assert len(firings) == 1
        assert trigger.has_fired is True

    def test_enter_vault_trigger_does_not_fire_on_second_entry(self):
        """The once trigger does not fire on revisit."""
        vault = make_treasure_vault()
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        trigger = make_enter_vault_trigger()
        trigger.has_fired = True

        ctx = ExplorationContext(
            character=aragorn,
            scene=vault,
            action_type=ActionType.move,
        )
        firings = self.trigger_engine.evaluate(ctx, [trigger])

        assert firings == []

    def test_search_vault_finds_hidden_chest(self):
        """Searching the vault finds the hidden iron chest."""
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        chest = make_hidden_chest_item()

        result = self.explore_engine.search(
            aragorn,
            vault,
            [chest],
            campaign_id=CAMPAIGN_ID,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.success is True
        assert chest in result.found_items

    def test_search_vault_discovers_secret_clue(self):
        """Searching the vault discovers the vault secret clue."""
        aragorn = make_character_aragorn(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()

        result = self.clue_engine.discover(
            aragorn,
            vault,
            clue,
            ActionType.search,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is True
        assert result.fact.owner_scope_id == ARAGORN_PRIVATE_SCOPE_ID

    def test_legolas_finds_different_private_scoped_clue(self):
        """Legolas discovers the same clue definition but it goes to her scope."""
        legolas = make_character_legolas(TREASURE_VAULT_ID)
        vault = make_treasure_vault()
        clue = make_vault_secret_clue()
        clue.has_been_discovered = False  # reset for Legolas

        result = self.clue_engine.discover(
            legolas,
            vault,
            clue,
            ActionType.search,
            private_scope_id=LEGOLAS_PRIVATE_SCOPE_ID,
        )

        assert result.discovered is True
        assert result.fact.owner_scope_id == LEGOLAS_PRIVATE_SCOPE_ID

    def test_inspect_pressure_plate_reveals_trap_warning(self):
        """Inspecting the pressure plate reveals the trap warning clue."""
        aragorn = make_character_aragorn(GUARD_ROOM_ID)
        guard_room = make_guard_room()
        clue = make_plate_warning_clue()

        result = self.clue_engine.discover(
            aragorn,
            guard_room,
            clue,
            ActionType.inspect,
            private_scope_id=ARAGORN_PRIVATE_SCOPE_ID,
            inspected_target=PRESSURE_PLATE_ID,
        )

        assert result.discovered is True
        assert "crossbow" in result.fact.payload.lower()

    def test_revisit_memory_tracks_visit_count(self):
        """Visit count increments on each visit."""
        record = None
        for visit_num in range(1, 4):
            visit_result = self.memory_engine.record_visit(
                CHARACTER_ARAGORN_ID,
                PLAYER_ARAGORN_ID,
                ENTRANCE_HALL_ID,
                CAMPAIGN_ID,
                "A stone corridor.",
                record,
            )
            record = visit_result.record
            assert record.visit_count == visit_num

        recall = self.memory_engine.recall_description(
            CHARACTER_ARAGORN_ID, ENTRANCE_HALL_ID, record
        )
        assert recall.visit_count == 3

    def test_full_dungeon_path_with_portcullis_interaction(self):
        """
        Aragorn starts in Entrance Hall.
        Moves east to Guard Room.
        Opens the portcullis via interact.
        Moves east to Treasure Vault.
        """
        hall, aragorn, _ = make_entrance_hall_with_chars()
        guard_room = make_guard_room()
        vault = make_treasure_vault()
        portcullis = make_portcullis_state("closed")

        # Step 1: Move to Guard Room
        r1 = self.move_engine.move_character(aragorn, hall, "east", guard_room)
        assert r1.moved is True
        guard_room.character_ids = [CHARACTER_ARAGORN_ID]
        guard_room.player_ids = [PLAYER_ARAGORN_ID]

        # Step 2: Open portcullis — use DOOR_TRANSITIONS since portcullis starts "closed"
        # (PORTCULLIS_TRANSITIONS uses raised/lowered; we use a door-style table here)
        r2 = self.explore_engine.interact(
            aragorn,
            guard_room,
            portcullis,
            "open",
            campaign_id=CAMPAIGN_ID,
            public_scope_id=PUBLIC_SCOPE_ID,
            allowed_transitions=DOOR_TRANSITIONS,
        )
        assert r2.success is True
        assert portcullis.state_label == "open"

        # Step 3: East is now unblocked
        blocked = self.object_engine.derive_blocked_exits(
            {"east": {PORTCULLIS_ID: portcullis}}
        )
        assert "east" not in blocked

        # Step 4: Move to Treasure Vault
        r3 = self.move_engine.move_character(
            aragorn, guard_room, "east", vault, blocked_exits=blocked
        )
        assert r3.moved is True
        assert aragorn.scene_id == TREASURE_VAULT_ID
