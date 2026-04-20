"""Exploration action resolution engine — pure domain logic, no I/O.

Resolves the four canonical exploration actions:
  - move    → handled by MovementEngine (see movement.py)
  - inspect → examine a specific target (NPC, item, feature, object)
  - search  → broad sweep of the current scene for hidden content
  - interact → engage with an object or mechanism (open door, pull lever, etc.)

All methods accept and return domain entities plus typed result objects.
Persistence is the caller's responsibility.

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import (
    Character,
    InventoryItem,
    KnowledgeFact,
    Scene,
)
from server.domain.enums import (
    KnowledgeFactType,
)
from server.domain.helpers import new_id, utc_now


# ---------------------------------------------------------------------------
# Object state model
# ---------------------------------------------------------------------------


@dataclass
class ObjectState:
    """Runtime state for an interactive object in a scene.

    object_id must match an InventoryItem.item_id or a scene feature key.
    """

    object_id: str
    scene_id: str
    state_label: str = "closed"  # e.g. "open", "closed", "locked", "broken"
    is_hidden: bool = False
    properties: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class InspectResult:
    """Returned by ExplorationEngine.inspect()."""

    success: bool
    # Public narrative description produced for the inspecting character
    public_description: str = ""
    # Private (referee-scoped) description for this character only
    private_description: str = ""
    # New KnowledgeFacts produced by this inspection (caller persists and scopes)
    new_facts: list[KnowledgeFact] = field(default_factory=list)
    rejection_reason: str = ""


@dataclass
class SearchResult:
    """Returned by ExplorationEngine.search()."""

    success: bool
    # Hidden items uncovered (caller changes is_hidden=False and persists)
    found_items: list[InventoryItem] = field(default_factory=list)
    # New KnowledgeFacts produced by the search (caller persists and scopes)
    new_facts: list[KnowledgeFact] = field(default_factory=list)
    public_description: str = ""
    private_description: str = ""
    rejection_reason: str = ""


@dataclass
class InteractResult:
    """Returned by ExplorationEngine.interact()."""

    success: bool
    # Updated object state (caller persists)
    updated_object: ObjectState | None = None
    # New KnowledgeFacts produced (caller persists and scopes)
    new_facts: list[KnowledgeFact] = field(default_factory=list)
    public_description: str = ""
    private_description: str = ""
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExplorationError(Exception):
    """Base class for exploration action errors."""


class NotInSceneError(ExplorationError):
    """Character is not in the declared scene."""


class TargetNotFoundError(ExplorationError):
    """The target item or object is not present in the scene."""


class ObjectLockedError(ExplorationError):
    """The object cannot be interacted with in its current state."""


# ---------------------------------------------------------------------------
# ExplorationEngine
# ---------------------------------------------------------------------------


class ExplorationEngine:
    """Stateless engine for exploration action resolution.

    Callers are responsible for:
      - Loading all domain entities before calling engine methods.
      - Persisting returned entities, updated states, and new facts.
      - Routing new KnowledgeFacts through ScopeEngine for delivery.
      - Applying trigger checks after each action (see triggers.py).

    The engine never calls any storage layer directly.
    """

    # ------------------------------------------------------------------
    # Inspect
    # ------------------------------------------------------------------

    def inspect(
        self,
        character: Character,
        scene: Scene,
        target_item: InventoryItem | None = None,
        target_feature: str | None = None,
        campaign_id: str = "",
        public_scope_id: str = "",
        private_scope_id: str = "",
    ) -> InspectResult:
        """Resolve an inspect action.

        The character examines a specific target in the scene.  If the target
        is an InventoryItem, its ``properties`` dict may contain a
        ``"inspect_note"`` key with additional lore.  If the target is a named
        scene feature (a string key from ``scene.hidden_description``-style
        annotations) the hidden description is surfaced privately.

        Args:
            character:       The inspecting character.
            scene:           The scene they are currently in.
            target_item:     The InventoryItem being inspected (or None).
            target_feature:  A named feature to inspect (or None).
            campaign_id:     Campaign to stamp on new KnowledgeFacts.
            public_scope_id: Scope ID for publicly-scoped facts.
            private_scope_id: Scope ID for privately-scoped facts.

        Returns:
            InspectResult.
        """
        if character.scene_id != scene.scene_id:
            return InspectResult(
                success=False,
                rejection_reason=(
                    f"Character {character.character_id!r} is not in scene "
                    f"{scene.scene_id!r}."
                ),
            )

        new_facts: list[KnowledgeFact] = []

        # ---- Inspect item ----
        if target_item is not None:
            if target_item.owner_scene_id != scene.scene_id and (
                target_item.owner_character_id != character.character_id
            ):
                return InspectResult(
                    success=False,
                    rejection_reason=(
                        f"Item {target_item.item_id!r} is not present in scene "
                        f"{scene.scene_id!r} or on character "
                        f"{character.character_id!r}."
                    ),
                )

            inspect_note = target_item.properties.get("inspect_note", "")
            public_desc = f"You examine the {target_item.name}. " + (
                inspect_note if inspect_note else "Nothing unusual stands out."
            )
            private_desc = target_item.properties.get("private_inspect_note", "")

            if private_desc and private_scope_id:
                new_facts.append(
                    KnowledgeFact(
                        fact_id=new_id(),
                        campaign_id=campaign_id,
                        scene_id=scene.scene_id,
                        owner_scope_id=private_scope_id,
                        fact_type=KnowledgeFactType.clue,
                        payload=private_desc,
                        revealed_at=utc_now(),
                    )
                )

            return InspectResult(
                success=True,
                public_description=public_desc,
                private_description=private_desc,
                new_facts=new_facts,
            )

        # ---- Inspect scene feature ----
        if target_feature is not None:
            # Surface the scene's hidden_description privately
            if scene.hidden_description and private_scope_id:
                new_facts.append(
                    KnowledgeFact(
                        fact_id=new_id(),
                        campaign_id=campaign_id,
                        scene_id=scene.scene_id,
                        owner_scope_id=private_scope_id,
                        fact_type=KnowledgeFactType.lore,
                        payload=scene.hidden_description,
                        revealed_at=utc_now(),
                    )
                )
            return InspectResult(
                success=True,
                public_description=(f"You inspect the {target_feature} carefully."),
                private_description=scene.hidden_description,
                new_facts=new_facts,
            )

        # No target — inspect the whole scene
        return InspectResult(
            success=True,
            public_description=(f"You look around {scene.name}. {scene.description}"),
            private_description="",
            new_facts=new_facts,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        character: Character,
        scene: Scene,
        scene_items: list[InventoryItem],
        campaign_id: str = "",
        private_scope_id: str = "",
    ) -> SearchResult:
        """Resolve a search action — broad sweep for hidden content.

        Reveals all InventoryItems in the scene whose ``is_hidden=True``.
        Creates a private KnowledgeFact for each found hidden item.

        Args:
            character:        The searching character.
            scene:            The scene being searched.
            scene_items:      All InventoryItems currently in the scene
                              (hidden and visible).
            campaign_id:      Campaign to stamp on new facts.
            private_scope_id: Scope for the private discovery facts.

        Returns:
            SearchResult.
        """
        if character.scene_id != scene.scene_id:
            return SearchResult(
                success=False,
                rejection_reason=(
                    f"Character {character.character_id!r} is not in scene "
                    f"{scene.scene_id!r}."
                ),
            )

        hidden_items = [item for item in scene_items if item.is_hidden]
        new_facts: list[KnowledgeFact] = []

        for item in hidden_items:
            item.is_hidden = False
            fact_payload = (
                item.properties.get("found_note") or f"You find a hidden {item.name}."
            )
            if private_scope_id:
                new_facts.append(
                    KnowledgeFact(
                        fact_id=new_id(),
                        campaign_id=campaign_id,
                        scene_id=scene.scene_id,
                        owner_scope_id=private_scope_id,
                        fact_type=KnowledgeFactType.hidden_object,
                        payload=fact_payload,
                        revealed_at=utc_now(),
                    )
                )

        if hidden_items:
            desc = (
                f"Your search of {scene.name} uncovers "
                + ", ".join(item.name for item in hidden_items)
                + "."
            )
        else:
            desc = f"You search {scene.name} thoroughly but find nothing hidden."

        return SearchResult(
            success=True,
            found_items=hidden_items,
            new_facts=new_facts,
            public_description=desc,
            private_description="",
        )

    # ------------------------------------------------------------------
    # Interact
    # ------------------------------------------------------------------

    def interact(
        self,
        character: Character,
        scene: Scene,
        obj: ObjectState,
        desired_state: str,
        campaign_id: str = "",
        public_scope_id: str = "",
        private_scope_id: str = "",
        allowed_transitions: dict[str, set[str]] | None = None,
    ) -> InteractResult:
        """Resolve an interact action — change an object's state.

        Examples: open/close a door, pull a lever, open a chest.

        Args:
            character:           The interacting character.
            scene:               The scene they are in.
            obj:                 The ObjectState being operated on.
            desired_state:       The state the character wants the object in
                                 (e.g. "open", "closed").
            campaign_id:         Campaign for new facts.
            public_scope_id:     Scope for public facts.
            private_scope_id:    Scope for private facts.
            allowed_transitions: Mapping of current_state → set of reachable
                                 states. If None, any transition is allowed.

        Returns:
            InteractResult.
        """
        if character.scene_id != scene.scene_id:
            return InteractResult(
                success=False,
                rejection_reason=(
                    f"Character {character.character_id!r} is not in scene "
                    f"{scene.scene_id!r}."
                ),
            )

        if obj.scene_id != scene.scene_id:
            return InteractResult(
                success=False,
                rejection_reason=(
                    f"Object {obj.object_id!r} is not in scene {scene.scene_id!r}."
                ),
            )

        # Already in desired state?
        if obj.state_label == desired_state:
            return InteractResult(
                success=True,
                updated_object=obj,
                public_description=(f"The {obj.object_id} is already {desired_state}."),
            )

        # Check transition table if provided
        if allowed_transitions is not None:
            reachable = allowed_transitions.get(obj.state_label, set())
            if desired_state not in reachable:
                return InteractResult(
                    success=False,
                    rejection_reason=(
                        f"Cannot change {obj.object_id!r} from "
                        f"{obj.state_label!r} to {desired_state!r}."
                    ),
                )

        old_state = obj.state_label
        obj.state_label = desired_state

        new_facts: list[KnowledgeFact] = []
        if public_scope_id:
            new_facts.append(
                KnowledgeFact(
                    fact_id=new_id(),
                    campaign_id=campaign_id,
                    scene_id=scene.scene_id,
                    owner_scope_id=public_scope_id,
                    fact_type=KnowledgeFactType.custom,
                    payload=(
                        f"The {obj.object_id} changed from {old_state} "
                        f"to {desired_state}."
                    ),
                    revealed_at=utc_now(),
                )
            )

        return InteractResult(
            success=True,
            updated_object=obj,
            new_facts=new_facts,
            public_description=(f"You {desired_state} the {obj.object_id}."),
        )
