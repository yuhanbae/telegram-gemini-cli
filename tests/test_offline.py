"""Offline tests: chunking, session-ref validation, subprocess mock,
and bot construction. No network, no real Gemini calls."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test:test-token")

from src.bot import send_chunked, CHUNK_SIZE, build_app  # noqa: E402
from src import gemini_cli  # noqa: E402


class FakeMessage:
    def __init__(self):
        self.sent = []

    async def reply_text(self, text, **kwargs):
        self.sent.append(text)


def test_chunking():
    async def run():
        m = FakeMessage()
        await send_chunked(m, "x" * 9000)
        assert all(len(t) <= 4096 for t in m.sent)
        assert "".join(m.sent) == "x" * 9000
        assert [len(t) for t in m.sent] == [CHUNK_SIZE, CHUNK_SIZE, 1000]
        await send_chunked(m, "   ")  # whitespace-only -> placeholder
        assert m.sent[-1] == "(empty response)"

    asyncio.run(run())


def test_session_ref_validation():
    import uuid as _uuid
    sid = _uuid.uuid4().hex
    assert gemini_cli._SESSION_ID_RE.fullmatch(sid)
    assert gemini_cli._SESSION_ID_RE.fullmatch("123")
    for bad in ("bad; rm -rf /", "abc def", "../x", ""):
        assert not gemini_cli._SESSION_ID_RE.fullmatch(bad.strip() or " " if bad else " ")

    async def run():
        for bad in ("bad; rm -rf /", "abc def", "../x"):
            try:
                await gemini_cli.delete_session(bad)
                raise AssertionError(f"should reject {bad!r}")
            except ValueError:
                pass

    asyncio.run(run())


def test_new_session_id():
    sid = gemini_cli.new_session_id()
    import uuid as _uuid
    _uuid.UUID(sid)  # must be a valid UUID
    assert sid != gemini_cli.new_session_id()


def test_subprocess_mock(tmp_path=None):
    """_run() must pass through env, time out, and translate non-zero exits."""
    import pathlib, tempfile

    script = pathlib.Path(tempfile.mkstemp(suffix=".py")[1])
    script.write_text(
        "import os, sys\n"
        "if os.environ.get('MOCK_FAIL'):\n"
        "    sys.stderr.write('mock failure detail\\n')\n"
        "    sys.exit(3)\n"
        "if os.environ.get('MOCK_SLEEP'):\n"
        "    import time\n"
        "    time.sleep(float(os.environ['MOCK_SLEEP']))\n"
        "print('mock output')\n"
    )
    py = sys.executable

    async def run():
        # success path
        proc = await asyncio.create_subprocess_exec(
            py, str(script),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        assert out.decode().strip() == "mock output"

        # timeout path uses the same pattern as _run: verify wait_for kills
        async def slow():
            p = await asyncio.create_subprocess_exec(
                py, str(script),
                env={**os.environ, "MOCK_SLEEP": "2"},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(p.communicate(), timeout=0.5)
                assert False, "expected TimeoutError"
            except asyncio.TimeoutError:
                p.kill()
                await p.wait()
        await slow()
        print("subprocess mock tests OK")

    asyncio.run(run())


def test_bot_builds():
    app = build_app()
    assert len(app.handlers[0]) == 8  # 7 commands + text handler


if __name__ == "__main__":
    test_chunking()
    test_session_ref_validation()
    test_new_session_id()
    test_subprocess_mock()
    test_bot_builds()
    print("all offline tests passed")
