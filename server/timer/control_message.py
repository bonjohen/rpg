"""Public turn-control message builder.

There is exactly ONE turn-control message per active TurnWindow, posted to the
campaign's public play topic.  It is edited in-place as the timer counts down
and player readiness changes.

This module is pure domain logic: it produces message text and InlineKeyboard
data.  Telegram sends are the caller's responsibility.

Inline button callback data format:
    "<action>:<turn_window_id>"

Actions:
    ready   — Player marks themselves ready
    pass    — Player passes this turn
    askref  — Player asks the referee a question (opens DM)
    revise  — Player wants to revise their submitted action
    submit  — Player confirms final action submission
"""

from __future__ import annotations

from dataclasses import dataclass, field

from server.domain.enums import ReadyState


# ---------------------------------------------------------------------------
# Callback data constants
# ---------------------------------------------------------------------------

ACTION_READY = "ready"
ACTION_PASS = "pass"
ACTION_ASKREF = "askref"
ACTION_REVISE = "revise"
ACTION_SUBMIT = "submit"


# ---------------------------------------------------------------------------
# Player readiness summary
# ---------------------------------------------------------------------------


@dataclass
class PlayerReadinessEntry:
    """One player's readiness status for the control message."""

    player_id: str
    display_name: str
    ready_state: ReadyState = ReadyState.not_ready


# ---------------------------------------------------------------------------
# Control message data
# ---------------------------------------------------------------------------


@dataclass
class ControlMessageData:
    """All data needed to render the turn-control message."""

    turn_window_id: str
    turn_number: int
    seconds_remaining: int
    is_paused: bool = False
    is_locked: bool = False
    players: list[PlayerReadinessEntry] = field(default_factory=list)
    situation_summary: str = ""  # Short scene situation (from last narration)


# ---------------------------------------------------------------------------
# Inline keyboard button
# ---------------------------------------------------------------------------


@dataclass
class InlineButton:
    text: str
    callback_data: str


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class ControlMessageBuilder:
    """Builds turn-control message text and inline keyboard layout."""

    def build_text(self, data: ControlMessageData) -> str:
        """Return the message text for the turn-control message."""
        lines: list[str] = []

        # Header
        lines.append(f"<b>Turn {data.turn_number}</b>")

        if data.situation_summary:
            lines.append(data.situation_summary)

        lines.append("")

        # Timer line
        if data.is_locked:
            lines.append("🔒 <i>Turn locked — resolving…</i>")
        elif data.is_paused:
            lines.append("⏸ <i>Timer paused</i>")
        else:
            mins, secs = divmod(data.seconds_remaining, 60)
            lines.append(f"⏱ <b>{mins:02d}:{secs:02d}</b> remaining")

        lines.append("")

        # Player readiness list
        if data.players:
            lines.append("<b>Players:</b>")
            for entry in data.players:
                icon = _readiness_icon(entry.ready_state)
                lines.append(f"  {icon} {entry.display_name}")

        return "\n".join(lines)

    def build_keyboard(
        self,
        turn_window_id: str,
        is_locked: bool = False,
    ) -> list[list[InlineButton]]:
        """Return rows of inline buttons.

        Returns an empty keyboard when the turn is locked (no more input).
        """
        if is_locked:
            return []

        def _btn(text: str, action: str) -> InlineButton:
            return InlineButton(
                text=text,
                callback_data=f"{action}:{turn_window_id}",
            )

        return [
            [_btn("✅ Ready", ACTION_READY), _btn("⏭ Pass", ACTION_PASS)],
            [_btn("❓ Ask Ref", ACTION_ASKREF), _btn("✏️ Revise", ACTION_REVISE)],
            [_btn("📨 Submit", ACTION_SUBMIT)],
        ]

    def parse_callback_data(self, data: str) -> tuple[str, str]:
        """Parse callback_data into (action, turn_window_id).

        Raises ValueError if the format is invalid.
        """
        parts = data.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid callback data: {data!r}")
        return parts[0], parts[1]


def _readiness_icon(state: ReadyState) -> str:
    return {
        ReadyState.ready: "✅",
        ReadyState.passed: "⏭",
        ReadyState.not_ready: "⏳",
    }.get(state, "⏳")
