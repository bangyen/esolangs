"""The Forbin suites shared helper: run a program and return what it printed."""

import contextlib

from esolangs.languages.forbin.interpreter import run
from esolangs.runtime.io import ScriptedIO


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()
