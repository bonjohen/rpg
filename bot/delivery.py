"""Turn result delivery: narration generation and Telegram posting.

After turn resolution, this module:
1. Calls the main model for rich narration (falling back to basic text)
2. Posts public narration to the group chat
3. Sends private facts to individual player DMs
"""

from __future__ import annotations

import logging

from telegram import Bot

from bot.config import BotConfig
from bot.mapping import BotRegistry, UnknownUserError
from bot.outbound import send_private_by_player_id, send_public
from models.main.context import ActionContext, SceneContext
from models.main.tasks import narrate_scene
from models.protocol import MainAdapter
from server.domain.entities import Scene, TurnLogEntry

logger = logging.getLogger(__name__)


async def generate_narration(
    main_adapter: MainAdapter | None,
    turn_log_entry: TurnLogEntry,
    scene: Scene,
    committed_actions: list[ActionContext],
) -> str:
    """Generate rich narration via the main model, with fallback.

    Falls back to turn_log_entry.narration (basic concatenated text) if:
    - No main adapter configured
    - Main model call fails or times out
    """
    if main_adapter is None:
        return turn_log_entry.narration or "The turn resolves."

    scene_ctx = SceneContext(
        scene_id=scene.scene_id,
        location_name=scene.name,
        description=scene.description,
    )

    try:
        output, _ = await narrate_scene(
            main_adapter,
            scene_ctx,
            committed_actions,
        )
        return output.narration or turn_log_entry.narration
    except Exception:
        logger.exception("Main model narration failed, using fallback")
        return turn_log_entry.narration or "The turn resolves."


async def deliver_turn_results(
    turn_log_entry: TurnLogEntry,
    scene: Scene,
    narration_text: str,
    bot: Bot,
    config: BotConfig,
    registry: BotRegistry,
    private_facts: list[tuple[str, str]] | None = None,
) -> None:
    """Post turn results to Telegram.

    Args:
        turn_log_entry: The resolved turn log entry.
        scene: The scene where the turn resolved.
        narration_text: Pre-generated narration text.
        bot: PTB Bot instance.
        config: Bot configuration.
        registry: Player-Telegram ID mapping.
        private_facts: List of (player_id, fact_text) tuples for private delivery.
    """
    # Post public narration
    try:
        header = f"Turn {turn_log_entry.turn_number} resolved.\n\n"
        await send_public(bot, config, header + narration_text)
    except Exception:
        logger.exception("Failed to send public narration")

    # Send private facts to individual players
    if private_facts:
        for player_id, fact_text in private_facts:
            try:
                await send_private_by_player_id(bot, registry, player_id, fact_text)
            except (UnknownUserError, Exception) as exc:
                logger.error(
                    "Failed to send private fact to player_id=%s: %s",
                    player_id,
                    exc,
                )
