# Telegram Gemini CLI

A lightweight Telegram wrapper for the local Gemini CLI.

## Features

- Telegram → Gemini CLI bridge
- Non-interactive Gemini CLI execution
- `/start`
- `/status`
- `/new`
- `/donate`
- Telegram 4096-character response splitting
- Environment-based secrets
- Termux-friendly
- PayPal donation support

## Requirements

- Python 3.10+
- Telegram Bot Token
- Gemini CLI installed and authenticated

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env
cd ~/telegram-gemini-cli

cat > src/gemini_cli.py <<'EOF'
import asyncio
import os
import re

from .config import GEMINI_COMMAND, GEMINI_MODEL, GEMINI_TIMEOUT


async def run_gemini(*args: str) -> tuple[str, str]:
    cmd = [GEMINI_COMMAND, *args]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.getcwd(),
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=GEMINI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("Gemini CLI timed out")

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        raise RuntimeError(err or out or f"Gemini exited with {proc.returncode}")

    return out, err


def base_args() -> list[str]:
    args = []

    if GEMINI_MODEL:
        args += ["--model", GEMINI_MODEL]

    return args


async def ask_gemini(prompt: str, session: str | None = None) -> str:
    args = base_args()

    if session:
        args += ["--resume", session]

    args += ["--prompt", prompt]

    output, _ = await run_gemini(*args)
    return output or "(Gemini returned an empty response)"


async def list_sessions() -> str:
    output, _ = await run_gemini(*base_args(), "--list-sessions")
    return output or "No Gemini sessions found."


async def delete_session(session_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise ValueError("Invalid session identifier")

    output, _ = await run_gemini(
        *base_args(),
        "--delete-session",
        session_id,
    )

    return output or f"Session {session_id} deleted."
