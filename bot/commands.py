"""Slash command handlers: /start, /join, /help, /status, and game commands.

Each handler is an async PTB callback.  They are registered onto the
Application in handlers.py via CommandHandler.

The registry is retrieved from application.bot_data["registry"]; the config
from application.bot_data["config"].  Both are injected at startup.
The orchestrator is from application.bot_data["orchestrator"] (Phase 16+).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.mapping import BotRegistry, UnknownUserError
from bot.onboarding import ONBOARDING_MESSAGES, ONBOARDING_PROMPT

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "Available commands:\n"
    "  /start       — Start a conversation with the bot\n"
    "  /join        — Register as a player (send this in the group)\n"
    "  /help        — Show this message\n"
    "  /status      — Show your current game status\n"
    "  /newgame     — Load a scenario (admin)\n"
    "  /nextturn    — Open next turn (admin/debug)\n"
    "  /forceresolve — Force-resolve current turn (admin/debug)\n"
    "  /diagnostics — Show diagnostics report (admin)\n"
    "  /scene       — Show current scene\n"
    "  /who         — Show who is in which scene\n"
)


def _registry(context: ContextTypes.DEFAULT_TYPE) -> BotRegistry:
    return context.application.bot_data.get("registry", BotRegistry())


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — greet the user and prompt onboarding if needed."""
    user = update.effective_user
    registry = _registry(context)

    if not registry.is_known_player(user.id):
        await update.message.reply_text(
            f"Hello, {user.first_name}!\n\n{ONBOARDING_PROMPT}"
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {user.first_name}! You're registered as a player.\n"
            "Use /help to see available commands."
        )


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/join — register the sender as a player in the current campaign.

    Must be sent from the campaign supergroup; the chat_id is used to look
    up the campaign.  If the user is already registered, confirm idempotently.
    """
    user = update.effective_user
    registry = _registry(context)

    if update.message.chat.type == "private":
        await update.message.reply_text(ONBOARDING_MESSAGES["join_in_group"])
        return

    if registry.is_known_player(user.id):
        orchestrator = _orchestrator(context)
        if orchestrator:
            player_id = registry.player_id_for(user.id)
            char = orchestrator.get_player_character(player_id)
            scene = orchestrator.get_player_scene(player_id)
            if char and scene:
                await update.message.reply_text(
                    ONBOARDING_MESSAGES["already_joined"].format(
                        name=char.name, scene=scene.name
                    )
                )
                return
        await update.message.reply_text(
            f"You're already registered, {user.first_name}. Good to go!"
        )
        return

    # Stub: in Phase 3 we create a minimal player record and register it.
    # Full character creation happens in later phases.
    import uuid

    player_id = str(uuid.uuid4())
    registry.register_player(user.id, player_id)

    logger.info("Player joined: telegram_user_id=%s player_id=%s", user.id, player_id)
    await update.message.reply_text(
        f"Welcome, {user.first_name}! You've been registered as a player.\n"
        "You can now DM me directly for private game actions."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — show the command list."""
    await update.message.reply_text(_HELP_TEXT)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — show the player's current game state (stub)."""
    user = update.effective_user
    registry = _registry(context)

    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await update.message.reply_text(ONBOARDING_MESSAGES["not_joined"])
        return

    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(
            f"Player ID: {player_id}\nStatus: registered (no active game)"
        )
        return

    scene = orchestrator.get_player_scene(player_id)
    if scene is None:
        await update.message.reply_text(
            f"Player ID: {player_id}\nStatus: registered, not in a scene"
        )
        return

    char = orchestrator.get_player_character(player_id)
    char_info = f"Character: {char.name}" if char else ""
    await update.message.reply_text(
        f"Player ID: {player_id}\n{char_info}\nScene: {scene.name}\nState: {scene.state.value}"
    )


def _orchestrator(context: ContextTypes.DEFAULT_TYPE):
    """Get the GameOrchestrator from bot_data, or None."""
    return context.application.bot_data.get("orchestrator")


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/newgame <scenario_path> — load a scenario and start a campaign."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /newgame <scenario_path>")
        return

    scenario_path = args[0]
    success = orchestrator.load_scenario(scenario_path)
    if success:
        scene_count = len(orchestrator.scenes)
        await update.message.reply_text(
            f"Scenario loaded! {scene_count} scenes ready.\n"
            "Players can now /join to enter the game."
        )
    else:
        await update.message.reply_text("Failed to load scenario. Check the path.")


async def cmd_nextturn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/nextturn — open the next turn (admin/debug)."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    registry = _registry(context)
    user = update.effective_user
    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await update.message.reply_text(ONBOARDING_MESSAGES["not_joined"])
        return

    scene = orchestrator.get_player_scene(player_id)
    if scene is None:
        await update.message.reply_text("You're not in a scene.")
        return

    tw = orchestrator.open_turn(scene.scene_id)
    if tw:
        await update.message.reply_text(
            f"Turn {tw.turn_number} opened in {scene.name}. Submit your actions!"
        )
    else:
        await update.message.reply_text("Could not open a new turn.")


async def cmd_forceresolve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/forceresolve — force-resolve the current turn window (admin/debug)."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    registry = _registry(context)
    user = update.effective_user
    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await update.message.reply_text(ONBOARDING_MESSAGES["not_joined"])
        return

    scene = orchestrator.get_player_scene(player_id)
    if scene is None or scene.active_turn_window_id is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_active_turn"])
        return

    log_entry = orchestrator.resolve_turn(scene.active_turn_window_id)
    if log_entry:
        await update.message.reply_text(
            f"Turn {log_entry.turn_number} resolved.\n{log_entry.narration}"
        )
    else:
        await update.message.reply_text("Failed to resolve the turn.")


async def cmd_diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/diagnostics — run diagnostics and DM the report (admin)."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    report = orchestrator.diagnostics_engine.build_report(
        campaign_id=orchestrator.campaign.campaign_id if orchestrator.campaign else "",
        turn_windows=list(orchestrator.turn_windows.values()),
        scenes=list(orchestrator.scenes.values()),
        players=list(orchestrator.players.values()),
    )
    text = orchestrator.diagnostics_engine.format_report(report)
    await update.message.reply_text(text[:4096])


async def cmd_scene(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/scene — show the current scene description and exits."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_active_game"])
        return

    registry = _registry(context)
    user = update.effective_user
    try:
        player_id = registry.player_id_for(user.id)
    except UnknownUserError:
        await update.message.reply_text(ONBOARDING_MESSAGES["not_joined"])
        return

    scene = orchestrator.get_player_scene(player_id)
    if scene is None:
        await update.message.reply_text("You're not in a scene.")
        return

    exit_parts = []
    for d, sid in scene.exits.items():
        dest = orchestrator.scenes.get(sid)
        dest_name = dest.name if dest else sid
        exit_parts.append(f"{d} -> {dest_name}")
    exits_text = ", ".join(exit_parts) or "None"

    await update.message.reply_text(
        f"📍 {scene.name}\n\n{scene.description}\n\nExits: {exits_text}"
    )


async def cmd_who(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/who — show which players are in which scenes."""
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_active_game"])
        return

    lines = []
    for scene in orchestrator.scenes.values():
        players = orchestrator.get_scene_players(scene.scene_id)
        player_names = [p.display_name for p in players]
        if player_names:
            lines.append(f"{scene.name}: {', '.join(player_names)}")
        else:
            lines.append(f"{scene.name}: (empty)")

    await update.message.reply_text("\n".join(lines) if lines else "No scenes.")
