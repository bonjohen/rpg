"""Movement and scene-transition engine — pure domain logic, no I/O.

Enforces:
  - A character may only move to a scene reachable via an exit from their
    current scene.
  - The exit must not be blocked (door closed, passage collapsed, etc.).
  - A character must be present in the source scene to leave it.
  - Destination scene existence is validated by the caller supplying it.

All methods accept and return domain entities. Persistence is the caller's
responsibility.

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.domain.entities import Character, Scene


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    """Returned by MovementEngine.move_character()."""

    moved: bool
    # Updated source scene (character removed from player_ids / character_ids)
    source_scene: Scene
    # Updated destination scene (character added to player_ids / character_ids)
    destination_scene: Scene
    # The character with updated scene_id
    character: Character
    rejection_reason: str = ""


@dataclass
class TransitionCheck:
    """Describes whether a given move is legal."""

    allowed: bool
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MovementError(Exception):
    """Base class for movement errors."""


class NoExitError(MovementError):
    """Raised when the direction does not exist in the scene's exits."""


class ExitBlockedError(MovementError):
    """Raised when the exit exists but is currently blocked."""


class NotInSceneError(MovementError):
    """Raised when the character is not a member of the source scene."""


# ---------------------------------------------------------------------------
# MovementEngine
# ---------------------------------------------------------------------------


class MovementEngine:
    """Stateless engine for scene-transition resolution.

    Callers are responsible for:
      - Loading source and destination Scene entities.
      - Loading the Character entity.
      - Supplying the current set of blocked exits for the scene.
      - Persisting the returned (mutated) scenes and character.

    The engine never calls any storage layer directly.
    """

    def check_move(
        self,
        character: Character,
        source_scene: Scene,
        direction: str,
        destination_scene: Scene,
        blocked_exits: set[str] | None = None,
    ) -> TransitionCheck:
        """Validate whether a character can move in ``direction``.

        Args:
            character:        The character attempting to move.
            source_scene:     The scene they are currently in.
            direction:        The exit label (e.g. "north", "door_a").
            destination_scene: The resolved destination scene object.
            blocked_exits:    Set of exit labels currently blocked (locked
                              doors, collapsed passages, etc.).

        Returns:
            TransitionCheck with allowed=True/False and a reason if denied.
        """
        blocked_exits = blocked_exits or set()

        # Character must be in the source scene
        if character.scene_id != source_scene.scene_id:
            return TransitionCheck(
                allowed=False,
                rejection_reason=(
                    f"Character {character.character_id!r} is not in scene "
                    f"{source_scene.scene_id!r}."
                ),
            )

        # Exit must exist
        if direction not in source_scene.exits:
            available = ", ".join(sorted(source_scene.exits.keys())) or "none"
            return TransitionCheck(
                allowed=False,
                rejection_reason=(
                    f"No exit {direction!r} from scene {source_scene.name!r}. "
                    f"Available exits: {available}."
                ),
            )

        # Exit must lead to the declared destination
        declared_dest_id = source_scene.exits[direction]
        if declared_dest_id != destination_scene.scene_id:
            return TransitionCheck(
                allowed=False,
                rejection_reason=(
                    f"Exit {direction!r} leads to scene {declared_dest_id!r}, "
                    f"not {destination_scene.scene_id!r}."
                ),
            )

        # Exit must not be blocked
        if direction in blocked_exits:
            return TransitionCheck(
                allowed=False,
                rejection_reason=f"Exit {direction!r} is currently blocked.",
            )

        return TransitionCheck(allowed=True)

    def move_character(
        self,
        character: Character,
        source_scene: Scene,
        direction: str,
        destination_scene: Scene,
        blocked_exits: set[str] | None = None,
    ) -> MoveResult:
        """Move a character from source to destination via ``direction``.

        Removes the character (and their player_id) from source_scene and
        adds them to destination_scene.  Updates character.scene_id.

        Returns a MoveResult.  Caller must persist all three returned
        entities (character, source_scene, destination_scene).
        """
        check = self.check_move(
            character, source_scene, direction, destination_scene, blocked_exits
        )
        if not check.allowed:
            return MoveResult(
                moved=False,
                source_scene=source_scene,
                destination_scene=destination_scene,
                character=character,
                rejection_reason=check.rejection_reason,
            )

        # Remove from source
        if character.character_id in source_scene.character_ids:
            source_scene.character_ids.remove(character.character_id)
        if character.player_id in source_scene.player_ids:
            source_scene.player_ids.remove(character.player_id)

        # Add to destination (guard against duplicates)
        if character.character_id not in destination_scene.character_ids:
            destination_scene.character_ids.append(character.character_id)
        if character.player_id not in destination_scene.player_ids:
            destination_scene.player_ids.append(character.player_id)

        # Update character scene membership
        character.scene_id = destination_scene.scene_id

        return MoveResult(
            moved=True,
            source_scene=source_scene,
            destination_scene=destination_scene,
            character=character,
        )

    def list_exits(
        self,
        scene: Scene,
        blocked_exits: set[str] | None = None,
    ) -> list[tuple[str, str, bool]]:
        """Return exits as (direction, destination_scene_id, is_blocked).

        Args:
            scene:         The scene whose exits to list.
            blocked_exits: Set of exit labels currently blocked.

        Returns:
            List of (direction, destination_scene_id, is_blocked) tuples,
            sorted by direction for deterministic output.
        """
        blocked_exits = blocked_exits or set()
        return sorted(
            [
                (direction, dest_id, direction in blocked_exits)
                for direction, dest_id in scene.exits.items()
            ],
            key=lambda t: t[0],
        )
