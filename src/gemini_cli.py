"""Async subprocess wrappers around the local Gemini CLI.

All commands are run non-interactively via the verified Gemini CLI flags:

    gemini -p "<prompt>"                 # headless prompt
    gemini --session-id <uuid>           # start a new named session
    gemini --resume <uuid|index|latest>  # resume an existing session
    gemini --list-sessions               # list sessions for the project
    gemini --delete-session <id|index>   # delete a session

Session state is kept per Telegram chat (chat_data) and maps the chat to a
UUID created on "/new" (or lazily on first message). The wrapper tracks
whether each UUID has been materialized in the CLI's session store and
picks the correct flag per call — see ask_gemini_safe().
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
        detail = detail.replace(
            "An unexpected critical error occurred:[object Object]", ""
        )
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


def clean_session_id(session_id: str | None) -> str | None:
    """Return the user-facing UUID, stripping any internal marker."""
    if not session_id:
        return None
    return session_id.split("#", 1)[0]


async def ask_gemini(
    prompt: str,
    session_id: str | None = None,
    resume: bool = False,
) -> str:
    """Single explicit-flag call. Prefer ask_gemini_safe() in the bot."""
    args = _base_args()
    if session_id:
        sid = clean_session_id(session_id)  # CLI never sees markers
        if resume:
            args += ["--resume", sid]
        else:
            args += ["--session-id", sid]
    args += ["-p", prompt, "--output-format", "text"]

    out, _err = await _run(*args, stdin_data=prompt)
    return out or "(Gemini CLI returned an empty response.)"


async def ask_gemini_safe(
    prompt: str,
    session_id: str | None = None,
    materialized: bool = False,
) -> tuple[str, str | None, bool]:
    """Ask Gemini with correct flag selection, self-healing on errors.

    Returns ``(answer, effective_session_id, materialized)``.

    Flag logic:
      * materialized  -> --resume <uuid|index>
      * not materialized -> --session-id <uuid>   (creates the session)

    Self-healing (one retry only):
      * "Session ID ... already exists"       -> retry with --resume
      * "No previous sessions" on resume      -> retry with --session-id
      * "Invalid session identifier"          -> retry with --resume
    """
    if not session_id:
        return await ask_gemini(prompt), None, False

    try:
        if materialized:
            answer = await ask_gemini(prompt, session_id, resume=True)
            return answer, session_id, True
        answer = await ask_gemini(prompt, session_id, resume=False)
        return answer, session_id, True
    except RuntimeError as exc:
        msg = str(exc)
        if "already exists" in msg:
            logger.info("Session %s exists; switching to --resume.",
                        clean_session_id(session_id))
            answer = await ask_gemini(prompt, session_id, resume=True)
            return answer, session_id, True
        if "No previous sessions" in msg or "Invalid session identifier" in msg:
            logger.info("Creating/switching session %s with --session-id.",
                        clean_session_id(session_id))
            answer = await ask_gemini(prompt, session_id, resume=False)
            return answer, session_id, True
        raise


async def list_sessions() -> str:
    out, _err = await _run(*_base_args(), "--list-sessions")
    return out or "No Gemini sessions found for this project."


async def delete_session(session_ref: str) -> str:
    """Delete a session by UUID or by list index.

    ``session_ref`` must be a UUID or a positive integer (index from
    ``--list-sessions``). Anything else is rejected to avoid CLI arg
    injection.
    """
    cleaned = session_ref.strip().split("#", 1)[0]
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
