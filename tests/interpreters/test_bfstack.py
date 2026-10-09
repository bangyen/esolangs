"""Unit tests for the BFStack interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.stack_based.bfstack import run
from tests.interpreters.contract import (
    CycleContract,
    InputCursorContract,
    StateViewContract,
)
from tests.interpreters.runner import run_lines
from tests.raises import assert_rejected_with_hint, raises_message

run_and_capture = run_lines(run)


class TestBFStack:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param(">+.", "\x01", id="push_and_output"),
            # < pops the top of the stack.
            pytest.param(">+>+<.", "\x01", id="pop"),
            # A loop that zeroes its cell executes exactly once.
            pytest.param(">+[>+<-]>+.", "\x01", id="loop"),
            # [ jumps past its matching ] when the top is zero.
            pytest.param(">[>]", "", id="loop_skipped_when_zero"),
            # A skipped loop with nested [ brackets counts both.
            pytest.param(">[[-]]", "", id="loop_skip_nested"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        assert run_and_capture(code) == expected

    def test_a_pop_leaves_everything_below_it(self) -> None:
        """Popping removes one cell, not all but the bottom one."""
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + ".") == "\x03"
        assert run_and_capture(three + "<.") == "\x02"
        assert run_and_capture(three + "<<.") == "\x01"

    def test_a_decrement_rebuilds_the_stack_below_the_top(self) -> None:
        """``-`` replaces the top and leaves the rest where they were."""
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + "-.") == "\x02"
        assert run_and_capture(three + "-<.") == "\x02"

    def test_input(self) -> None:
        """, pushes ASCII input onto the stack."""
        assert run_and_capture(">,.", inputs=["Z"]) == "Z"

    def test_input_adds_a_cell_rather_than_overwriting_one(self) -> None:
        """``,`` pushes, so what was on top before is still underneath."""
        assert run_and_capture(">+,<.", inputs=["Z"]) == "\x01"

    def test_loop_skip_unmatched(self) -> None:
        """A skipped [ with no closing ] is a malformed program."""
        with raises_message(ValueError, "unmatched '['"):
            run_and_capture(">[")

    def test_output_on_empty_stack_raises(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture(".")

    def test_unmatched_closing_bracket_raises(self) -> None:
        """] with no matching [ is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture(">]")

    def test_cells_wrap_at_a_byte(self) -> None:
        """+ and - wrap modulo 256, in both directions."""
        assert run_and_capture(">-.") == "\xff"
        assert run_and_capture(">" + "+" * 256 + ".") == "\x00"
        assert run_and_capture(">" + "+" * 255 + ".") == "\xff"

    def test_pop_on_empty_stack_raises(self) -> None:
        """< on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("<")

    def test_arithmetic_on_empty_stack_raises(self) -> None:
        """+ and - need a value to act on."""
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
        machine.step()  # > pushes 0
        assert machine.stk == (0,)
        machine.step()  # + increments the top
        assert machine.stk == (1,)
        machine.step()  # . prints it
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 3

    def test_lst_holds_the_positions_of_entered_loops(self) -> None:
        """``lst`` is the loop stack: a ``[`` that is entered records itself."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+[", ScriptedIO())
        for _ in range(3):
            machine.step()
        assert machine.lst == (2,)  # the [ at index 2, entered with a 1 on top

    def test_memory_is_empty_because_the_store_is_the_stack(self) -> None:
        """``memory`` and ``stack`` are different views, not one field twice."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert not hasattr(machine, "memory")
        assert machine.stack == [1]

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        """The cursor is moved to the end before the error is raised."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">[", ScriptedIO())
        machine.step()  # > pushes 0
        with raises_message(ValueError, "unmatched '['"):
            machine.step()  # [ scans for a partner and runs off the end
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
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    halting_program = ">+."
    looping_program = ">+[]"
    state_views = ("lst", "ip")
    # The loop test's own program: it enters a loop, so the loop stack
    # moves.
    viewing_program = ">+[>+<-]>+."
    reader = staticmethod(_reader)
    reading_program = ">,"  # > pushes 0, then , reads the first byte
    reading_stdin = "A\nB"
    steps_to_read = 2


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("BFStack", ">[", "close the loop")
