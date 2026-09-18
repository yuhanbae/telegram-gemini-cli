from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import TELEGRAM_BOT_TOKEN
from .gemini_cli import ask_gemini, list_sessions

DONATE_URL = (
    "https://www.paypal.com/donate/"
    "?business=yuhanbae%40gmail.com&currency_code=USD"
)


def donate_keyboard():
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "☕ Donate / Buy Me a Coffee",
                url=DONATE_URL,
            )
        ]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Telegram Gemini CLI*\n\n"
        "Send a message to Gemini CLI.\n\n"
        "Commands:\n"
        "/new — start a new Gemini session\n"
        "/resume — resume the current session\n"
        "/sessions — list Gemini sessions\n"
        "/status — wrapper status\n"
        "/donate — support development ☕",
        parse_mode="Markdown",
        reply_markup=donate_keyboard(),
    )


async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☕ Support development with PayPal:",
        reply_markup=donate_keyboard(),
    )


async def new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.pop("gemini_session", None)
    await update.message.reply_text(
        "🆕 Session mapping cleared.\n"
        "The next message will start a fresh Gemini session."
    )


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.chat_data.get("gemini_session")

    if not session:
        await update.message.reply_text(
            "No session is mapped to this Telegram chat yet."
        )
        return

    await update.message.reply_text(
        f"🔄 Gemini session configured:\n`{session}`",
        parse_mode="Markdown",
    )


async def sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        output = await list_sessions()
    except Exception as exc:
        await update.message.reply_text(f"❌ {exc}")
        return

    await send_chunks(update, output)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = context.chat_data.get("gemini_session")

    await update.message.reply_text(
        "🟢 Telegram wrapper online\n"
        f"Gemini session: {session or 'new / not mapped'}"
    )


async def send_chunks(update: Update, text: str):
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i + 4000])


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").strip()

    if not prompt:
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    session = context.chat_data.get("gemini_session")

    try:
        answer = await ask_gemini(prompt, session=session)

    except Exception as exc:
        await update.message.reply_text(
            f"❌ Gemini CLI error:\n{exc}"
        )
        return

    await send_chunks(update, answer)


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("new", new))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("sessions", sessions))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message,
        )
    )

    return app
