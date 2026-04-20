"""NPC Social Loop starter content — two meaningful NPC interactions.

Scenario: "The Tavern and the Gate"
  - Mira the Innkeeper: friendly information source, secrets about the merchant disappearance
  - Theron the Gate Guard: dutiful, susceptible to bribery (bargain), resistant to threats

Fixed IDs are used so tests are deterministic and repeatable.
"""

from __future__ import annotations

from server.domain.helpers import utc_now as _now

from server.domain.entities import NPC
from server.domain.enums import BehaviorMode
from server.npc.tells import TellDefinition

# ---------------------------------------------------------------------------
# Fixed IDs
# ---------------------------------------------------------------------------

CAMPAIGN_ID = "campaign-social-001"
SCENE_TAVERN_ID = "scene-tavern-001"
SCENE_GATE_ID = "scene-gate-001"
PUBLIC_SCOPE_ID = "scope-public-001"
REFEREE_SCOPE_ID = "scope-referee-001"
PLAYER_SERA_ID = "player-sera-001"
PLAYER_BRAND_ID = "player-brand-001"

NPC_MIRA_ID = "npc-mira-001"
NPC_THERON_ID = "npc-theron-001"


# ---------------------------------------------------------------------------
# NPC 1: Mira the Innkeeper
#
# Interaction: Players can question her about the missing merchant.
# - Knows secret info (merchant hid something in the cellar)
# - Friendly to helpful players, evasive when trust is low
# - Has a tell: her hands shake when asked directly about the cellar
# ---------------------------------------------------------------------------


def make_npc_mira(**kwargs) -> NPC:
    """Create Mira the Innkeeper NPC."""
    return NPC(
        npc_id=kwargs.get("npc_id", NPC_MIRA_ID),
        campaign_id=kwargs.get("campaign_id", CAMPAIGN_ID),
        name=kwargs.get("name", "Mira the Innkeeper"),
        created_at=kwargs.get("created_at", _now()),
        scene_id=kwargs.get("scene_id", SCENE_TAVERN_ID),
        health_state=kwargs.get("health_state", "healthy"),
        inventory_item_ids=kwargs.get("inventory_item_ids", []),
        faction_id=kwargs.get("faction_id", "townsfolk"),
        status_effects=kwargs.get("status_effects", []),
        is_visible=kwargs.get("is_visible", True),
        stance_to_party=kwargs.get("stance_to_party", "neutral"),
        trust_by_player=kwargs.get("trust_by_player", {}),
        goal_tags=kwargs.get("goal_tags", ["protect_family", "keep_inn_safe"]),
        fear_tags=kwargs.get("fear_tags", ["exposure", "retaliation"]),
        personality_tags=kwargs.get("personality_tags", ["cautious", "secretive"]),
        memory_tags=kwargs.get("memory_tags", []),
        knowledge_fact_ids=kwargs.get("knowledge_fact_ids", []),
        current_behavior_mode=kwargs.get("current_behavior_mode", BehaviorMode.idle),
    )


def make_mira_tells() -> list[TellDefinition]:
    """Return TellDefinitions for Mira — fires when cellar topic comes up."""
    return [
        TellDefinition(
            tell_id="tell-mira-cellar",
            npc_id=NPC_MIRA_ID,
            trigger_tag="player_questioned_npc_answered",
            trigger_action_type="question",
            tell_text=(
                "Mira's hands tighten around her cloth as she mentions the cellar. "
                "She glances toward the back door before answering."
            ),
            is_active=True,
        ),
        TellDefinition(
            tell_id="tell-mira-threat",
            npc_id=NPC_MIRA_ID,
            trigger_stance="fearful",
            trigger_action_type="threaten",
            tell_text=(
                "Mira goes pale. Her voice drops to a whisper and she leans in. "
                "She is about to reveal something she normally would not."
            ),
            is_active=True,
        ),
        TellDefinition(
            tell_id="tell-mira-lie-detected",
            npc_id=NPC_MIRA_ID,
            trigger_tag="player_lied_npc_detected",
            tell_text=(
                "Mira's eyes narrow almost imperceptibly. She knows that was false "
                "but says nothing — she is noting it."
            ),
            is_active=True,
        ),
    ]


# ---------------------------------------------------------------------------
# NPC 2: Theron the Gate Guard
#
# Interaction: Players can bargain for passage or question him about recent traffic.
# - Susceptible to bargain (accepts bribes if trust ≥ 0)
# - Resistant to threats (he is a guard — has authority)
# - Will partially answer questions about road conditions
# ---------------------------------------------------------------------------


def make_npc_theron(**kwargs) -> NPC:
    """Create Theron the Gate Guard NPC."""
    return NPC(
        npc_id=kwargs.get("npc_id", NPC_THERON_ID),
        campaign_id=kwargs.get("campaign_id", CAMPAIGN_ID),
        name=kwargs.get("name", "Theron the Gate Guard"),
        created_at=kwargs.get("created_at", _now()),
        scene_id=kwargs.get("scene_id", SCENE_GATE_ID),
        health_state=kwargs.get("health_state", "healthy"),
        inventory_item_ids=kwargs.get("inventory_item_ids", []),
        faction_id=kwargs.get("faction_id", "city_watch"),
        status_effects=kwargs.get("status_effects", []),
        is_visible=kwargs.get("is_visible", True),
        stance_to_party=kwargs.get("stance_to_party", "neutral"),
        trust_by_player=kwargs.get("trust_by_player", {}),
        goal_tags=kwargs.get("goal_tags", ["enforce_gate_rules", "supplement_wage"]),
        fear_tags=kwargs.get("fear_tags", ["losing_post", "captain_disapproval"]),
        personality_tags=kwargs.get(
            "personality_tags", ["dutiful", "greedy", "guard_captain"]
        ),
        memory_tags=kwargs.get("memory_tags", []),
        knowledge_fact_ids=kwargs.get("knowledge_fact_ids", []),
        current_behavior_mode=kwargs.get("current_behavior_mode", BehaviorMode.guard),
    )


def make_theron_tells() -> list[TellDefinition]:
    """Return TellDefinitions for Theron — fires on bribe attempt or threat."""
    return [
        TellDefinition(
            tell_id="tell-theron-bribe",
            npc_id=NPC_THERON_ID,
            trigger_tag="player_bargain_accepted",
            tell_text=(
                "Theron glances left and right before palming the coin. "
                "He steps back from the gate with studied disinterest."
            ),
            is_active=True,
        ),
        TellDefinition(
            tell_id="tell-theron-threat-escalate",
            npc_id=NPC_THERON_ID,
            trigger_tag="player_threatened_npc_escalated",
            tell_text=(
                "Theron's hand drops to his sword hilt. He raises his voice: "
                "'Guard!' — the situation is escalating rapidly."
            ),
            is_active=True,
        ),
        TellDefinition(
            tell_id="tell-theron-question-partial",
            npc_id=NPC_THERON_ID,
            trigger_tag="player_questioned_npc_evasive",
            tell_text=(
                "Theron shrugs and says 'road's road' — but his eyes flick north "
                "before he does. Something came through from that direction recently."
            ),
            is_active=True,
        ),
    ]
