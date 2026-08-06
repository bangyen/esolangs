"""Unit tests for the Back interpreter."""

import io
from contextlib import redirect_stdout
from typing import List

from esolangs.interpreters.tape_based.back import run


def run_and_capture(code: List[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code)
    return buffer.getvalue()


class TestBack:
    def test_halt_prints_tape(self) -> None:
        assert run_and_capture(["*"]) == "0\n"

    def test_flip_bit(self) -> None:
        assert run_and_capture(["-*"]) == "1\n"

    def test_move_right(self) -> None:
        assert run_and_capture([">-*"]) == "0 1\n"

    def test_flip_twice(self) -> None:
        assert run_and_capture([">--*"]) == "0 0\n"

    def test_skip_instruction_on_zero(self) -> None:
        """+ skips the next cell when the current bit is 0."""
        assert run_and_capture([">+-*"]) == "0 0\n"

    def test_reflect_backslash(self) -> None:
        """\\ reflects the direction."""
        assert run_and_capture(["\\-*"]) == "1\n"

    def test_reflect_slash(self) -> None:
        """/ reflects the direction."""
        assert run_and_capture(["/-*"]) == "1\n"

    def test_move_left(self) -> None:
        """< moves the tape head left when it is not at zero."""
        assert run_and_capture([">>-<*"]) == "0 0 1\n"
