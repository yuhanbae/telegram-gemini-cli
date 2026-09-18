"""Async subprocess wrappers around the local Gemini CLI.

All commands are run non-interactively via the verified Gemini CLI flags:

    gemini -p "<prompt>"                 # headless prompt
    gemini --session-id <uuid>           # start a new named session
    gemini --resume <id|latest>          # resume an existing session
    gemini --list-sessions               # list sessions for the project
    gemini --delete-session <id|index>   # delete a session

Session state is kept per Telegram chat (chat_data) and maps the chat to a
UUID created on "/new" (or lazily on first message). "latest" is NOT used,
because sessions are per-project directory and would collide between chats
and with any other CLI usage on the machine.
"""

import asyncio
import logging
import os
import re
import uuid

from .config import GEMINI_COMMAND, GEMINI_MODEL, GEMINI_TIMEOUT

logger = logging.getLogger(__name__)

_SESSION_ID_RE = re.compile(r"^[0-9a-fA-F-]+$")


def _base_args() -> list[str]:
    args: list[str] = []
    if GEMINI_MODEL:
        args += ["--model", GEMINI_MODEL]
    return args


async def _run(*args: str, stdin_data: str | None = None) -> tuple[str, str]:
    """Run a Gemini CLI subcommand, return (stdout, stderr)."""
    cmd = [GEMINI_COMMAND, *args]
    logger.debug("Running: %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.getcwd(),
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin_data.encode("utf-8") if stdin_data else None),
            timeout=GEMINI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(
            f"Gemini CLI timed out after {GEMINI_TIMEOUT} seconds."
        ) from None

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()

    # The Gemini CLI on Termux prints node-pty load warnings to stderr even
    # on success; filter that known noise so real errors stand out.
    err = _strip_pty_noise(err)

    if proc.returncode != 0:
        detail = err or out
        detail = detail.replace("An unexpected critical error occurred:[object Object]", "")
        detail = " ".join(detail.split())  # squash stack-trace newlines
        if len(detail) > 500:
            detail = detail[:500] + " …"
        raise RuntimeError(
            f"Gemini CLI exited with code {proc.returncode}. "
            f"{'Detail: ' + detail if detail else 'No output captured.'}"
        )

    return out, err


def _strip_pty_noise(err: str) -> str:
    if not err:
        return ""
    lines = [
        line for line in err.splitlines()
        if "node-pty" not in line and "pty.node" not in line
        and not line.startswith("innerError")
        and not line.startswith("Require stack")
        and not line.startswith("  at ")
        and not line.startswith("code: 'MODULE_NOT_FOUND'")
        and not line.startswith("requireStack")
        and not line.startswith("]")
    ]
    return "\n".join(lines).strip()


def new_session_id() -> str:
    return str(uuid.uuid4())


async def ask_gemini(
    prompt: str,
    session_id: str | None = None,
    resume: bool = False,
) -> str:
    args = _base_args()
    if resume and session_id:
        args += ["--resume", session_id]
    elif session_id:
        args += ["--session-id", session_id]
    args += ["-p", prompt, "--output-format", "text"]

    out, _err = await _run(*args, stdin_data=prompt)
    return out or "(Gemini CLI returned an empty response.)"


async def ask_gemini_safe(
    prompt: str,
    session_id: str | None = None,
) -> tuple[str, str | None]:
    """Ask Gemini, auto-falling back to a fresh session when a resume fails.

    Returns ``(answer, effective_session_id)``.

    The Gemini CLI rejects a ``--resume <uuid>`` when no session with that
    UUID exists for the *current project directory* (e.g. the session was
    created under a different directory, deleted, or this is the chat's
    first message and the UUID was just generated). In that case we retry
    once with ``--session-id <uuid>`` which *creates* the session, so the
    chat keeps a stable multi-turn identity afterwards.
    """
    if session_id:
        try:
            return await ask_gemini(prompt, session_id=session_id, resume=True), session_id
        except RuntimeError as exc:
            if "No previous sessions" not in str(exc):
                raise
            logger.info(
                "Resume of %s failed (not in this project dir); "
                "creating it with --session-id instead.", session_id,
            )
    return await ask_gemini(prompt, session_id=session_id), session_id


async def list_sessions() -> str:
    out, _err = await _run(*_base_args(), "--list-sessions")
    return out or "No Gemini sessions found for this project."


async def delete_session(session_ref: str) -> str:
    """Delete a session by UUID or by list index.

    ``session_ref`` must be a UUID or a positive integer (index from
    ``--list-sessions``). Anything else is rejected to avoid shell
    injection through CLI arguments.
    """
    cleaned = session_ref.strip()
    if not (
        _SESSION_ID_RE.fullmatch(cleaned)
        or cleaned.isdigit()
    ):
        raise ValueError(
            f"Invalid session reference: {session_ref!r}. "
            "Use a session UUID or the numeric index shown by /sessions."
        )
    await _run(*_base_args(), "--delete-session", cleaned)
    return f"Session {cleaned} deleted."
