"""Telegram bot that bridges messages to the local Gemini CLI.

Per-chat session state lives in ``context.chat_data``:

    {"gemini_session": "<uuid>"}

The UUID is created on /new or lazily on the first plain message, then
reused for every subsequent message in that chat so Gemini CLI keeps
multi-turn context via --session-id.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import gemini_cli
from .config import (
    ALLOWED_USER_IDS,
    GEMINI_COMMAND,
    GEMINI_MODEL,
    GEMINI_TIMEOUT,
    require_token,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4000  # below Telegram's 4096-char message limit

SPEED_WALLET_INVOICE = (
    "lightning:lnbc1p426acmpp5ga2jqrl7glrl3s9s680r3t2lucnc8zrgnpzy200hxpp7hrsa99"
    "pqdqqcqzzsxqyz5vqsp5h34eyqhnsemqjwlrqv86j9x7mst2jm0vjnmqwgpxgtya3ntaumqs9qxpqysgqpxuc"
    "wqklhnjpgv3rlrf59z35w7jrpqvhkdcksa40qad9nuedc2hhpxtyvay08atw00ujv7ehqf7ee2r57wulqwlzrfj038rl2h8nd8gp4l0q3y"
    "?label=Buy%20Me%20a%20Coffee%20(tegem)"
)

PAYPAL_ME_URL = "https://www.paypal.com/paypalme/yuhanbae"

SESSION_KEY = "gemini_session"


def donate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "⚡ Buy Me a Coffee (Speed Wallet)",
                url=SPEED_WALLET_INVOICE,
            ),
            InlineKeyboardButton(
                "☕ PayPal.Me / Buy Me a Coffee",
                url=PAYPAL_ME_URL,
            ),
        ]]
    )


async def send_chunked(message, text: str) -> None:
    text = (text or "").strip() or "(empty response)"
    for i in range(0, len(text), CHUNK_SIZE):
        await message.reply_text(text[i : i + CHUNK_SIZE])


def _allowed(update: Update) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    user_id = str(update.effective_user.id)
    return user_id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        logger.warning("Rejected /start from user %s", update.effective_user.id)
        return
    await update.message.reply_text(
        "🤖 *Telegram → Gemini CLI bridge*\n\n"
        "Send me a message and I will pass it to your local Gemini CLI.\n\n"
        "*Commands*\n"
        "/new — start a fresh session for this chat\n"
        "/resume <uuid|index> — switch to an existing Gemini CLI session\n"
        "/sessions — list sessions saved for this project directory\n"
        "/status — show wrapper + session state\n"
        "/donate — support the project ⚡\n\n"
        "Plain text messages are answered by Gemini CLI in your "
        "current working directory.",
        reply_markup=donate_keyboard(),
    )


async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "Thanks for your support! ⚡\n"
        "Open the button in any Lightning wallet\n"
        "(Speed Wallet, Bitcoin Core, Phoenix, Alby …).",
        reply_markup=donate_keyboard(),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    session = context.chat_data.get(SESSION_KEY)
    model = GEMINI_MODEL or "default"
    lines = [
        "🟢 *Status*",
        f"• Gemini CLI: `{GEMINI_COMMAND}`",
        f"• Model: {model}",
        f"• Timeout: {GEMINI_TIMEOUT}s",
        f"• This chat's session: `{session}`" if session else
        "• This chat's session: none yet (fresh start)",
    ]
    await update.message.reply_text("\n".join(lines))


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    session = gemini_cli.new_session_id()
    context.chat_data[SESSION_KEY] = session
    await update.message.reply_text(
        f"🆕 Fresh session started.\n"
        f"Session ID: `{session}`\n"
        "Your next message will open a new Gemini CLI session "
        "with that ID.",
    )


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    arg = " ".join(context.args).strip() if context.args else ""
    session = arg or context.chat_data.get(SESSION_KEY)

    if not session:
        await update.message.reply_text(
            "No session to resume in this chat yet.\n"
            "Use /new first, or /resume <uuid|index> with a session "
            "shown by /sessions.\n"
            "(Gemini CLI also accepts `latest` — note it refers to the "
            "most recent session of *this project directory*, not of "
            "this chat.)",
        )
        return

    context.chat_data[SESSION_KEY] = session
    await update.message.reply_text(
        f"🔄 This chat now maps to session `{session}`.\n"
        "The next message will be resumed with --resume.",
    )


async def sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    try:
        output = await gemini_cli.list_sessions()
    except RuntimeError as exc:
        await update.message.reply_text(f"❌ {exc}")
        return
    await send_chunked(update.message, output)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        logger.warning("Rejected message from user %s", update.effective_user.id)
        return

    prompt = (update.message.text or "").strip()
    if not prompt:
        return

    session = context.chat_data.get(SESSION_KEY)
    if not session:
        # First message of the chat: lazily create a UUID so multi-turn
        # context works for all following messages.
        session = gemini_cli.new_session_id()
        context.chat_data[SESSION_KEY] = session

    await update.message.chat.send_action(ChatAction.TYPING)
    logger.info("chat=%s session=%s prompt=%r",
                update.chat.id, session, prompt[:80])

    try:
        answer = await gemini_cli.ask_gemini(
            prompt, session_id=session, resume=True,
        )
    except RuntimeError as exc:
        logger.error("gemini run failed: %s", exc)
        await update.message.reply_text(f"❌ {exc}")
        return
    except Exception:
        logger.exception("unexpected error while running Gemini CLI")
        await update.message.reply_text(
            "❌ Unexpected internal error. Check the bot logs."
        )
        return

    await send_chunked(update.message, answer)


def build_app() -> Application:
    token = require_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("new", new))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("sessions", sessions))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message,
        ),
    )
    return app
