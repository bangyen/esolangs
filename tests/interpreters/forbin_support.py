"""The Forbin suites shared helper: run a program and return what it printed."""

import contextlib

from esolangs.interpreters.forbin import run
from esolangs.interpreters.io import ScriptedIO


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()
