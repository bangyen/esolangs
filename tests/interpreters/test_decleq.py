"""Unit tests for the Decleq interpreter.

Tests cover the ``b = a - 1`` countdown OISC, the memory-mapped I/O
(``-2`` output, ``-1`` input), the jump and fall-through, and the documented
halt/limit conventions.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.decleq import run
from tests.interpreters.contract import EmptyProgramContract
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

    def test_the_default_limit_is_ten_thousand(self) -> None:
        """The default cuts a run off at exactly 10,000 instructions.

        Every other test passes ``limit=`` explicitly, so the default was
        never the bound under test and could take any nearby value unnoticed.
        ``run_with_limit`` checks ``halted`` at the *top* of each pass, so a
        program taking exactly ``limit`` steps still exhausts the loop and
        raises -- which makes 10,000 the count that separates the real
        default from one a single step larger, and 9,998 the companion that
        pins it from below.

        The program is a countdown of ``n`` passes behind a one-instruction
        prologue, so it runs 2n steps: cell 11 counts down and jumps off the
        end at zero, while the cell-12 source keeps the loop's tail
        instruction jumping back to it.
        """

        def countdown(n: int) -> str:
            mem = [9, 10, 0, 11, 11, 99, 12, 13, 3, 5, 0, n, 0, 0]
            return " ".join(map(str, mem))

        with pytest.raises(HaltError):
            run(countdown(5000), ScriptedIO(""))
        run(countdown(4999), ScriptedIO(""))

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            _run("10 10 x")

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        code = "# a comment\n\n1 1 3 # trailing comment\n-2 1 0\n"
        assert _run(code) == "\x00"


class TestOperandRange:
    """The guards on an operand that points outside memory.

    Every one of these was a surviving mutant: the suite exercised the
    guards only from well inside memory, where widening or narrowing a
    bound changes nothing, so each boundary is pinned from both sides.
    """

    def test_output_reads_the_first_cell(self) -> None:
        # b == 0 is in range, so this prints memory[0] -- here the -2 of the
        # output instruction itself, & 0xFF.  Raising the guard's floor off
        # zero would print a NUL instead.
        assert _run(memory([[-2, 0, 0], [0, 0, 999]])) == "\xfe"

    def test_output_past_the_end_reads_zero(self) -> None:
        # b == len(memory) is one past the last cell, so the guard's upper
        # bound has to be strict: memory[6] does not exist.
        assert _run(memory([[-2, 6, 0], [0, 0, 999]])) == "\x00"

    def test_output_before_the_start_reads_zero(self) -> None:
        assert _run(memory([[-2, -5, 0], [0, 0, 999]])) == "\x00"

    def test_source_past_the_end_reads_zero(self) -> None:
        # a == len(memory) exactly, the other side of the same strictness:
        # memory[1] becomes 0 - 1, which is <= 0, so it jumps to 99 and
        # halts.  A non-strict bound would index off the end instead.
        assert _run("6 1 99 0 0 0") == ""

    def test_decrement_to_one_falls_through(self) -> None:
        # The jump is on <= 0, so a cell landing on exactly 1 must fall
        # through to the output rather than jump past it.
        code = memory([[10, 10, 9], [-2, 10, 0], [0, 0, 999]], {10: 2})
        assert _run(code) == "\x01"

    def test_growing_memory_fills_with_zeros(self) -> None:
        # Writing to cell 20 grows memory to reach it; the cells the growth
        # creates on the way are zero.  Cell 19 is read rather than 20,
        # because the instruction overwrites 20 itself.
        code = memory([[5, 20, 6], [0, 0, 0], [-2, 19, 0], [0, 0, 999]], {5: 1})
        assert _run(code) == "\x00"

    def test_growth_stops_at_the_cell_it_was_for(self) -> None:
        # Growth reaches exactly the cell being written and no further, and
        # the length that leaves is what decides the halt: memory is six
        # cells, writing cell 6 makes it seven, and the jump to 7 is then
        # one past the end.  Growing even one cell further would leave an
        # instruction there for the pointer to land on, so the program
        # would run on instead of stopping.  The cells' *values* cannot
        # show this -- a surplus cell is zero, and reading past the end
        # gives zero too -- so it is the halt that pins it.
        assert _run("-2 5 0 9 6 7") == "\x07"

    def test_input_growth_stops_at_the_cell_it_was_for(self) -> None:
        # The input branch grows memory with its own copy of the code, so
        # it needs the same boundary as the countdown above.  Memory is
        # five cells; reading into cell 5 makes it exactly six, the output
        # at pc 3 prints what was read, and the fall-through to pc 6 is
        # then one past the end.  Growing further would leave cells for the
        # pointer to keep walking through instead of halting.
        assert _run("-1 5 0 -2 5", "Z") == "Z"

    def test_input_grows_memory_to_reach_its_cell(self) -> None:
        # b == len(memory) exactly: one past the last cell, so the growth
        # has to fire here rather than only beyond it.
        code = memory([[-1, 6, 3], [-2, 6, 0]])
        assert _run(code, "Z") == "Z"

    def test_input_growth_fills_with_zeros(self) -> None:
        # As above for the countdown, read a neighbour of the written cell:
        # cell 19 is created by growing out to cell 20 and stays zero.
        code = memory([[-1, 20, 3], [-2, 19, 0], [0, 0, 999]])
        assert _run(code, "Z") == "\x00"

    def test_input_advances_the_pointer_by_three(self) -> None:
        # The advance past an input is relative.  It coincides with an
        # absolute jump to 3 whenever the input sits at pc 0, so this one is
        # reached from a countdown instead: after the read at pc 3 the
        # pointer must fall through to the marker at pc 6, not back to 3.
        code = "9 9 3 -1 10 0 -2 11 0 1 0 66 0 0 999"
        assert _run(code, "Z") == "B"

    def test_truncated_final_instruction(self) -> None:
        # Memory ends mid-instruction: cell 6 is a lone `7` with no b and no
        # c after it, so both default to zero.  It therefore stores
        # memory[7 - 1] -- itself absent, so 0 -- minus one into memory[0]
        # and jumps to 0.  Reading either operand off the end instead of
        # defaulting raises IndexError, which is what this pins.
        from esolangs.interpreters.register_based.decleq import _Machine

        machine = _Machine("5 5 6 0 0 0 7", ScriptedIO(""))
        machine.pc = 6
        machine.step()
        assert (machine.pc, machine.memory[0]) == (0, -1)


class TestStepMachine:
    def test_step_tracks_memory_and_pointer(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.decleq import _Machine

        machine = _Machine("-2 5 9 9 9 65 0 0", ScriptedIO())
        assert (machine.pc, list(machine.memory)) == (0, [-2, 5, 9, 9, 9, 65, 0, 0])
        machine.step()  # a=-2 outputs memory[5]
        assert machine.io.getvalue() == "A"
        assert machine.pc == 3
        machine.step()  # the countdown then jumps off the end of memory
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.pc == 65

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.decleq import _Machine

        assert hash(_Machine("-2 5 9 9 9 65 0 0", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.decleq import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert (
            run_until_halt_or_cycle(_Machine("-2 5 9 9 9 65 0 0", ScriptedIO())) is True
        )


class TestContract(EmptyProgramContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
