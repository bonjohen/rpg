"""Object-state registry and change engine — pure domain logic, no I/O.

Manages the lifecycle of interactive objects in scenes (doors, chests,
levers, pressure plates, etc.).  An "object" in exploration terms is any
scene feature whose state can change as a result of character actions.

ObjectState lives in server.exploration.actions; this module provides
the ObjectStateEngine that operates on collections of ObjectState objects,
handles batch state changes (e.g. a trigger firing multiple transitions),
and validates transitions against the object's allowed-transition table.

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.exploration.actions import ObjectState


# ---------------------------------------------------------------------------
# Predefined transition tables for common object types
# ---------------------------------------------------------------------------

#: Default allowed state transitions for a simple door.
DOOR_TRANSITIONS: dict[str, set[str]] = {
    "open": {"closed"},
    "closed": {"open", "locked"},
    "locked": {"closed"},  # can unlock → closed, but not directly to open
}

#: Default transitions for a chest.
CHEST_TRANSITIONS: dict[str, set[str]] = {
    "closed": {"open", "locked"},
    "locked": {"closed"},
    "open": {"closed"},
}

#: Default transitions for a lever / switch.
LEVER_TRANSITIONS: dict[str, set[str]] = {
    "up": {"down"},
    "down": {"up"},
}

#: Default transitions for a portcullis (gate).
PORTCULLIS_TRANSITIONS: dict[str, set[str]] = {
    "raised": {"lowered"},
    "lowered": {"raised"},
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class StateChangeResult:
    """Returned by ObjectStateEngine.apply_change()."""

    success: bool
    updated_object: ObjectState | None = None
    old_state: str = ""
    new_state: str = ""
    rejection_reason: str = ""


# ---------------------------------------------------------------------------
# ObjectStateEngine
# ---------------------------------------------------------------------------


class ObjectStateEngine:
    """Stateless engine for object-state change resolution.

    Callers are responsible for:
      - Loading the current ObjectState for each object.
      - Supplying an allowed_transitions table (or None for unrestricted).
      - Persisting the returned updated ObjectState.

    The engine never calls any storage layer directly.
    """

    def apply_change(
        self,
        obj: ObjectState,
        new_state: str,
        allowed_transitions: dict[str, set[str]] | None = None,
    ) -> StateChangeResult:
        """Attempt to change ``obj`` to ``new_state``.

        Args:
            obj:                  The current ObjectState.
            new_state:            The desired new state label.
            allowed_transitions:  Transition table. If None, any transition is
                                  allowed.  Use DOOR_TRANSITIONS etc. for
                                  common object types.

        Returns:
            StateChangeResult.
        """
        if obj.state_label == new_state:
            return StateChangeResult(
                success=True,
                updated_object=obj,
                old_state=new_state,
                new_state=new_state,
            )

        if allowed_transitions is not None:
            reachable = allowed_transitions.get(obj.state_label, set())
            if new_state not in reachable:
                return StateChangeResult(
                    success=False,
                    updated_object=obj,
                    old_state=obj.state_label,
                    new_state=new_state,
                    rejection_reason=(
                        f"Object {obj.object_id!r}: cannot transition from "
                        f"{obj.state_label!r} to {new_state!r}. "
                        f"Allowed: {sorted(reachable) or 'none'}."
                    ),
                )

        old_state = obj.state_label
        obj.state_label = new_state
        return StateChangeResult(
            success=True,
            updated_object=obj,
            old_state=old_state,
            new_state=new_state,
        )

    def apply_batch(
        self,
        objects_by_id: dict[str, ObjectState],
        changes: dict[str, str],
        allowed_transitions: dict[str, dict[str, set[str]]] | None = None,
    ) -> list[StateChangeResult]:
        """Apply multiple state changes at once.

        Args:
            objects_by_id:       object_id → ObjectState mapping.
            changes:             object_id → desired_new_state mapping.
            allowed_transitions: object_id → transition table. If a given
                                 object_id has no entry, any transition is
                                 allowed for that object.

        Returns:
            List of StateChangeResult in the order of ``changes.items()``.
        """
        allowed_transitions = allowed_transitions or {}
        results: list[StateChangeResult] = []
        for obj_id, new_state in changes.items():
            obj = objects_by_id.get(obj_id)
            if obj is None:
                results.append(
                    StateChangeResult(
                        success=False,
                        old_state="",
                        new_state=new_state,
                        rejection_reason=(
                            f"Object {obj_id!r} not found in objects_by_id."
                        ),
                    )
                )
                continue
            trans = allowed_transitions.get(obj_id)
            results.append(self.apply_change(obj, new_state, trans))
        return results

    def is_blocked_exit(
        self,
        exit_direction: str,
        blocking_objects: dict[str, ObjectState],
        blocking_states: set[str] | None = None,
    ) -> bool:
        """Return True if any blocking object is in a blocking state.

        Used to derive blocked_exits for MovementEngine from object states.

        Args:
            exit_direction:  The exit label to check (not used directly —
                             included so the caller can build a per-exit map).
            blocking_objects: object_id → ObjectState for objects that guard
                              this exit.
            blocking_states:  States that count as "blocked" (default:
                              {"closed", "locked"}).

        Returns:
            True if any blocking object is in a blocking state.
        """
        blocking_states = blocking_states or {"closed", "locked"}
        return any(
            obj.state_label in blocking_states for obj in blocking_objects.values()
        )

    def derive_blocked_exits(
        self,
        exit_guard_map: dict[str, dict[str, ObjectState]],
        blocking_states: set[str] | None = None,
    ) -> set[str]:
        """Derive the set of blocked exit directions from object states.

        Args:
            exit_guard_map:  direction → {object_id: ObjectState} for objects
                             guarding each exit.  An exit is blocked if ANY
                             guarding object is in a blocking state.
            blocking_states: States that count as "blocked".

        Returns:
            Set of blocked exit direction labels.
        """
        blocking_states = blocking_states or {"closed", "locked"}
        blocked: set[str] = set()
        for direction, objs in exit_guard_map.items():
            if any(obj.state_label in blocking_states for obj in objs.values()):
                blocked.add(direction)
        return blocked
