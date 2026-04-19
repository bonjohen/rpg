"""Environmental triggers and simple trap engine — pure domain logic, no I/O.

A trigger is a declarative rule:
  "when <condition> is true, apply <effect>"

Conditions are evaluated against an ExplorationContext.
Effects are applied to domain entities and returned to the caller for persistence.

Design decisions:
  - Triggers are data (TriggerDefinition dataclasses), not subclasses.
  - TriggerEngine.evaluate() fires all matching triggers and returns
    a list of TriggerFiring records describing what happened.
  - The caller is responsible for persisting state changes and delivering
    new KnowledgeFacts through ScopeEngine.
  - Traps are triggers with TriggerKind.trap; they have a damage/status
    effect payload and an optional disarm condition.

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid

from server.domain.entities import (
    Character,
    KnowledgeFact,
    Scene,
)
from server.domain.enums import (
    ActionType,
    KnowledgeFactType,
)
from server.exploration.actions import ObjectState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Trigger model
# ---------------------------------------------------------------------------


class TriggerKind(str, Enum):
    on_enter = "on_enter"  # fires when a character enters the scene
    on_exit = "on_exit"  # fires when a character leaves the scene
    on_search = "on_search"  # fires when a character searches
    on_inspect = "on_inspect"  # fires when a character inspects a target
    on_interact = "on_interact"  # fires when an object changes state
    trap = "trap"  # fires on enter or interact; has damage payload
    on_any_action = "on_any_action"  # fires on any exploration action


class TriggerCondition(str, Enum):
    always = "always"
    once = "once"  # only fires once (first qualifying event)
    if_object_open = "if_object_open"  # fires only when a named object is open
    if_object_closed = "if_object_closed"
    if_item_present = "if_item_present"  # fires only if a named item is in scene


@dataclass
class TriggerEffect:
    """What happens when a trigger fires."""

    # Narrative for public chat
    public_narrative: str = ""
    # Private narrative delivered only to the triggering character
    private_narrative: str = ""
    # Status effects to apply to the triggering character (caller applies)
    apply_status_effects: list[str] = field(default_factory=list)
    # Object state changes: {object_id: new_state_label}
    object_state_changes: dict[str, str] = field(default_factory=dict)
    # New KnowledgeFacts to create (owner_scope_id filled in by engine)
    new_fact_payloads: list[tuple[KnowledgeFactType, str]] = field(
        default_factory=list
    )  # list of (fact_type, payload_text)
    # Trap-specific: damage expression (purely descriptive; game system resolves)
    trap_damage: str = ""


@dataclass
class TriggerDefinition:
    """A single trigger rule attached to a scene or object.

    trigger_id must be unique within a campaign / scenario.
    """

    trigger_id: str
    scene_id: str
    kind: TriggerKind
    condition: TriggerCondition
    effect: TriggerEffect
    label: str = ""  # human-readable name for debugging
    # For on_interact: which object_id must change state
    target_object_id: str = ""
    # For if_item_present: which item_id must be present
    condition_item_id: str = ""
    # For if_object_open/closed: which object_id to check
    condition_object_id: str = ""
    # True once this trigger has fired (for TriggerCondition.once)
    has_fired: bool = False
    # Scope IDs for fact creation (set by the caller, used by engine)
    public_scope_id: str = ""
    private_scope_id: str = ""
    campaign_id: str = ""


# ---------------------------------------------------------------------------
# Evaluation context
# ---------------------------------------------------------------------------


@dataclass
class ExplorationContext:
    """Snapshot of the current exploration event for trigger evaluation."""

    # The character taking the action
    character: Character
    # Current scene
    scene: Scene
    # Action that caused the evaluation
    action_type: ActionType
    # For on_interact: the object that changed state
    interacted_object: ObjectState | None = None
    # Items currently in the scene (for condition checks)
    scene_item_ids: set[str] = field(default_factory=set)
    # Current object states: {object_id: state_label}
    object_states: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Firing record
# ---------------------------------------------------------------------------


@dataclass
class TriggerFiring:
    """Records that a trigger fired and what it produced."""

    trigger_id: str
    trigger_label: str
    # Narrative texts (caller delivers these via outbound layer)
    public_narrative: str
    private_narrative: str
    # Status effects to apply to the character (caller applies)
    apply_status_effects: list[str] = field(default_factory=list)
    # Object state changes to apply (caller persists ObjectState objects)
    object_state_changes: dict[str, str] = field(default_factory=dict)
    # New facts to persist and scope-deliver
    new_facts: list[KnowledgeFact] = field(default_factory=list)
    # Trap damage descriptor (empty if not a trap)
    trap_damage: str = ""


# ---------------------------------------------------------------------------
# TriggerEngine
# ---------------------------------------------------------------------------


class TriggerEngine:
    """Stateless engine that evaluates trigger rules against an exploration context.

    Callers are responsible for:
      - Providing all TriggerDefinitions for the current scene.
      - Providing accurate ExplorationContext data.
      - Persisting TriggerDefinition.has_fired after evaluation.
      - Applying TriggerFiring effects: object state changes, status effects,
        delivering narratives, and persisting new KnowledgeFacts.

    The engine never calls any storage layer directly.
    """

    def evaluate(
        self,
        ctx: ExplorationContext,
        triggers: list[TriggerDefinition],
    ) -> list[TriggerFiring]:
        """Evaluate all triggers against ``ctx`` and return those that fire.

        Mutates ``trigger.has_fired = True`` for any TriggerCondition.once
        triggers that fire. Caller must persist the updated TriggerDefinition.

        Returns a list of TriggerFiring records (may be empty).
        """
        fired: list[TriggerFiring] = []
        for trigger in triggers:
            if trigger.scene_id != ctx.scene.scene_id:
                continue
            if self._should_fire(trigger, ctx):
                firing = self._apply(trigger, ctx)
                if TriggerCondition(trigger.condition) == TriggerCondition.once:
                    trigger.has_fired = True
                fired.append(firing)
        return fired

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _should_fire(
        self,
        trigger: TriggerDefinition,
        ctx: ExplorationContext,
    ) -> bool:
        """Return True if this trigger should fire for the given context."""
        kind = TriggerKind(trigger.kind)
        condition = TriggerCondition(trigger.condition)

        # Once triggers skip if already fired
        if condition == TriggerCondition.once and trigger.has_fired:
            return False

        # Kind matching
        if kind == TriggerKind.on_any_action:
            pass  # always matches on any action
        elif kind == TriggerKind.on_enter:
            if ctx.action_type != ActionType.move:
                return False
        elif kind == TriggerKind.on_exit:
            # Fired by caller after move resolves; treat move as candidate
            if ctx.action_type != ActionType.move:
                return False
        elif kind == TriggerKind.on_search:
            if ctx.action_type != ActionType.search:
                return False
        elif kind == TriggerKind.on_inspect:
            if ctx.action_type != ActionType.inspect:
                return False
        elif kind == TriggerKind.on_interact:
            if ctx.action_type != ActionType.interact:
                return False
            if trigger.target_object_id:
                if (
                    ctx.interacted_object is None
                    or ctx.interacted_object.object_id != trigger.target_object_id
                ):
                    return False
        elif kind == TriggerKind.trap:
            # Traps fire on enter or interact
            if ctx.action_type not in (ActionType.move, ActionType.interact):
                return False

        # Condition matching
        if condition == TriggerCondition.always or condition == TriggerCondition.once:
            return True
        elif condition == TriggerCondition.if_object_open:
            obj_id = trigger.condition_object_id
            return ctx.object_states.get(obj_id) == "open"
        elif condition == TriggerCondition.if_object_closed:
            obj_id = trigger.condition_object_id
            return ctx.object_states.get(obj_id) == "closed"
        elif condition == TriggerCondition.if_item_present:
            return trigger.condition_item_id in ctx.scene_item_ids

        return False

    def _apply(
        self,
        trigger: TriggerDefinition,
        ctx: ExplorationContext,
    ) -> TriggerFiring:
        """Build a TriggerFiring from the trigger's effect."""
        effect = trigger.effect
        new_facts: list[KnowledgeFact] = []

        for fact_type, payload in effect.new_fact_payloads:
            # Use private scope for private narrative facts, public otherwise
            scope_id = (
                trigger.private_scope_id
                if trigger.private_scope_id
                else trigger.public_scope_id
            )
            if scope_id:
                new_facts.append(
                    KnowledgeFact(
                        fact_id=_new_id(),
                        campaign_id=trigger.campaign_id,
                        scene_id=trigger.scene_id,
                        owner_scope_id=scope_id,
                        fact_type=fact_type,
                        payload=payload,
                        revealed_at=_now(),
                    )
                )

        return TriggerFiring(
            trigger_id=trigger.trigger_id,
            trigger_label=trigger.label,
            public_narrative=effect.public_narrative,
            private_narrative=effect.private_narrative,
            apply_status_effects=list(effect.apply_status_effects),
            object_state_changes=dict(effect.object_state_changes),
            new_facts=new_facts,
            trap_damage=effect.trap_damage,
        )
