"""The Forbin suites shared helper: run a program and return what it printed."""

import contextlib

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.forbin import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()
