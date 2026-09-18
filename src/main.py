"""Entry point: start the Telegram bot in long-polling mode."""

import logging

from .bot import build_app
from .config import GEMINI_COMMAND, GEMINI_TIMEOUT, GEMINI_MODEL


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = build_app()
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting Telegram Gemini CLI bridge "
        "(cmd=%s model=%r timeout=%ss)",
        GEMINI_COMMAND, GEMINI_MODEL or "default", GEMINI_TIMEOUT,
    )
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
