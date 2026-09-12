r"""Unit tests for the BFStack interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.stack_based.bfstack import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestBFStack:
    def test_push_and_output(self) -> None:
        assert run_and_capture(">+.") == "\x01"

    def test_increment_twice(self) -> None:
        assert run_and_capture(">++.") == "\x02"

    def test_pop(self) -> None:
        r"""< pops the top of the stack."""
        assert run_and_capture(">+>+<.") == "\x01"

    def test_a_pop_leaves_everything_below_it(self) -> None:
        r"""Popping removes one cell, not all but the bottom one."""
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + ".") == "\x03"
        assert run_and_capture(three + "<.") == "\x02"
        assert run_and_capture(three + "<<.") == "\x01"

    def test_a_decrement_rebuilds_the_stack_below_the_top(self) -> None:
        r"""``-`` replaces the top and leaves the rest where they were."""
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + "-.") == "\x02"
        assert run_and_capture(three + "-<.") == "\x02"

    def test_input(self) -> None:
        r""", pushes ASCII input onto the stack."""
        assert run_and_capture(">,.", inputs=["Z"]) == "Z"

    def test_input_adds_a_cell_rather_than_overwriting_one(self) -> None:
        r"""``,`` pushes, so what was on top before is still underneath."""
        assert run_and_capture(">+,<.", inputs=["Z"]) == "\x01"

    def test_loop(self) -> None:
        r"""A loop that zeroes its cell executes exactly once."""
        assert run_and_capture(">+[>+<-]>+.") == "\x01"

    def test_loop_skipped_when_zero(self) -> None:
        r"""[ jumps past its matching ] when the top is zero."""
        assert run_and_capture(">[>]") == ""

    def test_loop_skip_nested(self) -> None:
        r"""A skipped loop with nested [ brackets counts both."""
        assert run_and_capture(">[[-]]") == ""

    def test_loop_skip_unmatched(self) -> None:
        r"""A skipped [ with no closing ] is a malformed program."""
        with pytest.raises(ValueError, match=r"^unmatched '\['$"):
            run_and_capture(">[")

    def test_output_on_empty_stack_raises(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture(".")

    def test_loop_on_empty_stack_raises(self) -> None:
        r"""[ on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("[")

    def test_unmatched_closing_bracket_raises(self) -> None:
        r"""] with no matching [ is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture(">]")

    def test_decrement(self) -> None:
        r"""- subtracts one from the top of the stack."""
        assert run_and_capture(">+-.") == "\x00"
        assert run_and_capture(">++-.") == "\x01"

    def test_cells_wrap_at_a_byte(self) -> None:
        r"""+ and - wrap modulo 256, in both directions."""
        assert run_and_capture(">-.") == "\xff"
        assert run_and_capture(">" + "+" * 256 + ".") == "\x00"
        assert run_and_capture(">" + "+" * 255 + ".") == "\xff"

    def test_pop_on_empty_stack_raises(self) -> None:
        r"""< on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("<")

    def test_arithmetic_on_empty_stack_raises(self) -> None:
        r"""+ and - need a value to act on."""
        with pytest.raises(HaltError):
            run_and_capture("+")
        with pytest.raises(HaltError):
            run_and_capture("-")


class TestStepMachine:
    def test_step_tracks_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+.", ScriptedIO())
        assert (machine.ind, machine.stk) == (0, ())
        machine.step()  # > pushes 0.
        assert machine.stk == (0,)
        machine.step()  # + increments the top.
        assert machine.stk == (1,)
        machine.step()  # .
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 3

    def test_lst_holds_the_positions_of_entered_loops(self) -> None:
        r"""``lst`` is the loop stack: a ``[`` that is entered records itself."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+[", ScriptedIO())
        for _ in range(3):
            machine.step()
        assert machine.lst == (2,)  # the [ at index 2, entered.

    def test_memory_is_empty_because_the_store_is_the_stack(self) -> None:
        r"""``memory`` and ``stack`` are different views, not one field twice."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert machine.memory == []
        assert machine.stack == [1]

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        r"""The cursor is moved to the end before the error is raised."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">[", ScriptedIO())
        machine.step()  # > pushes 0.
        with pytest.raises(ValueError, match=r"^unmatched '\['$"):
            machine.step()  # [ scans for a partner and.
        assert machine.halted
        assert machine.ind == 2


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.bfstack import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.bfstack import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    halting_program = ">+."
    looping_program = ">+[]"
    state_views = ("lst", "ip", "memory")
    # The loop test's own program:.
    # moves.
    # cells, its store is `stack`.
    viewing_program = ">+[>+<-]>+."
    constant_views = frozenset({"memory"})
    reader = staticmethod(_reader)
    reading_program = ">,"  # > pushes 0, then , reads the.
    reading_stdin = "A\nB"
    steps_to_read = 2
