"""Interpreter runners shared by the boolean-generator test modules."""

import importlib
import io
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout

from esolangs.runtime.io import IO
from tests.interpreters.runner import run_program

Runner = Callable[[str, list[str]], str]


def _stdin(inputs: list[str]) -> str:
    """Join input lines into the single stdin string the runner takes."""
    return "".join(f"{line}\n" for line in inputs)


def _runner(module: str, *, lines: bool = False, newline: bool = False) -> Runner:
    """Build ``run_X(program, inputs)`` for ``esolangs.languages.<id>.interpreter``.

    ``lines`` hands the program over as rows; ``newline`` feeds one input per
    line instead of joining them.  The module is imported on first run.
    """

    def run_language(program: str, inputs: list[str]) -> str:
        run = importlib.import_module(f"esolangs.languages.{module}.interpreter").run
        code = program.splitlines() if lines else program
        return run_program(run, code, _stdin(inputs) if newline else "".join(inputs))

    return run_language


run_bf = _runner("brainfuck")


def _run_from(module: str, program: str, feed: Iterator[str]) -> str:
    """Run ``program`` against an iterator, leaving what it did not read."""
    run = importlib.import_module(module).run
    buffer = io.StringIO()

    class CharacterFeed(IO):
        def input_char(self, _prompt: str = "Input: ") -> int:
            return ord(next(feed))

    with redirect_stdout(buffer):
        run(program, io=CharacterFeed())
    return buffer.getvalue()
