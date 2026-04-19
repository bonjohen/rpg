"""Hidden clue discovery and scoped delivery engine — pure domain logic, no I/O.

Clues are KnowledgeFacts scoped as private_referee (for the discovering player)
or referee_only (never shown until unlocked).  This engine handles:

  - Registering clues on scene objects or scene features
  - Determining discovery (immediate or requiring a search/inspect roll)
  - Producing the right KnowledgeFact with the right scope
  - Granting wider visibility (e.g. a player shares a clue publicly)

Design decisions:
  - A ClueDefinition is pure data: discovery_method, required_action,
    scope_policy.
  - ClueEngine.discover() accepts a character, scene, and clue definition,
    and returns a ClueDiscovery result with the new KnowledgeFact and
    the intended scope.
  - Scope assignment rules:
      * scope_policy="private"  → private_referee scope for the discovering player
      * scope_policy="public"   → public scope (immediately shared)
      * scope_policy="referee"  → referee_only (stored, never delivered until
                                  the server explicitly grants visibility)

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import uuid

from server.domain.entities import (
    Character,
    KnowledgeFact,
    Scene,
    VisibilityGrant,
)
from server.domain.enums import (
    ActionType,
    KnowledgeFactType,
    ScopeType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Clue model
# ---------------------------------------------------------------------------


class ClueDiscoveryMethod(str, Enum):
    automatic = "automatic"  # discovered as soon as the character enters scene
    search = "search"  # requires a search action
    inspect = "inspect"  # requires inspecting a specific target
    interact = "interact"  # requires interacting with a specific object


class ClueScopePolicy(str, Enum):
    private = "private"  # private_referee — only the discovering player
    public = "public"  # public — everyone sees it immediately
    referee = "referee"  # referee_only — server stores, never auto-delivers


@dataclass
class ClueDefinition:
    """Definition of a discoverable clue attached to a scene feature or object.

    clue_id must be unique within the campaign / scenario.
    """

    clue_id: str
    scene_id: str
    campaign_id: str
    fact_type: KnowledgeFactType
    payload: str  # the clue text
    discovery_method: ClueDiscoveryMethod = ClueDiscoveryMethod.search
    scope_policy: ClueScopePolicy = ClueScopePolicy.private
    # For inspect/interact: the target name or object_id
    target_id: str = ""
    label: str = ""  # human-readable debug label
    has_been_discovered: bool = False  # True once any player finds it


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ClueDiscovery:
    """Result of ClueEngine.discover()."""

    discovered: bool
    # The new KnowledgeFact (caller persists and delivers via ScopeEngine)
    fact: KnowledgeFact | None = None
    # The intended scope type (caller must pass the right scope_id)
    intended_scope_type: ScopeType = ScopeType.private_referee
    # The scope_id to use (caller must supply based on scope_policy)
    scope_id: str = ""
    rejection_reason: str = ""


@dataclass
class ClueGrant:
    """Result of ClueEngine.share_clue()."""

    granted: bool
    grant: VisibilityGrant | None = None
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ClueError(Exception):
    """Base for clue engine errors."""


class ClueAlreadyDiscoveredError(ClueError):
    """Raised when a once-only clue has already been discovered."""


# ---------------------------------------------------------------------------
# ClueEngine
# ---------------------------------------------------------------------------


class ClueEngine:
    """Stateless engine for clue discovery and scoped delivery.

    Callers are responsible for:
      - Supplying accurate ClueDefinitions (loaded from scenario data).
      - Supplying the correct scope_ids (public, private, referee) for the
        campaign/player combination.
      - Persisting returned KnowledgeFacts and VisibilityGrants.
      - Delivering facts through ScopeEngine after persistence.
      - Marking ClueDefinition.has_been_discovered = True after discovery.

    The engine never calls any storage layer directly.
    """

    def discover(
        self,
        character: Character,
        scene: Scene,
        clue: ClueDefinition,
        action_type: ActionType,
        *,
        public_scope_id: str = "",
        private_scope_id: str = "",
        referee_scope_id: str = "",
        inspected_target: str = "",
        interacted_object_id: str = "",
    ) -> ClueDiscovery:
        """Attempt to discover a clue.

        Args:
            character:            The character taking the action.
            scene:                The scene they are in.
            clue:                 The ClueDefinition to check.
            action_type:          The action being resolved.
            public_scope_id:      Scope ID for public-policy clues.
            private_scope_id:     Scope ID for private-policy clues.
            referee_scope_id:     Scope ID for referee-only clues.
            inspected_target:     The target_id being inspected, if any.
            interacted_object_id: The object_id being interacted with, if any.

        Returns:
            ClueDiscovery.
        """
        if character.scene_id != scene.scene_id:
            return ClueDiscovery(
                discovered=False,
                rejection_reason=(
                    f"Character {character.character_id!r} is not in scene "
                    f"{scene.scene_id!r}."
                ),
            )

        if clue.scene_id != scene.scene_id:
            return ClueDiscovery(
                discovered=False,
                rejection_reason=(
                    f"Clue {clue.clue_id!r} is not in scene {scene.scene_id!r}."
                ),
            )

        # Discovery method gating
        method = ClueDiscoveryMethod(clue.discovery_method)

        if method == ClueDiscoveryMethod.automatic:
            pass  # always discoverable

        elif method == ClueDiscoveryMethod.search:
            if action_type != ActionType.search:
                return ClueDiscovery(
                    discovered=False,
                    rejection_reason=(
                        "This clue requires a search action to discover."
                    ),
                )

        elif method == ClueDiscoveryMethod.inspect:
            if action_type != ActionType.inspect:
                return ClueDiscovery(
                    discovered=False,
                    rejection_reason=(
                        "This clue requires an inspect action to discover."
                    ),
                )
            if clue.target_id and inspected_target != clue.target_id:
                return ClueDiscovery(
                    discovered=False,
                    rejection_reason=(
                        f"Clue {clue.clue_id!r} requires inspecting {clue.target_id!r}."
                    ),
                )

        elif method == ClueDiscoveryMethod.interact:
            if action_type != ActionType.interact:
                return ClueDiscovery(
                    discovered=False,
                    rejection_reason=(
                        "This clue requires an interact action to discover."
                    ),
                )
            if clue.target_id and interacted_object_id != clue.target_id:
                return ClueDiscovery(
                    discovered=False,
                    rejection_reason=(
                        f"Clue {clue.clue_id!r} requires interacting with "
                        f"{clue.target_id!r}."
                    ),
                )

        # Determine scope
        policy = ClueScopePolicy(clue.scope_policy)
        if policy == ClueScopePolicy.private:
            scope_id = private_scope_id
            scope_type = ScopeType.private_referee
        elif policy == ClueScopePolicy.public:
            scope_id = public_scope_id
            scope_type = ScopeType.public
        else:  # referee
            scope_id = referee_scope_id
            scope_type = ScopeType.referee_only

        if not scope_id:
            return ClueDiscovery(
                discovered=False,
                rejection_reason=(
                    f"No scope_id provided for scope_policy {clue.scope_policy!r}."
                ),
            )

        fact = KnowledgeFact(
            fact_id=_new_id(),
            campaign_id=clue.campaign_id,
            scene_id=scene.scene_id,
            owner_scope_id=scope_id,
            fact_type=clue.fact_type,
            payload=clue.payload,
            revealed_at=_now(),
        )

        # Mark discovered
        clue.has_been_discovered = True

        return ClueDiscovery(
            discovered=True,
            fact=fact,
            intended_scope_type=scope_type,
            scope_id=scope_id,
        )

    def share_clue(
        self,
        fact: KnowledgeFact,
        granted_to_scope_id: str,
        campaign_id: str,
        granted_by_player_id: str | None = None,
    ) -> ClueGrant:
        """Grant wider visibility to an existing KnowledgeFact.

        Creates a VisibilityGrant so a previously private clue can be
        seen by a broader audience (e.g. a player announces it publicly).

        Returns ClueGrant with the new VisibilityGrant (caller persists).
        """
        if not granted_to_scope_id:
            return ClueGrant(
                granted=False,
                rejection_reason="granted_to_scope_id must not be empty.",
            )

        grant = VisibilityGrant(
            grant_id=_new_id(),
            fact_id=fact.fact_id,
            campaign_id=campaign_id,
            granted_to_scope_id=granted_to_scope_id,
            granted_at=_now(),
            granted_by_player_id=granted_by_player_id,
        )

        return ClueGrant(granted=True, grant=grant)

    def filter_discoverable(
        self,
        clues: list[ClueDefinition],
        scene_id: str,
        action_type: ActionType,
        already_discovered_ids: set[str] | None = None,
    ) -> list[ClueDefinition]:
        """Return clues that could be discovered by ``action_type`` in ``scene_id``.

        Excludes clues that have already been discovered (by anyone) if
        ``already_discovered_ids`` is provided.

        Args:
            clues:                  All ClueDefinitions to filter.
            scene_id:               Target scene.
            action_type:            The action being taken.
            already_discovered_ids: Set of clue_ids already discovered.

        Returns:
            Filtered list of ClueDefinitions.
        """
        already_discovered_ids = already_discovered_ids or set()

        _action_to_methods: dict[ActionType, set[ClueDiscoveryMethod]] = {
            ActionType.move: {ClueDiscoveryMethod.automatic},
            ActionType.search: {
                ClueDiscoveryMethod.automatic,
                ClueDiscoveryMethod.search,
            },
            ActionType.inspect: {
                ClueDiscoveryMethod.automatic,
                ClueDiscoveryMethod.inspect,
            },
            ActionType.interact: {
                ClueDiscoveryMethod.automatic,
                ClueDiscoveryMethod.interact,
            },
        }

        discoverable_methods = _action_to_methods.get(action_type, set())

        return [
            c
            for c in clues
            if c.scene_id == scene_id
            and ClueDiscoveryMethod(c.discovery_method) in discoverable_methods
            and c.clue_id not in already_discovered_ids
        ]
