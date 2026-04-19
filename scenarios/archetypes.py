"""Reusable NPC archetypes and monster templates for scenario authoring.

Each archetype/template provides default personality, goals, dialogue hints,
tells, and stats that a scenario author can instantiate and override.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scenarios.schema import MonsterDefinition, NpcDefinition, NpcTellDefinition


# ---------------------------------------------------------------------------
# NPC Archetypes
# ---------------------------------------------------------------------------


@dataclass
class NpcArchetype:
    """Reusable NPC personality template."""

    archetype_id: str
    personality_tags: list[str]
    default_goals: list[str]
    dialogue_hints: list[str]
    default_tells: list[NpcTellDefinition]

    def instantiate(
        self,
        npc_id: str,
        name: str,
        scene_id: str = "",
        **overrides: object,
    ) -> NpcDefinition:
        """Create an NpcDefinition from this archetype."""
        tags = list(
            overrides.get("personality_tags", self.personality_tags)
            or self.personality_tags
        )  # type: ignore[arg-type]
        goals = list(overrides.get("goals", self.default_goals) or self.default_goals)  # type: ignore[arg-type]
        hints = list(
            overrides.get("dialogue_hints", self.dialogue_hints) or self.dialogue_hints
        )  # type: ignore[arg-type]
        tells = list(overrides.get("tells", self.default_tells) or self.default_tells)  # type: ignore[arg-type]

        return NpcDefinition(
            npc_id=npc_id,
            name=name,
            description=str(overrides.get("description", "")),
            personality_tags=tags,
            goals=goals,
            trust_initial=dict(overrides.get("trust_initial", {}) or {}),  # type: ignore[arg-type]
            faction=str(overrides.get("faction", "")),
            scene_id=scene_id,
            inventory_item_ids=list(overrides.get("inventory_item_ids", []) or []),  # type: ignore[arg-type]
            dialogue_hints=hints,
            referee_notes=str(overrides.get("referee_notes", "")),
            tells=tells,
        )


SUSPICIOUS_MERCHANT = NpcArchetype(
    archetype_id="suspicious_merchant",
    personality_tags=["cautious", "greedy", "deceptive"],
    default_goals=["maximize profit", "avoid trouble"],
    dialogue_hints=["speaks evasively", "quotes prices for everything"],
    default_tells=[
        NpcTellDefinition(
            tell_id="suspicious_merchant_exit_glance",
            trigger_type="trust_below",
            trigger_value="-20",
            behavior="glances at the exit",
            scope="public",
        ),
        NpcTellDefinition(
            tell_id="suspicious_merchant_reach",
            trigger_type="action_type",
            trigger_value="threaten",
            behavior="reaches under the counter",
            scope="public",
        ),
    ],
)

LOYAL_GUARD = NpcArchetype(
    archetype_id="loyal_guard",
    personality_tags=["dutiful", "brave", "stubborn"],
    default_goals=["protect their charge", "follow orders"],
    dialogue_hints=["speaks formally", "references duty and honor"],
    default_tells=[
        NpcTellDefinition(
            tell_id="loyal_guard_relax",
            trigger_type="trust_above",
            trigger_value="30",
            behavior="relaxes stance slightly",
            scope="public",
        ),
        NpcTellDefinition(
            tell_id="loyal_guard_weapon",
            trigger_type="trust_below",
            trigger_value="-40",
            behavior="hand moves to weapon",
            scope="public",
        ),
    ],
)

MYSTERIOUS_SAGE = NpcArchetype(
    archetype_id="mysterious_sage",
    personality_tags=["cryptic", "knowledgeable", "patient"],
    default_goals=["share wisdom selectively", "test the worthy"],
    dialogue_hints=["speaks in metaphor", "asks questions instead of answering"],
    default_tells=[
        NpcTellDefinition(
            tell_id="mysterious_sage_pause",
            trigger_type="action_type",
            trigger_value="question",
            behavior="pauses thoughtfully before speaking",
            scope="public",
        ),
    ],
)

COWARDLY_MINION = NpcArchetype(
    archetype_id="cowardly_minion",
    personality_tags=["fearful", "obedient", "chatty_when_scared"],
    default_goals=["survive", "please the boss"],
    dialogue_hints=["stammers when nervous", "looks for escape routes"],
    default_tells=[
        NpcTellDefinition(
            tell_id="cowardly_minion_blurt",
            trigger_type="trust_below",
            trigger_value="-50",
            behavior="trembles and blurts information",
            scope="public",
        ),
    ],
)


ALL_ARCHETYPES: dict[str, NpcArchetype] = {
    a.archetype_id: a
    for a in [
        SUSPICIOUS_MERCHANT,
        LOYAL_GUARD,
        MYSTERIOUS_SAGE,
        COWARDLY_MINION,
    ]
}


def get_archetype(archetype_id: str) -> NpcArchetype:
    """Look up an NPC archetype by ID.  Raises KeyError if not found."""
    return ALL_ARCHETYPES[archetype_id]


# ---------------------------------------------------------------------------
# Monster Templates
# ---------------------------------------------------------------------------


@dataclass
class MonsterTemplate:
    """Reusable monster group configuration."""

    template_id: str
    unit_type: str
    default_behavior_mode: str
    default_awareness_state: str
    default_stats: dict[str, int]
    default_special_rules: list[str] = field(default_factory=list)

    def instantiate(
        self,
        monster_id: str,
        scene_id: str = "",
        count: int = 1,
        **overrides: object,
    ) -> MonsterDefinition:
        """Create a MonsterDefinition from this template."""
        stats = dict(overrides.get("stats", self.default_stats) or self.default_stats)  # type: ignore[arg-type]
        rules = list(
            overrides.get("special_rules", self.default_special_rules)
            or self.default_special_rules  # type: ignore[arg-type]
        )

        return MonsterDefinition(
            monster_id=monster_id,
            unit_type=self.unit_type,
            count=count,
            behavior_mode=str(
                overrides.get("behavior_mode", self.default_behavior_mode)
            ),
            awareness_state=str(
                overrides.get("awareness_state", self.default_awareness_state)
            ),
            stats=stats,
            special_rules=rules,
            territory_id=str(overrides.get("territory_id", "")),
            scene_id=scene_id,
            loot_item_ids=list(overrides.get("loot_item_ids", []) or []),  # type: ignore[arg-type]
            referee_notes=str(overrides.get("referee_notes", "")),
        )


GOBLIN_PATROL = MonsterTemplate(
    template_id="goblin_patrol",
    unit_type="goblin",
    default_behavior_mode="patrol",
    default_awareness_state="alert",
    default_stats={"attack": 4, "defense": 1, "hp_per_unit": 5},
)

SKELETON_GUARD = MonsterTemplate(
    template_id="skeleton_guard",
    unit_type="skeleton",
    default_behavior_mode="guard",
    default_awareness_state="unaware",
    default_stats={"attack": 5, "defense": 3, "hp_per_unit": 8},
    default_special_rules=["immune_to_morale"],
)

WOLF_PACK = MonsterTemplate(
    template_id="wolf_pack",
    unit_type="wolf",
    default_behavior_mode="pursue",
    default_awareness_state="aware",
    default_stats={"attack": 6, "defense": 1, "hp_per_unit": 6},
    default_special_rules=["pack_tactics"],
)

BANDIT_GROUP = MonsterTemplate(
    template_id="bandit_group",
    unit_type="bandit",
    default_behavior_mode="ambush",
    default_awareness_state="alert",
    default_stats={"attack": 5, "defense": 2, "hp_per_unit": 7},
    default_special_rules=["leader_dead_routs"],
)

SPIDER_SWARM = MonsterTemplate(
    template_id="spider_swarm",
    unit_type="spider",
    default_behavior_mode="ambush",
    default_awareness_state="unaware",
    default_stats={"attack": 3, "defense": 0, "hp_per_unit": 3},
    default_special_rules=["poison_bite"],
)


ALL_TEMPLATES: dict[str, MonsterTemplate] = {
    t.template_id: t
    for t in [
        GOBLIN_PATROL,
        SKELETON_GUARD,
        WOLF_PACK,
        BANDIT_GROUP,
        SPIDER_SWARM,
    ]
}


def get_template(template_id: str) -> MonsterTemplate:
    """Look up a monster template by ID.  Raises KeyError if not found."""
    return ALL_TEMPLATES[template_id]
