"""User-to-player and chat-to-campaign mapping.

The BotRegistry is the runtime lookup table between Telegram identities and
game domain IDs.  It is intentionally thin: it holds the mapping and raises
well-typed exceptions on misses.  Persistence (loading from DB on startup,
updating on join) is the caller's responsibility.
"""

from __future__ import annotations


class UnknownUserError(Exception):
    """Raised when a Telegram user_id has no player mapping."""


class UnknownChatError(Exception):
    """Raised when a Telegram chat_id has no campaign mapping."""


class BotRegistry:
    """In-memory mapping between Telegram identities and domain IDs.

    Thread-safety: not required for the asyncio single-thread model PTB uses.

    Example::

        registry = BotRegistry()
        registry.register_player(telegram_user_id=123, player_id="uuid-abc")
        registry.register_campaign(telegram_chat_id=-100999, campaign_id="uuid-xyz")

        player_id = registry.player_id_for(123)
        campaign_id = registry.campaign_id_for(-100999)
    """

    def __init__(self) -> None:
        self._user_to_player: dict[int, str] = {}
        self._chat_to_campaign: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_player(self, telegram_user_id: int, player_id: str) -> None:
        """Map ``telegram_user_id`` → ``player_id``."""
        self._user_to_player[telegram_user_id] = player_id

    def unregister_player(self, telegram_user_id: int) -> None:
        """Remove a player mapping (used in tests and admin operations)."""
        self._user_to_player.pop(telegram_user_id, None)

    def register_campaign(self, telegram_chat_id: int, campaign_id: str) -> None:
        """Map ``telegram_chat_id`` → ``campaign_id``."""
        self._chat_to_campaign[telegram_chat_id] = campaign_id

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def player_id_for(self, telegram_user_id: int) -> str:
        """Return the player_id for a Telegram user.

        Raises UnknownUserError if no mapping exists.
        """
        try:
            return self._user_to_player[telegram_user_id]
        except KeyError:
            raise UnknownUserError(
                f"Telegram user {telegram_user_id} has no player mapping. "
                "The user must complete onboarding (/join) first."
            )

    def campaign_id_for(self, telegram_chat_id: int) -> str:
        """Return the campaign_id for a Telegram chat.

        Raises UnknownChatError if no mapping exists.
        """
        try:
            return self._chat_to_campaign[telegram_chat_id]
        except KeyError:
            raise UnknownChatError(
                f"Telegram chat {telegram_chat_id} has no campaign mapping."
            )

    def is_known_player(self, telegram_user_id: int) -> bool:
        """Return True if the user has a player mapping."""
        return telegram_user_id in self._user_to_player

    def get_user_id_for_player(self, player_id: str) -> int | None:
        """Reverse lookup: return the Telegram user_id for a game player_id.

        Returns None if no mapping exists.
        """
        for tg_uid, pid in self._user_to_player.items():
            if pid == player_id:
                return tg_uid
        return None

    def is_known_chat(self, telegram_chat_id: int) -> bool:
        """Return True if the chat has a campaign mapping."""
        return telegram_chat_id in self._chat_to_campaign
