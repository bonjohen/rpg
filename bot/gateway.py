"""Telegram Bot Gateway — entry point.

Creates the PTB Application, registers all handlers, and exposes run()
for both polling (dev) and webhook (prod) modes.

Usage:
    from bot.gateway import build_app, run_polling

    app = build_app(token="...", config=BotConfig(...))
    run_polling(app)
"""

from __future__ import annotations

import logging

from telegram.ext import Application, ApplicationBuilder

from bot.config import BotConfig
from bot.handlers import register_handlers

logger = logging.getLogger(__name__)


def build_app(token: str, config: BotConfig | None = None) -> Application:
    """Build and return a configured PTB Application.

    Registers all handlers.  Does not start the event loop.
    """
    cfg = config or BotConfig(token=token)
    cfg.token = token  # explicit token always wins

    builder = ApplicationBuilder().token(token)
    for key, value in cfg.builder_kwargs.items():
        getattr(builder, key)(value)

    app = builder.build()
    # Attach config so handlers can read it
    app.bot_data["config"] = cfg

    register_handlers(app)
    logger.info("Bot application built (chat_id=%s)", cfg.group_chat_id)
    return app


def run_polling(app: Application) -> None:
    """Start the bot in long-polling mode (blocking)."""
    logger.info("Starting bot in polling mode")
    app.run_polling(drop_pending_updates=True)


def run_webhook(app: Application, config: BotConfig) -> None:
    """Start the bot in webhook mode (blocking)."""
    if not config.webhook_url:
        raise ValueError("webhook_url must be set in BotConfig for webhook mode")
    logger.info("Starting bot in webhook mode url=%s", config.webhook_url)
    app.run_webhook(
        listen="0.0.0.0",
        port=config.webhook_port,
        webhook_url=config.webhook_url,
        drop_pending_updates=True,
    )
