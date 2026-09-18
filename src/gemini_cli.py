import asyncio
import os

from .config import GEMINI_COMMAND, GEMINI_MODEL, GEMINI_TIMEOUT


async def ask_gemini(prompt: str) -> str:
    cmd = [GEMINI_COMMAND]

    if GEMINI_MODEL:
        cmd += ["--model", GEMINI_MODEL]

    cmd += ["--prompt", prompt]

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

    output = stdout.decode("utf-8", errors="replace").strip()
    error = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        raise RuntimeError(
            error or output or f"Gemini CLI exited with {proc.returncode}"
        )

    return output or "(Gemini returned an empty response)"
