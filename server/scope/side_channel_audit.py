"""Audit trail for side-channel lifecycle events.

Every creation, message, and closure produces a referee-only KnowledgeFact
so the server has a tamper-proof record of private coordination activity.
All audit facts use scope_type=referee_only so they never reach players or
the LLM.
"""

from __future__ import annotations

from server.domain.entities import KnowledgeFact, SideChannel
from server.domain.enums import KnowledgeFactType
from server.domain.helpers import new_id, utc_now


class SideChannelAuditor:
    """Produces referee-only KnowledgeFacts for side-channel events."""

    def record_creation(
        self,
        channel: SideChannel,
        campaign_id: str,
        scene_id: str,
        *,
        fact_id: str = "",
        referee_scope_id: str = "",
    ) -> KnowledgeFact:
        """Record that a side-channel was created."""
        members = ", ".join(channel.member_player_ids)
        return KnowledgeFact(
            fact_id=fact_id or new_id(),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id or f"scope-referee-{campaign_id}",
            fact_type=KnowledgeFactType.custom,
            payload=(
                f"[side_channel_audit] Created channel '{channel.label}' "
                f"with members: {members}"
            ),
            revealed_at=utc_now(),
        )

    def record_message(
        self,
        channel: SideChannel,
        sender_player_id: str,
        campaign_id: str,
        scene_id: str,
        *,
        fact_id: str = "",
        referee_scope_id: str = "",
    ) -> KnowledgeFact:
        """Record that a message was sent in a side-channel."""
        return KnowledgeFact(
            fact_id=fact_id or new_id(),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id or f"scope-referee-{campaign_id}",
            fact_type=KnowledgeFactType.custom,
            payload=(
                f"[side_channel_audit] Message sent in '{channel.label}' "
                f"by {sender_player_id}"
            ),
            revealed_at=utc_now(),
        )

    def record_closure(
        self,
        channel: SideChannel,
        closer_player_id: str,
        campaign_id: str,
        scene_id: str,
        *,
        fact_id: str = "",
        referee_scope_id: str = "",
    ) -> KnowledgeFact:
        """Record that a side-channel was closed."""
        return KnowledgeFact(
            fact_id=fact_id or new_id(),
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id or f"scope-referee-{campaign_id}",
            fact_type=KnowledgeFactType.custom,
            payload=(
                f"[side_channel_audit] Channel '{channel.label}' closed "
                f"by {closer_player_id}"
            ),
            revealed_at=utc_now(),
        )
