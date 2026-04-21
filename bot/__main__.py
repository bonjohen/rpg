"""Run the bot: python -m bot

Reads BOT_TOKEN from the environment.  If WEBHOOK_URL is set, runs in
webhook mode; otherwise long-polling (development default).
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

from bot.config import BotConfig
from bot.gateway import build_app, run_polling, run_webhook
from bot.mapping import BotRegistry
from models.fast.adapter import OllamaFastAdapter
from models.main.adapter import OpenAIMainAdapter
from server.orchestrator.game_loop import GameOrchestrator
from server.storage.db import create_all_tables, get_engine, get_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()
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

    # Database
    engine = get_engine()
    create_all_tables(engine)
    session_factory = get_session_factory(engine)

    # Model adapters
    fast_adapter = OllamaFastAdapter()
    main_adapter = OpenAIMainAdapter()

    # Game orchestrator
    registry = BotRegistry()
    orchestrator = GameOrchestrator(
        fast_adapter=fast_adapter,
        main_adapter=main_adapter,
        bot_registry=registry,
        config=config,
        session_factory=session_factory,
    )
    logger.info("Game orchestrator initialized (db=%s)", engine.url)

    app = build_app(token=token, config=config)
    app.bot_data["orchestrator"] = orchestrator
    app.bot_data["registry"] = registry

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
