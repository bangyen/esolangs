"""Unit tests for the Home Row interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.home_row import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    StateViewContract,
)


def run_program(code: str) -> str:
    io = ScriptedIO("")
    run(code, io)
    return io.getvalue()


_OUTPUT = {
    # cells are unbounded: 0 - 1 = -1, printed as its low byte
    "subtract": ("sk;", "\xff"),
    "semicolon_halts": ("ak;ak;", "\x01"),
    # increment cell 0, move down, increment cell 5, move back up (d x4
    # wraps), and print cell 0.
    "move_then_edit_distinct_cells": ("a" + "d" + "a" + "d" * 4 + "k;", "\x01"),
    # cell 0 is zero, so j skips the k.
    "jump_skips_next_on_zero": ("jk;", ""),
    "jump_does_not_skip_on_nonzero": ("ajk;", "\x01"),
    # ``j`` steps over the command after it, wherever it sits.
    "jump_skips_relative_to_itself": ("ffjak;", "\x00"),
    # aa l s l k; : the body decrements 2 down to 0, so k prints NUL.
    "loop_runs_while_nonzero": ("aa" + "l" + "s" + "l" + "k;", "\x00"),
    # cell is zero, so the body never runs and nothing prints.
    "loop_skips_when_zero": ("l" + "a" + "l" + "k;", "\x00"),
    # after the loop runs 1 down to 0, execution continues past it.
    "loop_exits_and_execution_continues": ("a" + "lsl" + "a" + "k;", "\x01"),
}


@pytest.mark.parametrize(("code", "expected"), _OUTPUT.values(), ids=list(_OUTPUT))
def test_output(code, expected) -> None:
    assert run_program(code) == expected


class TestBasics:
    def test_print_and_reset(self) -> None:
        # 65 increments then k prints 'A' and resets the cell to zero.
        assert run_program("a" * 65 + "k;") == "A"
        # the cell is zero again, so a following k prints NUL
        assert run_program("a" * 65 + "k" + "k;") == "A\x00"


class TestPointer:
    def test_torus_wraps(self) -> None:
        # f four times returns to the same column (5x5), so the fifth cell
        # is cell 0 again: a fffff k prints the 1 from cell 0.
        assert run_program("af" * 5 + "k;") == "\x01"
        # d wraps the bottom row back to the top the same way.
        assert run_program("ad" * 5 + "k;") == "\x01"

    def test_down_lands_on_the_next_row(self) -> None:
        """``d`` moves a whole row forward, not backward."""
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("d", ScriptedIO())
        machine.step()
        assert machine.ptr == 5

    def test_forward_wraps_at_the_row_edge(self) -> None:
        """``f`` returns to the start of its row rather than crossing into
        the next.
        """
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("f", ScriptedIO())
        machine.step()
        assert machine.ptr == 1

        machine = _Machine("fffff", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.ptr == 0


class TestLoop:
    def test_unmatched_loop_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run_program("ak;l")


class TestLongProgram:
    def test_multiply_loops_print_hello_world(self) -> None:
        """Thirteen multiply-loops end to end, one per character."""
        program = (
            "aaaaaaaalfaaaaaaaaaffffslfkffffaaaaaaaaaalfaaaaaaaaaaffffslfakffffaa"
            "aaaaaaalfaaaaaaaaaaaaffffslfkffffaaaaaaaaalfaaaaaaaaaaaaffffslfkffff"
            "aaaaaaaaaalfaaaaaaaaaaaffffslfakffffaaaalfaaaaaaaaaaaffffslfkffffaaa"
            "alfaaaaaaaaffffslfkffffaaaaaaalfaaaaaaaaaaaaffffslfaaakffffaaaaaaaaa"
            "alfaaaaaaaaaaaffffslfakffffaaaaaaaalfaaaaaaaaaaaaaaffffslfaakffffaaa"
            "aaaaaalfaaaaaaaaaaaaffffslfkffffaaaaaaaaaalfaaaaaaaaaaffffslfkffffaa"
            "aalfaaaaaaaaffffslfakffff;"
        )
        assert run_program(program) == "Hello, World!"


class TestStepMachine:
    def test_snapshot_changes_after_a_step(self) -> None:
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("a", ScriptedIO())
        before = machine.snapshot()
        machine.step()  # a increments the current cell
        assert machine.snapshot() != before
        assert machine.grid[0] == 1

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.tape_based.home_row import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.grid[0] == 0


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.home_row import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract, StateViewContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    halting_program = "ak;"
    looping_program = "all"
    state_views = ("ind", "ip", "memory")
    viewing_program = "ak;"
