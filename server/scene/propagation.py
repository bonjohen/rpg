"""Delayed information propagation between subgroups.

When the party is split across scenes, events in one scene can propagate
to another with a configurable turn delay.  Stateless, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from server.domain.entities import KnowledgeFact
from server.domain.helpers import utc_now


@dataclass
class PropagationEvent:
    """A queued cross-scene information delivery."""

    event_id: str
    fact: KnowledgeFact
    source_scene_id: str
    target_scene_id: str
    delay_turns: int
    queued_at_turn: int
    delivered: bool = False


class InformationPropagationEngine:
    """Manages delayed cross-scene fact propagation."""

    def queue_propagation(
        self,
        fact: KnowledgeFact,
        source_scene_id: str,
        target_scene_id: str,
        delay_turns: int,
        current_turn: int,
        *,
        event_id: str = "",
    ) -> PropagationEvent:
        """Create a propagation event for a fact to reach another scene.

        Args:
            fact:             The fact to propagate.
            source_scene_id:  Where the fact originated.
            target_scene_id:  Where the fact should be delivered.
            delay_turns:      How many turns to wait before delivery.
            current_turn:     The current turn number when queuing.
            event_id:         Pre-assigned ID (for tests).
        """
        return PropagationEvent(
            event_id=event_id
            or f"prop-{source_scene_id}-{target_scene_id}-{fact.fact_id}",
            fact=fact,
            source_scene_id=source_scene_id,
            target_scene_id=target_scene_id,
            delay_turns=delay_turns,
            queued_at_turn=current_turn,
            delivered=False,
        )

    def check_deliverable(
        self, events: list[PropagationEvent], current_turn: int
    ) -> list[PropagationEvent]:
        """Return events that are ready for delivery.

        An event is deliverable when:
          current_turn >= queued_at_turn + delay_turns AND not yet delivered.
        """
        return [
            e
            for e in events
            if not e.delivered and current_turn >= e.queued_at_turn + e.delay_turns
        ]

    def deliver(
        self,
        event: PropagationEvent,
        target_scope_id: str,
        *,
        new_fact_id: str = "",
    ) -> tuple[PropagationEvent, KnowledgeFact]:
        """Deliver a propagation event, creating a new fact in the target scene.

        Marks the event as delivered and creates a new KnowledgeFact in the
        target scene with the payload prefixed with "[delayed] ".

        Args:
            event:           The propagation event to deliver.
            target_scope_id: The scope to assign to the new fact.
            new_fact_id:     Pre-assigned ID for the new fact (for tests).

        Returns:
            Tuple of (updated event, new KnowledgeFact).
        """
        event.delivered = True

        new_fact = KnowledgeFact(
            fact_id=new_fact_id or f"fact-prop-{event.event_id}",
            campaign_id=event.fact.campaign_id,
            scene_id=event.target_scene_id,
            owner_scope_id=target_scope_id,
            fact_type=event.fact.fact_type,
            payload=f"[delayed] {event.fact.payload}",
            revealed_at=utc_now(),
            source_event_id=event.event_id,
        )

        return event, new_fact
