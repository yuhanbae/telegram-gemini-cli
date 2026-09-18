import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_COMMAND = os.getenv("GEMINI_COMMAND", "gemini").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "300"))

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
