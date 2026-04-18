"""Run the bot: python -m bot

Reads BOT_TOKEN from the environment.  If WEBHOOK_URL is set, runs in
webhook mode; otherwise long-polling (development default).
"""

from __future__ import annotations

import logging
import os
import sys

from bot.config import BotConfig
from bot.gateway import build_app, run_polling, run_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        logger.error("BOT_TOKEN environment variable is not set")
        sys.exit(1)

    config = BotConfig(
        token=token,
        group_chat_id=int(os.environ.get("GROUP_CHAT_ID", "0")),
        play_topic_id=_int_or_none(os.environ.get("PLAY_TOPIC_ID")),
        webhook_url=os.environ.get("WEBHOOK_URL", ""),
        webhook_port=int(os.environ.get("WEBHOOK_PORT", "8443")),
    )

    app = build_app(token=token, config=config)

    if config.webhook_url:
        run_webhook(app, config)
    else:
        run_polling(app)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


if __name__ == "__main__":
    main()
