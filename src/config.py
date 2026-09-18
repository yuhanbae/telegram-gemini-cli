"""Environment-based configuration.

All secrets come from the environment / .env file. Nothing here contains
hard-coded tokens.
"""

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_COMMAND = os.getenv("GEMINI_COMMAND", "gemini").strip() or "gemini"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

raw_timeout = os.getenv("GEMINI_TIMEOUT", "300").strip()
try:
    GEMINI_TIMEOUT = int(raw_timeout)
except ValueError:
    print(f"GEMINI_TIMEOUT={raw_timeout!r} is not an integer; defaulting to 300")
    GEMINI_TIMEOUT = 300

# Optional: extra args appended to every Gemini CLI invocation,
# e.g. "GEMINI_EXTRA_ARGS=--skip-trust" on Termux where /tmp is untrusted.
GEMINI_EXTRA_ARGS = [
    part for part in os.getenv("GEMINI_EXTRA_ARGS", "").split() if part
]

# Optional: restrict the bot to specific Telegram user ids (comma separated).
ALLOWED_USER_IDS = [
    part.strip()
    for part in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if part.strip()
]


def require_token() -> str:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured. "
            "Copy .env.example to .env and fill it in, or export the variable."
        )
    return TELEGRAM_BOT_TOKEN
