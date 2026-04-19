"""Duplicate-delivery and replay protection.

In-memory store of processed message/update IDs to prevent duplicate handling.
Uses collections.OrderedDict for efficient LRU-style eviction.

All stdlib — no external dependencies.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# IdempotencyStore
# ---------------------------------------------------------------------------


class IdempotencyStore:
    """In-memory store of processed keys to prevent duplicate handling.

    Keys are stored with timestamps. Eviction happens on two criteria:
      - TTL: entries older than ttl_seconds are evicted on access.
      - Max size: oldest entries evicted when store exceeds max_size.
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._seen: OrderedDict[str, datetime] = OrderedDict()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _evict_expired(self) -> None:
        """Remove entries older than ttl_seconds."""
        if not self._seen:
            return
        cutoff = self._now().timestamp() - self.ttl_seconds
        # Evict from the front (oldest entries)
        keys_to_remove = []
        for key, ts in self._seen.items():
            if ts.timestamp() < cutoff:
                keys_to_remove.append(key)
            else:
                break  # OrderedDict is insertion-ordered; rest are newer
        for key in keys_to_remove:
            del self._seen[key]

    def _evict_overflow(self) -> None:
        """Remove oldest entries if store exceeds max_size."""
        while len(self._seen) > self.max_size:
            self._seen.popitem(last=False)

    def mark_seen(self, key: str) -> bool:
        """Mark a key as seen.

        Returns True if this is the FIRST time seeing this key (not a duplicate).
        Returns False if already seen (duplicate).
        """
        self._evict_expired()

        if key in self._seen:
            return False

        self._seen[key] = self._now()
        self._evict_overflow()
        return True

    def is_seen(self, key: str) -> bool:
        """Check if a key has been seen, without marking it."""
        self._evict_expired()
        return key in self._seen

    def clear(self) -> None:
        """Reset the store (for testing)."""
        self._seen.clear()

    @property
    def size(self) -> int:
        """Current number of entries."""
        return len(self._seen)


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------


def telegram_update_key(update_id: int) -> str:
    """Generate an idempotency key for a Telegram update."""
    return f"tg_update:{update_id}"


def turn_action_key(turn_window_id: str, player_id: str) -> str:
    """Generate an idempotency key for a turn action submission."""
    return f"turn_action:{turn_window_id}:{player_id}"


def delivery_key(campaign_id: str, scene_id: str, turn_number: int, scope: str) -> str:
    """Generate an idempotency key for a narration delivery."""
    return f"delivery:{campaign_id}:{scene_id}:{turn_number}:{scope}"
