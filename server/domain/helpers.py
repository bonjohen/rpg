"""Shared utility helpers for timestamps and ID generation.

Centralises the ``utc_now`` and ``new_id`` helpers that were previously
duplicated across 18+ modules.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    """Return a new random UUID as a string."""
    return str(uuid.uuid4())
