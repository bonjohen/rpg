"""Battlefield summary builder for public turn posts."""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.entities import Character, MonsterGroup


@dataclass
class BattlefieldSummary:
    round_number: int
    combatant_lines: list[str] = field(default_factory=list)
    event_lines: list[str] = field(default_factory=list)
    status_line: str = "Combat ongoing"


class BattlefieldSummaryBuilder:
    """Assembles a text summary of the current combat state."""

    def build(
        self,
        characters: list[Character],
        groups: list[MonsterGroup],
        turn_number: int,
        action_results: list[str] | None = None,
        combat_status: str = "Combat ongoing",
    ) -> BattlefieldSummary:
        combatant_lines: list[str] = []

        # Character lines
        for c in characters:
            hp = c.stats.get("hp", 0)
            max_hp = c.stats.get("max_hp", hp)
            effects = c.status_effects
            line = f"{c.name} — {hp}/{max_hp} HP"
            if effects:
                line += f" — [{', '.join(effects)}]"
            if not c.is_alive:
                line += " — DEFEATED"
            combatant_lines.append(line)

        # Monster group lines
        for g in groups:
            if not g.is_visible:
                continue
            line = f"{g.unit_type} (x{g.count}) — {g.health_state}"
            if g.morale_state != "steady":
                line += f" — {g.morale_state}"
            combatant_lines.append(line)

        return BattlefieldSummary(
            round_number=turn_number,
            combatant_lines=combatant_lines,
            event_lines=action_results or [],
            status_line=combat_status,
        )
