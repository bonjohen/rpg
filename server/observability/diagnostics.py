"""Admin diagnostics for stuck turns, failed deliveries, and model health.

Assembles a DiagnosticReport from campaign state and formats it as
human-readable text for admin DM delivery.

All stdlib — no external dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.fast.instrumentation import ModelCallLog
from server.domain.entities import Player, Scene, TurnWindow
from server.domain.enums import TurnWindowState
from server.reliability.telegram_retry import DeliveryResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


@dataclass
class StuckTurnInfo:
    """Diagnostic info about a single stuck turn."""

    turn_window_id: str
    scene_id: str
    state: str
    age_minutes: float
    pending_players: list[str] = field(default_factory=list)
    recommended_action: str = ""  # "wait", "force_resolve", "abort"


@dataclass
class FailedDeliveryInfo:
    """Diagnostic info about a failed delivery."""

    target: str  # "public:{scene_id}" or "private:{player_id}"
    last_attempt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str = ""
    retry_count: int = 0


@dataclass
class ModelHealthInfo:
    """Diagnostic info about model health."""

    fast_model_responsive: bool = True
    main_model_responsive: bool = True
    fast_avg_latency_ms: float = 0.0
    main_avg_latency_ms: float = 0.0
    recent_failures: int = 0
    recent_fallbacks: int = 0


@dataclass
class PlayerStatusInfo:
    """Diagnostic info about a player."""

    player_id: str
    display_name: str = ""
    has_dm_open: bool = False
    current_scene_id: str = ""
    pending_action: bool = False


@dataclass
class DiagnosticReport:
    """Full diagnostic report for a campaign."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    campaign_id: str = ""
    stuck_turns: list[StuckTurnInfo] = field(default_factory=list)
    failed_deliveries: list[FailedDeliveryInfo] = field(default_factory=list)
    model_health: ModelHealthInfo = field(default_factory=ModelHealthInfo)
    player_status: list[PlayerStatusInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DiagnosticsEngine
# ---------------------------------------------------------------------------


class DiagnosticsEngine:
    """Assembles diagnostic reports from campaign state."""

    def build_report(
        self,
        campaign_id: str,
        turn_windows: list[TurnWindow],
        scenes: list[Scene],
        players: list[Player],
        delivery_log: list[DeliveryResult] | None = None,
        model_call_log: list[ModelCallLog] | None = None,
    ) -> DiagnosticReport:
        """Assemble a full diagnostic report."""
        delivery_log = delivery_log or []
        model_call_log = model_call_log or []

        stuck = self._find_stuck_turns(turn_windows, scenes, players)
        failed = self._find_failed_deliveries(delivery_log)
        health = self._compute_model_health(model_call_log)
        statuses = self._compute_player_status(players, scenes, turn_windows)

        return DiagnosticReport(
            campaign_id=campaign_id,
            stuck_turns=stuck,
            failed_deliveries=failed,
            model_health=health,
            player_status=statuses,
        )

    def _find_stuck_turns(
        self,
        turn_windows: list[TurnWindow],
        scenes: list[Scene],
        players: list[Player],
        max_age_minutes: int = 30,
        committed_actions: list | None = None,
    ) -> list[StuckTurnInfo]:
        """Identify turn windows stuck in non-terminal states."""
        now = datetime.now(timezone.utc)
        stuck_states = {
            TurnWindowState.open,
            TurnWindowState.all_ready,
            TurnWindowState.locked,
            TurnWindowState.resolving,
        }

        scene_map = {s.scene_id: s for s in scenes}
        results: list[StuckTurnInfo] = []

        for tw in turn_windows:
            if tw.state not in stuck_states:
                continue

            opened = tw.opened_at
            if opened.tzinfo is None:
                age_seconds = (now.replace(tzinfo=None) - opened).total_seconds()
            else:
                age_seconds = (now - opened).total_seconds()
            age_minutes = age_seconds / 60.0

            if age_minutes <= max_age_minutes:
                continue

            # Determine pending players
            scene = scene_map.get(tw.scene_id)
            scene_players = scene.player_ids if scene else []
            # Filter out players who have already submitted actions
            if committed_actions:
                submitted_ids = {
                    a.player_id
                    for a in committed_actions
                    if a.turn_window_id == tw.turn_window_id
                }
                pending = [pid for pid in scene_players if pid not in submitted_ids]
            else:
                pending = list(scene_players)

            # Recommend action based on state and age
            if age_minutes > 60:
                recommended = "abort"
            elif tw.state in {TurnWindowState.locked, TurnWindowState.resolving}:
                recommended = "force_resolve"
            else:
                recommended = "wait"

            results.append(
                StuckTurnInfo(
                    turn_window_id=tw.turn_window_id,
                    scene_id=tw.scene_id,
                    state=tw.state.value,
                    age_minutes=round(age_minutes, 1),
                    pending_players=pending,
                    recommended_action=recommended,
                )
            )

        return results

    def _find_failed_deliveries(
        self, delivery_log: list[DeliveryResult]
    ) -> list[FailedDeliveryInfo]:
        """Extract failed deliveries from the delivery log."""
        failed: list[FailedDeliveryInfo] = []
        for dr in delivery_log:
            if dr.success:
                continue
            last_attempt = dr.attempts[-1] if dr.attempts else None
            error_msg = last_attempt.error if last_attempt else "unknown"
            status = last_attempt.http_status if last_attempt else 0
            failed.append(
                FailedDeliveryInfo(
                    target=f"trace:{dr.trace_id}" if dr.trace_id else "unknown",
                    error=f"{status} {error_msg}" if status else error_msg,
                    retry_count=len(dr.attempts),
                )
            )
        return failed

    def _compute_model_health(
        self, model_call_log: list[ModelCallLog]
    ) -> ModelHealthInfo:
        """Compute model health from recent call logs."""
        if not model_call_log:
            return ModelHealthInfo()

        fast_latencies: list[float] = []
        main_latencies: list[float] = []
        failures = 0
        fallbacks = 0

        for log in model_call_log:
            if not log.success:
                failures += 1
            if log.fallback_triggered:
                fallbacks += 1
            if log.tier == "fast":
                fast_latencies.append(log.latency_ms)
            else:
                main_latencies.append(log.latency_ms)

        total = len(model_call_log)
        failure_rate = failures / total if total else 0.0
        return ModelHealthInfo(
            fast_model_responsive=bool(fast_latencies) and failure_rate < 0.5,
            main_model_responsive=bool(main_latencies) and failure_rate < 0.5,
            fast_avg_latency_ms=(
                sum(fast_latencies) / len(fast_latencies) if fast_latencies else 0.0
            ),
            main_avg_latency_ms=(
                sum(main_latencies) / len(main_latencies) if main_latencies else 0.0
            ),
            recent_failures=failures,
            recent_fallbacks=fallbacks,
        )

    def _compute_player_status(
        self,
        players: list[Player],
        scenes: list[Scene],
        turn_windows: list[TurnWindow],
    ) -> list[PlayerStatusInfo]:
        """Compute per-player status."""
        # Build scene lookup for active turn windows
        active_tw_scenes: set[str] = set()
        for tw in turn_windows:
            if tw.state in {TurnWindowState.open, TurnWindowState.all_ready}:
                active_tw_scenes.add(tw.scene_id)

        # Build player -> scene mapping from scene membership
        player_scene_map: dict[str, str] = {}
        for scene in scenes:
            for pid in scene.player_ids:
                player_scene_map[pid] = scene.scene_id

        results: list[PlayerStatusInfo] = []
        for player in players:
            scene_id = player_scene_map.get(player.player_id, "")
            pending = scene_id in active_tw_scenes
            results.append(
                PlayerStatusInfo(
                    player_id=player.player_id,
                    display_name=player.display_name,
                    has_dm_open=player.has_dm_open,
                    current_scene_id=scene_id,
                    pending_action=pending,
                )
            )
        return results

    def format_report(self, report: DiagnosticReport) -> str:
        """Format a DiagnosticReport as human-readable text for admin DM."""
        lines: list[str] = []
        lines.append("=== Campaign Diagnostics ===")
        lines.append(f"Campaign: {report.campaign_id}")
        lines.append(f"Time: {report.timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
        lines.append("")

        # Stuck turns
        lines.append(f"Stuck turns: {len(report.stuck_turns)}")
        for st in report.stuck_turns:
            lines.append(
                f"  - Turn {st.turn_window_id[:8]} in scene {st.scene_id[:8]} "
                f"({st.age_minutes:.0f} min, state={st.state})"
            )
            lines.append(f"    Recommended: {st.recommended_action}")
        lines.append("")

        # Failed deliveries
        lines.append(f"Failed deliveries: {len(report.failed_deliveries)}")
        for fd in report.failed_deliveries:
            lines.append(f"  - {fd.target} -- {fd.error} ({fd.retry_count} retries)")
        lines.append("")

        # Model health
        mh = report.model_health
        fast_status = "OK" if mh.fast_model_responsive else "DOWN"
        main_status = "OK" if mh.main_model_responsive else "DOWN"
        lines.append(
            f"Model health: fast {fast_status} "
            f"(avg {mh.fast_avg_latency_ms:.0f}ms), "
            f"main {main_status} (avg {mh.main_avg_latency_ms:.0f}ms)"
        )
        lines.append(
            f"  Recent failures: {mh.recent_failures}, fallbacks: {mh.recent_fallbacks}"
        )
        lines.append("")

        # Players
        active_count = sum(1 for p in report.player_status if p.current_scene_id)
        pending_count = sum(1 for p in report.player_status if p.pending_action)
        lines.append(f"Players: {active_count} active, {pending_count} pending action")

        return "\n".join(lines)
