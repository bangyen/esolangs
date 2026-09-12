r"""Unit tests for the Decleq interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.decleq import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.oisc import memory, run_program


def _run(code, stdin=""):
    return run_program(run, code, stdin=stdin)


class TestCountdown:
    def test_decrements_and_falls_through(self) -> None:
        # cell 10 starts 5; one.
        # advances to the halt and.
        code = memory([[10, 10, 99], [0, 0, 999]], {10: 5})
        assert _run(code) == ""

    def test_jumps_when_it_reaches_zero(self) -> None:
        # cell 10 = 1: after one.
        # pc 3 instead of falling.
        code = memory([[10, 10, 3], [-2, 10, 0], [0, 0, 999]], {10: 1})
        assert _run(code) == "\x00"

    def test_copy_decremented_value_to_another_cell(self) -> None:
        # a == 30, b == 31: memory[31].
        code = memory([[30, 31, 99], [-2, 31, 0], [0, 0, 999]], {30: 5})
        assert _run(code) == "\x04"


class TestIO:
    def test_output(self) -> None:
        # -2 10 0 outputs memory[10].
        code = memory([[-2, 10, 0], [0, 0, 999]], {10: 65})
        assert _run(code) == "A"

    def test_input(self) -> None:
        # -1 10 0 reads a byte into.
        code = memory([[-1, 10, 3], [-2, 10, 0], [0, 0, 999]])
        assert _run(code, "Q") == "Q"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(memory([[-1, 10, 3], [0, 0, 999]]), io)


class TestHaltAndErrors:
    def test_jump_off_the_end_halts(self) -> None:
        assert _run(memory([[10, 10, 10_000]], {10: 1})) == ""

    def test_a_self_decrementing_loop_never_revisits_a_snapshot(self) -> None:
        r"""The growth claim the module docstring makes, executed."""
        from esolangs.interpreters.register_based.decleq import _Machine

        # a == b == 10 -- the operand.
        # pass decrements what it just.
        code = memory([[10, 10, 0]], {})
        machine = _Machine(code, ScriptedIO(""))
        seen = set()
        for _ in range(500):
            assert not machine.halted
            machine.step()
            snapshot = machine.snapshot()
            assert snapshot not in seen
            seen.add(snapshot)

    def test_malformed_token(self) -> None:
        with pytest.raises(ValueError, match="malformed memory token"):
            _run("10 10 x")

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        code = "# a comment\n\n1 1 3 # trailing comment\n-2 1 0\n"
        assert _run(code) == "\x00"


class TestOperandRange:
    r"""The guards on an operand that points outside memory."""

    def test_output_reads_the_first_cell(self) -> None:
        # b == 0 is in range, so this.
        # output instruction itself, &.
        # zero would print a NUL.
        assert _run(memory([[-2, 0, 0], [0, 0, 999]])) == "\xfe"

    def test_output_past_the_end_reads_zero(self) -> None:
        # b == len(memory) is one past.
        # bound has to be strict:.
        assert _run(memory([[-2, 6, 0], [0, 0, 999]])) == "\x00"

    def test_output_before_the_start_reads_zero(self) -> None:
        assert _run(memory([[-2, -5, 0], [0, 0, 999]])) == "\x00"

    def test_source_past_the_end_reads_zero(self) -> None:
        # a == len(memory) exactly, the.
        # memory[1] becomes 0 - 1,.
        # halts.
        assert _run("6 1 99 0 0 0") == ""

    def test_decrement_to_one_falls_through(self) -> None:
        # The jump is on <= 0, so a.
        # through to the output rather.
        code = memory([[10, 10, 9], [-2, 10, 0], [0, 0, 999]], {10: 2})
        assert _run(code) == "\x01"

    def test_growing_memory_fills_with_zeros(self) -> None:
        # Writing to cell 20 grows.
        # creates on the way are zero.
        # because the instruction.
        code = memory([[5, 20, 6], [0, 0, 0], [-2, 19, 0], [0, 0, 999]], {5: 1})
        assert _run(code) == "\x00"

    def test_growth_stops_at_the_cell_it_was_for(self) -> None:
        # Growth reaches exactly the.
        # the length that leaves is.
        # cells, writing cell 6 makes.
        # one past the end.
        # instruction there for the.
        # would run on instead of.
        # show this -- a surplus cell.
        # gives zero too -- so it is.
        assert _run("-2 5 0 9 6 7") == "\x07"

    def test_input_growth_stops_at_the_cell_it_was_for(self) -> None:
        # The input branch grows memory.
        # it needs the same boundary as.
        # five cells; reading into cell.
        # at pc 3 prints what was read,.
        # then one past the end.
        # pointer to keep walking.
        assert _run("-1 5 0 -2 5", "Z") == "Z"

    def test_input_grows_memory_to_reach_its_cell(self) -> None:
        # b == len(memory) exactly: one.
        # has to fire here rather than.
        code = memory([[-1, 6, 3], [-2, 6, 0]])
        assert _run(code, "Z") == "Z"

    def test_input_growth_fills_with_zeros(self) -> None:
        # As above for the countdown,.
        # cell 19 is created by growing.
        code = memory([[-1, 20, 3], [-2, 19, 0], [0, 0, 999]])
        assert _run(code, "Z") == "\x00"

    def test_input_advances_the_pointer_by_three(self) -> None:
        # The advance past an input is.
        # absolute jump to 3 whenever.
        # reached from a countdown.
        # pointer must fall through to.
        code = "9 9 3 -1 10 0 -2 11 0 1 0 66 0 0 999"
        assert _run(code, "Z") == "B"

    def test_truncated_final_instruction(self) -> None:
        # Memory ends mid-instruction:.
        # c after it, so both default.
        # memory[7 - 1] -- itself.
        # and jumps to 0.
        # defaulting raises IndexError,.
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
        machine.step()  # a=-2 outputs memory[5].
        assert machine.io.getvalue() == "A"
        assert machine.pc == 3
        machine.step()  # the countdown then jumps off.
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.pc == 65


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.decleq import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(_run)
    machine = staticmethod(_machine)
    stepping_program = "-2 5 9 9 9 65 0 0"
    halting_program = "-2 5 9 9 9 65 0 0"


class TestNegativeWriteIndex:
    r"""``_written`` indexes a negative ``b`` from the right, or raises."""

    def test_negative_addr_writes_from_the_right(self) -> None:
        from esolangs.interpreters.register_based.decleq import _written

        assert _written((1, 2, 3), -1, 9) == (1, 2, 9)
        assert _written((1, 2, 3), -3, 9) == (9, 2, 3)

    def test_negative_addr_past_the_left_end_raises(self) -> None:
        from esolangs.interpreters.register_based.decleq import _written

        with pytest.raises(HaltError, match="past the left end"):
            _written((1, 2, 3), -4, 9)
        with pytest.raises(HaltError, match="past the left end"):
            _written((), -1, 9)
