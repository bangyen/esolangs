"""Unit tests for the Home Row interpreter.

Tests cover the BF-like commands (a/s/d/f/j/k/l/;), the 5x5 torus grid,
the while-nonzero loop, and the malformed-program rule.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.home_row import run


def run_program(code: str) -> str:
    io = ScriptedIO("")
    run(code, io)
    return io.getvalue()


class TestBasics:
    def test_print_and_reset(self) -> None:
        # 65 increments then k prints 'A' and resets the cell to zero.
        assert run_program("a" * 65 + "k;") == "A"
        # the cell is zero again, so a following k prints NUL
        assert run_program("a" * 65 + "k" + "k;") == "A\x00"

    def test_subtract(self) -> None:
        # cells are unbounded: 0 - 1 = -1, printed as its low byte
        assert run_program("sk;") == "\xff"

    def test_semicolon_halts(self) -> None:
        assert run_program("ak;ak;") == "\x01"

    def test_end_of_source_halts(self) -> None:
        assert run_program("ak") == "\x01"

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestPointer:
    def test_down_and_forward(self) -> None:
        # a on cell 0, f to cell 1, a increments cell 1, k prints it.
        assert run_program("afak;") == "\x01"

    def test_torus_wraps(self) -> None:
        # f four times returns to the same column (5x5), so the fifth cell
        # is cell 0 again: a fffff k prints the 1 from cell 0.
        assert run_program("af" * 5 + "k;") == "\x01"
        # d wraps the bottom row back to the top the same way.
        assert run_program("ad" * 5 + "k;") == "\x01"

    def test_move_then_edit_distinct_cells(self) -> None:
        # increment cell 0, move down, increment cell 5, move back up (d x4
        # wraps), and print cell 0.
        assert run_program("a" + "d" + "a" + "d" * 4 + "k;") == "\x01"


class TestSkip:
    def test_jump_skips_next_on_zero(self) -> None:
        # cell 0 is zero, so j skips the k.
        assert run_program("jk;") == ""

    def test_jump_does_not_skip_on_nonzero(self) -> None:
        assert run_program("ajk;") == "\x01"

    def test_jump_can_skip_an_increment(self) -> None:
        # j skips the a, so the cell stays zero.
        assert run_program("jak;") == "\x00"

    def test_jump_preserves_an_unskipped_increment(self) -> None:
        # cell 0 is nonzero, so j does not skip the a and it increments twice.
        assert run_program("ajak;") == "\x02"


class TestLoop:
    def test_loop_runs_while_nonzero(self) -> None:
        # aa l s l k; : the body decrements 2 down to 0, so k prints NUL.
        assert run_program("aa" + "l" + "s" + "l" + "k;") == "\x00"

    def test_loop_skips_when_zero(self) -> None:
        # cell is zero, so the body never runs and nothing prints.
        assert run_program("l" + "a" + "l" + "k;") == "\x00"

    def test_independent_loop_pairs(self) -> None:
        # l pairs alternate by order (like the compiler's loop // 2), so two
        # adjacent pairs are separate loops, not nesting.
        assert run_program("a" + "lsl" + "a" + "lsl" + "k;") == "\x00"

    def test_loop_exits_and_execution_continues(self) -> None:
        # after the loop runs 1 down to 0, execution continues past it.
        assert run_program("a" + "lsl" + "a" + "k;") == "\x01"

    def test_unmatched_loop_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run_program("ak;l")


class TestGenerator:
    def test_generated_program(self) -> None:
        from esolangs.tools.text.other import home_row

        assert run_program(home_row("Hello, World!")) == "Hello, World!"


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("a", ScriptedIO())
        before = machine.snapshot()
        machine.step()  # a increments the current cell
        assert machine.snapshot() != before
        assert machine.grid[0] == 1

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.home_row import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("ak;", ScriptedIO())) is True

    def test_loop_is_detected_as_a_cycle(self) -> None:
        # all: a increments cell 0 to 1, then the loop body is empty, so
        # the closing l jumps back to itself forever with the cell
        # unchanged -- a genuine state cycle, not unbounded growth.
        from esolangs.interpreters.tape_based.home_row import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("all", ScriptedIO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.grid[0] == 0
