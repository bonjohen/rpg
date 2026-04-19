"""Structured logging with trace IDs.

Provides TraceContext for request-scoped tracing, a JSON-structured logging
formatter, and a context-variable-based filter that attaches trace fields
to every log record automatically.

All stdlib — no external dependencies.
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.config
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# TraceContext
# ---------------------------------------------------------------------------


@dataclass
class TraceContext:
    """Per-request tracing context.

    Created once per incoming request/turn, then propagated through child spans.
    Stored in a contextvar so any code in the same async task can access it.
    """

    trace_id: str
    campaign_id: str = ""
    scene_id: str = ""
    turn_window_id: str = ""
    player_id: str = ""
    span: str = ""

    @classmethod
    def new(
        cls,
        campaign_id: str = "",
        scene_id: str = "",
        turn_window_id: str = "",
        player_id: str = "",
    ) -> TraceContext:
        """Create a new TraceContext with a fresh trace_id."""
        return cls(
            trace_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            scene_id=scene_id,
            turn_window_id=turn_window_id,
            player_id=player_id,
        )

    def child(self, span: str) -> TraceContext:
        """Create a child context sharing the same trace_id but with a new span."""
        return TraceContext(
            trace_id=self.trace_id,
            campaign_id=self.campaign_id,
            scene_id=self.scene_id,
            turn_window_id=self.turn_window_id,
            player_id=self.player_id,
            span=span,
        )

    def to_dict(self) -> dict:
        """Return a flat dict suitable for merging into log records."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Context variable for current trace
# ---------------------------------------------------------------------------

_current_trace: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "current_trace", default=None
)


def set_current_trace(ctx: TraceContext) -> contextvars.Token:
    """Store a TraceContext in the current task's contextvar."""
    return _current_trace.set(ctx)


def get_current_trace() -> TraceContext | None:
    """Retrieve the current TraceContext, or None if not set."""
    return _current_trace.get()


def clear_current_trace(token: contextvars.Token) -> None:
    """Reset the contextvar to its previous value."""
    _current_trace.reset(token)


# ---------------------------------------------------------------------------
# Structured JSON formatter
# ---------------------------------------------------------------------------


class StructuredJsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Fields: timestamp, level, logger, message, plus any TraceContext fields
    attached by TraceFilter.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach trace fields if present
        for key in (
            "trace_id",
            "campaign_id",
            "scene_id",
            "turn_window_id",
            "player_id",
            "span",
        ):
            val = getattr(record, key, "")
            if val:
                log_data[key] = val

        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


# ---------------------------------------------------------------------------
# TraceFilter — attaches TraceContext fields to log records
# ---------------------------------------------------------------------------


class TraceFilter(logging.Filter):
    """Logging filter that injects TraceContext fields into every record.

    Uses the contextvar to find the current TraceContext. If none is set,
    fields default to empty strings.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _current_trace.get()
        if ctx is not None:
            record.trace_id = ctx.trace_id  # type: ignore[attr-defined]
            record.campaign_id = ctx.campaign_id  # type: ignore[attr-defined]
            record.scene_id = ctx.scene_id  # type: ignore[attr-defined]
            record.turn_window_id = ctx.turn_window_id  # type: ignore[attr-defined]
            record.player_id = ctx.player_id  # type: ignore[attr-defined]
            record.span = ctx.span  # type: ignore[attr-defined]
        else:
            record.trace_id = ""  # type: ignore[attr-defined]
            record.campaign_id = ""  # type: ignore[attr-defined]
            record.scene_id = ""  # type: ignore[attr-defined]
            record.turn_window_id = ""  # type: ignore[attr-defined]
            record.player_id = ""  # type: ignore[attr-defined]
            record.span = ""  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_configured = False


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure the root logger with structured JSON output and TraceFilter.

    Safe to call multiple times; only the first call takes effect.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [%(trace_id)s] %(message)s"
            )
        )
    handler.addFilter(TraceFilter())
    root.addHandler(handler)


def reset_logging_config() -> None:
    """Reset the configured flag so configure_logging can be called again.

    For testing only.
    """
    global _configured
    _configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name.

    If configure_logging has not been called, the logger will still work
    with Python's default configuration.
    """
    return logging.getLogger(name)
