"""BotConfig dataclass — separated to avoid circular imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BotConfig:
    """Runtime configuration for the bot gateway."""

    token: str = ""
    # Telegram chat ID of the campaign supergroup
    group_chat_id: int = 0
    # message_thread_id of the main play topic inside the supergroup
    play_topic_id: int | None = None
    # Webhook URL (empty → use polling)
    webhook_url: str = ""
    webhook_port: int = 8443
    # Extra kwargs forwarded verbatim to ApplicationBuilder
    builder_kwargs: dict = field(default_factory=dict)
