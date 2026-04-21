"""Slash command handlers: /start, /join, /help, /status, and game commands.

Each handler is an async PTB callback.  They are registered onto the
Application in handlers.py via CommandHandler.

The registry is retrieved from application.bot_data["registry"]; the config
from application.bot_data["config"].  Both are injected at startup.
The orchestrator is from application.bot_data["orchestrator"] (Phase 16+).
"""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot.mapping import BotRegistry, UnknownUserError
from bot.onboarding import ONBOARDING_MESSAGES, ONBOARDING_PROMPT

# Scenario files must resolve under this directory
_SCENARIOS_ROOT = Path(__file__).resolve().parent.parent / "scenarios"

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "--- Getting Started ---\n"
    "  /start  — Say hello to the bot (required before playing)\n"
    "  /join   — Join the current game and enter the starting scene\n"
    "            (send this in the group, not in a DM)\n"
    "  /help   — Show this message\n"
    "\n"
    "--- Playing ---\n"
    "  /status — Show your character, scene, and game state\n"
    "  /scene  — Describe your current scene and its exits\n"
    "  /who    — Show which players are in which scenes\n"
    "\n"
    "During a turn, type your action as a regular message in the\n"
    "group chat. The bot will interpret it and submit it for you.\n"
    "Use /ready or /pass via inline buttons when they appear.\n"
    "\n"
    "--- Game Master / Admin ---\n"
    "  /newgame <path>  — Load a scenario and start a campaign\n"
    "                     e.g. /newgame scenarios/starters/goblin_caves.yaml\n"
    "  /nextturn        — Open the next turn in your scene\n"
    "  /forceresolve    — Force-resolve the current turn\n"
    "  /diagnostics     — Show a diagnostics report\n"
    "\n"
    "--- Tips ---\n"
    "  - DM the bot for private actions and secret communication\n"
    "  - The bot will DM you hidden clues and private referee info\n"
    "  - Available scenarios: goblin_caves, haunted_manor,\n"
    "    forest_ambush, merchant_quarter\n"
)


def _registry(context: ContextTypes.DEFAULT_TYPE) -> BotRegistry:
    registry = context.application.bot_data.get("registry")
    if registry is None:
        logger.error("BotRegistry not found in bot_data — bot not properly initialized")
        raise RuntimeError("BotRegistry not configured")
    return registry


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — greet the user and prompt onboarding if needed."""
    if not update.effective_user or not update.message:
        return
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
    if not update.effective_user or not update.message:
        return
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

    orchestrator = _orchestrator(context)
    if orchestrator is None or orchestrator.campaign_id is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_active_game"])
        return

    import uuid

    player_id = str(uuid.uuid4())
    display_name = user.full_name or user.first_name

    try:
        player, character = orchestrator.add_player(
            player_id=player_id,
            display_name=display_name,
            telegram_user_id=user.id,
        )
    except Exception:
        logger.exception("Failed to add player telegram_user_id=%s", user.id)
        await update.message.reply_text(
            "Something went wrong joining the game. Please try again."
        )
        return

    registry.register_player(user.id, player_id)

    scene = orchestrator.get_player_scene(player_id)
    scene_info = f" You're in: {scene.name}." if scene else ""

    logger.info(
        "Player joined: telegram_user_id=%s player_id=%s char=%s",
        user.id,
        player_id,
        character.name,
    )
    await update.message.reply_text(
        f"Welcome, {display_name}! Your character has been created.{scene_info}\n"
        "Use /scene to look around, or /help for all commands.\n"
        "DM me directly for private actions."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — show the command list."""
    if not update.message:
        return
    await update.message.reply_text(_HELP_TEXT)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — show the player's current game state (stub)."""
    if not update.effective_user or not update.message:
        return
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
            f"{user.first_name}\nStatus: registered (no active game)"
        )
        return

    player = orchestrator.get_player(player_id)
    display = player.display_name if player else user.first_name

    scene = orchestrator.get_player_scene(player_id)
    if scene is None:
        await update.message.reply_text(
            f"{display}\nStatus: registered, not in a scene"
        )
        return

    char = orchestrator.get_player_character(player_id)
    char_info = f"Character: {char.name}" if char else ""
    await update.message.reply_text(
        f"{display}\n{char_info}\nScene: {scene.name}\nState: {scene.state.value}"
    )


def _orchestrator(context: ContextTypes.DEFAULT_TYPE):
    """Get the GameOrchestrator from bot_data, or None."""
    return context.application.bot_data.get("orchestrator")


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/newgame <scenario_path> — load a scenario and start a campaign."""
    if not update.effective_user or not update.message:
        return
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /newgame <scenario_path>")
        return

    scenario_path = args[0]

    # Prevent path traversal: resolve against scenarios root
    try:
        resolved = Path(scenario_path).resolve()
        if not resolved.is_relative_to(_SCENARIOS_ROOT):
            await update.message.reply_text(
                "Invalid path. Scenarios must be under the scenarios/ directory."
            )
            return
    except (ValueError, OSError):
        await update.message.reply_text("Invalid scenario path.")
        return

    chat_id = update.message.chat.id
    success = orchestrator.load_scenario(scenario_path, telegram_group_id=chat_id)
    if success:
        # Register campaign→chat mapping in bot registry
        registry = _registry(context)
        if orchestrator.campaign_id:
            registry.register_campaign(chat_id, orchestrator.campaign_id)
        scene_count = len(orchestrator.get_scenes())
        await update.message.reply_text(
            f"Scenario loaded! {scene_count} scenes ready.\n"
            "Players can now /join to enter the game."
        )
    else:
        await update.message.reply_text("Failed to load scenario. Check the path.")


async def cmd_nextturn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/nextturn — open the next turn (admin/debug)."""
    if not update.effective_user or not update.message:
        return
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
    if not update.effective_user or not update.message:
        return
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
        narration = log_entry.narration
        _TELEGRAM_MAX = 4096
        header = f"Turn {log_entry.turn_number} resolved.\n"
        max_narration = _TELEGRAM_MAX - len(header) - 1  # -1 for safety
        if len(narration) > max_narration:
            narration = narration[: max_narration - 3] + "..."
        await update.message.reply_text(f"{header}{narration}")
    else:
        await update.message.reply_text("Failed to resolve the turn.")


async def cmd_diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/diagnostics — run diagnostics and DM the report (admin)."""
    if not update.message:
        return
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_orchestrator"])
        return

    campaign = orchestrator.get_campaign()
    report = orchestrator.diagnostics_engine.build_report(
        campaign_id=campaign.campaign_id if campaign else "",
        turn_windows=orchestrator.get_turn_windows(),
        scenes=orchestrator.get_scenes(),
        players=orchestrator.get_players(),
    )
    text = orchestrator.diagnostics_engine.format_report(report)
    await update.message.reply_text(text[:4096])


async def cmd_scene(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/scene — show the current scene description and exits."""
    if not update.effective_user or not update.message:
        return
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
        dest = orchestrator.get_scene(sid)
        dest_name = dest.name if dest else sid
        exit_parts.append(f"{d} -> {dest_name}")
    exits_text = ", ".join(exit_parts) or "None"

    await update.message.reply_text(
        f"📍 {scene.name}\n\n{scene.description}\n\nExits: {exits_text}"
    )


async def cmd_who(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/who — show which players are in which scenes."""
    if not update.message:
        return
    orchestrator = _orchestrator(context)
    if orchestrator is None:
        await update.message.reply_text(ONBOARDING_MESSAGES["no_active_game"])
        return

    lines = []
    for scene in orchestrator.get_scenes():
        players = orchestrator.get_scene_players(scene.scene_id)
        player_names = [p.display_name for p in players]
        if player_names:
            lines.append(f"{scene.name}: {', '.join(player_names)}")
        else:
            lines.append(f"{scene.name}: (empty)")

    await update.message.reply_text("\n".join(lines) if lines else "No scenes.")
