"""Unit tests for the Decleq interpreter.

Tests cover the ``b = a - 1`` countdown OISC, the memory-mapped I/O
(``-2`` output, ``-1`` input), the jump and fall-through, and the documented
halt/limit conventions.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.decleq import run
from tests.interpreters.oisc import memory, run_program


def _run(code, stdin="", limit=100_000):
    return run_program(run, code, stdin=stdin, limit=limit)


class TestCountdown:
    def test_decrements_and_falls_through(self) -> None:
        # cell 10 starts 5; one decrement leaves 4, not <= 0, so the pointer
        # advances to the halt and nothing prints.
        code = memory([[10, 10, 99], [0, 0, 999]], {10: 5})
        assert _run(code) == ""

    def test_jumps_when_it_reaches_zero(self) -> None:
        # cell 10 = 1: after one decrement it is 0, jumping to the output at
        # pc 3 instead of falling through.
        code = memory([[10, 10, 3], [-2, 10, 0], [0, 0, 999]], {10: 1})
        assert _run(code) == "\x00"

    def test_copy_decremented_value_to_another_cell(self) -> None:
        # a == 30, b == 31: memory[31] becomes memory[30] - 1 = 4.
        code = memory([[30, 31, 99], [-2, 31, 0], [0, 0, 999]], {30: 5})
        assert _run(code) == "\x04"


class TestIO:
    def test_output(self) -> None:
        # -2 10 0 outputs memory[10] and falls through to the halt.
        code = memory([[-2, 10, 0], [0, 0, 999]], {10: 65})
        assert _run(code) == "A"

    def test_input(self) -> None:
        # -1 10 0 reads a byte into memory[10]; -2 10 0 prints it.
        code = memory([[-1, 10, 3], [-2, 10, 0], [0, 0, 999]])
        assert _run(code, "Q") == "Q"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(memory([[-1, 10, 3], [0, 0, 999]]), io)


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        assert _run(memory([[10, 10, 10_000]], {10: 1})) == ""

    def test_looping_program_hits_the_limit(self) -> None:
        # decrement cell 10 from a large value, looping back to itself.
        code = memory([[10, 10, 0]], {10: 10**6})
        io = ScriptedIO("")
        with pytest.raises(HaltError):
            run(code, io, limit=100)

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            _run("10 10 x")

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        code = "# a comment\n\n1 1 3 # trailing comment\n-2 1 0\n"
        assert _run(code) == "\x00"

    def test_empty_program(self) -> None:
        assert _run("") == ""
