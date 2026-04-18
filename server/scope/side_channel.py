"""Side-channel lifecycle and membership rules.

A side-channel is a private subset-of-players channel delivered via DM relay.
It is not backed by a Telegram group — messages are forwarded individually to
each member.  The SideChannelPolicy enforces membership and lifecycle invariants.
"""

from __future__ import annotations

from server.domain.entities import SideChannel


class SideChannelError(Exception):
    """Raised when a side-channel operation violates policy."""


class SideChannelPolicy:
    """Stateless enforcer for SideChannel lifecycle and membership rules.

    All methods accept domain entities and return plain results or raise
    SideChannelError.  No I/O.
    """

    # Minimum members to form a channel (must have at least one other player)
    MIN_MEMBERS: int = 2

    def validate_creation(
        self,
        creator_player_id: str,
        member_player_ids: list[str],
        all_campaign_player_ids: list[str],
    ) -> None:
        """Validate that a side-channel can be created.

        Raises SideChannelError if:
          - The creator is not in the campaign.
          - Any proposed member is not in the campaign.
          - The member list has fewer than MIN_MEMBERS distinct members.
          - The creator is not in the member list.
        """
        if creator_player_id not in all_campaign_player_ids:
            raise SideChannelError(
                f"Creator {creator_player_id!r} is not a member of this campaign."
            )

        unknown = set(member_player_ids) - set(all_campaign_player_ids)
        if unknown:
            raise SideChannelError(
                f"Unknown player IDs in side-channel: {unknown}"
            )

        distinct = set(member_player_ids)
        if len(distinct) < self.MIN_MEMBERS:
            raise SideChannelError(
                f"Side-channel requires at least {self.MIN_MEMBERS} distinct members; "
                f"got {len(distinct)}."
            )

        if creator_player_id not in distinct:
            raise SideChannelError(
                "Creator must be included in the side-channel member list."
            )

    def is_member(self, channel: SideChannel, player_id: str) -> bool:
        """Return True if ``player_id`` is a member of this channel."""
        return player_id in channel.member_player_ids

    def can_receive_message(self, channel: SideChannel, player_id: str) -> bool:
        """Return True if a message can be delivered to ``player_id`` via this channel.

        A closed channel delivers nothing.
        """
        if not channel.is_open:
            return False
        return self.is_member(channel, player_id)

    def close_channel(self, channel: SideChannel) -> SideChannel:
        """Mark the channel as closed.  Returns the mutated channel.

        Caller must persist.
        """
        if not channel.is_open:
            raise SideChannelError(
                f"Side-channel {channel.side_channel_id!r} is already closed."
            )
        channel.is_open = False
        return channel

    def recipients(self, channel: SideChannel) -> list[str]:
        """Return the list of player_ids who should receive a side-channel message.

        Empty list if the channel is closed.
        """
        if not channel.is_open:
            return []
        return list(channel.member_player_ids)
