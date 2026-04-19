"""Side-channel scenario fixture for testing.

Three players in one campaign — two form a secret side-channel.
Pure data, no DB, no I/O.  All IDs are fixed strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from server.domain.entities import (
    Campaign,
    ConversationScope,
    KnowledgeFact,
    Scene,
    SideChannel,
)
from server.domain.enums import KnowledgeFactType, SceneState, ScopeType


# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-sc-001"
SCENE_ID = "scene-tavern-sc"

PLAYER_ALICE_ID = "player-alice"
PLAYER_BOB_ID = "player-bob"
PLAYER_CAROL_ID = "player-carol"

CHANNEL_ID = "sc-heist-crew"
CHANNEL_LABEL = "heist crew"

SCOPE_PUBLIC_ID = "scope-public-sc"
SCOPE_CHANNEL_ID = "scope-sc-heist"
SCOPE_REFEREE_ID = "scope-referee-sc"
SCOPE_PRIVATE_ALICE_ID = "scope-private-alice"

ALL_PLAYER_IDS = [PLAYER_ALICE_ID, PLAYER_BOB_ID, PLAYER_CAROL_ID]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def make_campaign() -> Campaign:
    return Campaign(
        campaign_id=CAMPAIGN_ID,
        name="Side-Channel Test Campaign",
        telegram_group_id=9003,
        main_topic_id=None,
        created_at=_now(),
    )


def make_tavern_scene() -> Scene:
    return Scene(
        scene_id=SCENE_ID,
        campaign_id=CAMPAIGN_ID,
        name="The Whispering Tavern",
        description="A dimly lit tavern popular with conspirators.",
        created_at=_now(),
        state=SceneState.awaiting_actions,
        player_ids=ALL_PLAYER_IDS[:],
    )


def make_side_channel(
    members: list[str] | None = None,
    is_open: bool = True,
) -> SideChannel:
    """Create a side-channel between Alice and Bob by default."""
    return SideChannel(
        side_channel_id=CHANNEL_ID,
        campaign_id=CAMPAIGN_ID,
        created_at=_now(),
        created_by_player_id=PLAYER_ALICE_ID,
        member_player_ids=members or [PLAYER_ALICE_ID, PLAYER_BOB_ID],
        is_open=is_open,
        label=CHANNEL_LABEL,
    )


def make_public_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_PUBLIC_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.public,
    )


def make_channel_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_CHANNEL_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.side_channel,
        side_channel_id=CHANNEL_ID,
    )


def make_referee_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_REFEREE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.referee_only,
    )


def make_private_alice_scope() -> ConversationScope:
    return ConversationScope(
        scope_id=SCOPE_PRIVATE_ALICE_ID,
        campaign_id=CAMPAIGN_ID,
        scope_type=ScopeType.private_referee,
        player_id=PLAYER_ALICE_ID,
    )


def make_public_fact(fact_id: str = "fact-pub-001") -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=fact_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        owner_scope_id=SCOPE_PUBLIC_ID,
        fact_type=KnowledgeFactType.lore,
        payload="The tavern serves excellent ale.",
        revealed_at=_now(),
    )


def make_side_channel_fact(
    fact_id: str = "fact-sc-001",
) -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=fact_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        owner_scope_id=SCOPE_CHANNEL_ID,
        fact_type=KnowledgeFactType.custom,
        payload="We meet at midnight behind the stables.",
        revealed_at=_now(),
    )


def make_referee_fact(fact_id: str = "fact-ref-001") -> KnowledgeFact:
    return KnowledgeFact(
        fact_id=fact_id,
        campaign_id=CAMPAIGN_ID,
        scene_id=SCENE_ID,
        owner_scope_id=SCOPE_REFEREE_ID,
        fact_type=KnowledgeFactType.custom,
        payload="Alice is secretly working with the thieves guild.",
        revealed_at=_now(),
    )
