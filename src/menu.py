"""Default /burger menu commands for the tegem bot.

Applied at every startup via ``Application.builder().post_init()`` so
Telegram's client-side menu list is always reset to exactly the commands
the bot implements (prevents stale/foreign entries accumulating).
"""

from telegram import BotCommand

DEFAULT_BOT_COMMANDS = [
    BotCommand("start", "Get started \u2014 usage overview"),
    BotCommand("help", "Command help"),
    BotCommand("new", "Start a fresh Gemini session"),
    BotCommand("resume", "Resume a session (uuid or index)"),
    BotCommand("sessions", "List saved Gemini sessions"),
    BotCommand("status", "Wrapper + session status"),
    BotCommand("donate", "Buy me a coffee \u26a1"),
]


async def post_init_reset_menu(application) -> None:
    """PTB post_init hook: reset the Telegram burger menu to defaults."""
    import logging

    logging.getLogger(__name__).info(
        "Resetting Telegram /burger menu to %d default commands",
        len(DEFAULT_BOT_COMMANDS),
    )
    await application.bot.set_my_commands(DEFAULT_BOT_COMMANDS)
