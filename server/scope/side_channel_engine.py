"""Side-channel creation and closure engine.

Delegates validation to SideChannelPolicy and produces domain entities
(SideChannel, ConversationScope, KnowledgeFact) for the caller to persist.
Stateless, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.domain.entities import ConversationScope, KnowledgeFact, SideChannel
from server.domain.enums import KnowledgeFactType, ScopeType
from server.scope.side_channel import SideChannelError, SideChannelPolicy


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SideChannelCreateResult:
    success: bool
    channel: Optional[SideChannel] = None
    scope: Optional[ConversationScope] = None
    rejection_reason: str = ""


@dataclass
class SideChannelCloseResult:
    success: bool
    channel: Optional[SideChannel] = None
    audit_fact: Optional[KnowledgeFact] = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SideChannelEngine:
    """Creates and closes side-channels, producing domain entities."""

    def __init__(self) -> None:
        self._policy = SideChannelPolicy()

    def create_channel(
        self,
        creator_player_id: str,
        member_player_ids: list[str],
        campaign_id: str,
        all_campaign_player_ids: list[str],
        label: str,
        *,
        channel_id: str = "",
        scope_id: str = "",
        created_at: object = None,
    ) -> SideChannelCreateResult:
        """Create a new side-channel with the given members.

        Args:
            creator_player_id:     The player creating the channel.
            member_player_ids:     All initial members (must include creator).
            campaign_id:           The campaign this channel belongs to.
            all_campaign_player_ids: All players in the campaign.
            label:                 Human-readable label for the channel.
            channel_id:            Pre-assigned channel ID (for tests).
            scope_id:              Pre-assigned scope ID (for tests).
            created_at:            Timestamp (for tests).

        Returns:
            SideChannelCreateResult with the new channel and scope on success.
        """
        from datetime import datetime, timezone

        try:
            self._policy.validate_creation(
                creator_player_id, member_player_ids, all_campaign_player_ids
            )
        except SideChannelError as exc:
            return SideChannelCreateResult(success=False, rejection_reason=str(exc))

        ts = created_at or datetime.now(timezone.utc).replace(tzinfo=None)

        channel = SideChannel(
            side_channel_id=channel_id or f"sc-{campaign_id}-{label}",
            campaign_id=campaign_id,
            created_at=ts,
            created_by_player_id=creator_player_id,
            member_player_ids=list(dict.fromkeys(member_player_ids)),
            is_open=True,
            label=label,
        )

        scope = ConversationScope(
            scope_id=scope_id or f"scope-sc-{channel.side_channel_id}",
            campaign_id=campaign_id,
            scope_type=ScopeType.side_channel,
            side_channel_id=channel.side_channel_id,
        )

        return SideChannelCreateResult(success=True, channel=channel, scope=scope)

    def close_channel(
        self,
        channel: SideChannel,
        closing_player_id: str,
        campaign_id: str,
        scene_id: str,
        *,
        fact_id: str = "",
        referee_scope_id: str = "",
    ) -> SideChannelCloseResult:
        """Close a side-channel and produce a referee-only audit fact.

        Args:
            channel:            The channel to close.
            closing_player_id:  The player closing it (must be a member).
            campaign_id:        Campaign ID for the audit fact.
            scene_id:           Scene ID for the audit fact.
            fact_id:            Pre-assigned fact ID (for tests).
            referee_scope_id:   Scope ID for referee_only audit fact.

        Returns:
            SideChannelCloseResult with the closed channel and audit fact.
        """
        from datetime import datetime, timezone

        if not self._policy.is_member(channel, closing_player_id):
            return SideChannelCloseResult(
                success=False,
                reason=f"Player {closing_player_id!r} is not a member of "
                f"channel {channel.side_channel_id!r}.",
            )

        try:
            self._policy.close_channel(channel)
        except SideChannelError as exc:
            return SideChannelCloseResult(success=False, reason=str(exc))

        ts = datetime.now(timezone.utc).replace(tzinfo=None)

        audit_fact = KnowledgeFact(
            fact_id=fact_id or f"fact-sc-close-{channel.side_channel_id}",
            campaign_id=campaign_id,
            scene_id=scene_id,
            owner_scope_id=referee_scope_id or f"scope-referee-{campaign_id}",
            fact_type=KnowledgeFactType.custom,
            payload=(
                f"[side_channel_audit] Channel '{channel.label}' closed by "
                f"{closing_player_id}"
            ),
            revealed_at=ts,
        )

        return SideChannelCloseResult(
            success=True, channel=channel, audit_fact=audit_fact, reason="closed"
        )
