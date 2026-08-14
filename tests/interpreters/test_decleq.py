"""Unit tests for the Decleq interpreter.

Tests cover the ``b = a - 1`` countdown OISC, the memory-mapped I/O
(``-2`` output, ``-1`` input), the jump and fall-through, and the documented
halt/limit conventions.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.decleq import run


def memory(instructions, cells=None):
    """Build the initial-memory code string.

    ``instructions`` is a list of ``[a, b, c]`` operand lists; ``cells``
    maps extra memory addresses to their initial values (the self-modifying
    model stores the program and data in one flat memory).
    """
    mem = []
    for ins in instructions:
        mem.extend(ins)
    cells = cells or {}
    while len(mem) <= max(cells, default=-1):
        mem.append(0)
    for addr, value in cells.items():
        mem[addr] = value
    return " ".join(map(str, mem))


def run_program(code, stdin="", limit=100_000):
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io, limit=limit)
    return io.getvalue()


class TestCountdown:
    def test_decrements_and_falls_through(self) -> None:
        # cell 10 starts 5; one decrement leaves 4, not <= 0, so the pointer
        # advances to the halt and nothing prints.
        code = memory([[10, 10, 99], [0, 0, 999]], {10: 5})
        assert run_program(code) == ""

    def test_jumps_when_it_reaches_zero(self) -> None:
        # cell 10 = 1: after one decrement it is 0, jumping to the output at
        # pc 3 instead of falling through.
        code = memory([[10, 10, 3], [-2, 10, 0], [0, 0, 999]], {10: 1})
        assert run_program(code) == "\x00"

    def test_copy_decremented_value_to_another_cell(self) -> None:
        # a == 30, b == 31: memory[31] becomes memory[30] - 1 = 4.
        code = memory([[30, 31, 99], [-2, 31, 0], [0, 0, 999]], {30: 5})
        assert run_program(code) == "\x04"


class TestIO:
    def test_output(self) -> None:
        # -2 10 0 outputs memory[10] and falls through to the halt.
        code = memory([[-2, 10, 0], [0, 0, 999]], {10: 65})
        assert run_program(code) == "A"

    def test_input(self) -> None:
        # -1 10 0 reads a byte into memory[10]; -2 10 0 prints it.
        code = memory([[-1, 10, 3], [-2, 10, 0], [0, 0, 999]])
        assert run_program(code, "Q") == "Q"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(memory([[-1, 10, 3], [0, 0, 999]]), io)


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        assert run_program(memory([[10, 10, 10_000]], {10: 1})) == ""

    def test_looping_program_hits_the_limit(self) -> None:
        # decrement cell 10 from a large value, looping back to itself.
        code = memory([[10, 10, 0]], {10: 10 ** 6})
        io = ScriptedIO("")
        with pytest.raises(HaltError):
            run(code, io, limit=100)

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            run_program("10 10 x")

    def test_empty_program(self) -> None:
        assert run_program("") == ""
