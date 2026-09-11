"""Unit tests for the BFStack interpreter."""

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
        """< pops the top of the stack."""
        assert run_and_capture(">+>+<.") == "\x01"

    def test_a_pop_leaves_everything_below_it(self) -> None:
        """Popping removes one cell, not all but the bottom one.

        ``test_pop`` uses two cells, where dropping the top and keeping
        only the bottom are the same stack.  Three cells with distinct
        values separate them, and popping twice reads each in turn.
        """
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + ".") == "\x03"
        assert run_and_capture(three + "<.") == "\x02"
        assert run_and_capture(three + "<<.") == "\x01"

    def test_a_decrement_rebuilds_the_stack_below_the_top(self) -> None:
        """``-`` replaces the top and leaves the rest where they were.

        The arm is written as a rebuild, so the slice it keeps has to be
        everything but the top -- which one cell cannot show.  Popping
        after the decrement reads what the rebuild preserved.
        """
        three = ">+" + ">++" + ">+++"
        assert run_and_capture(three + "-.") == "\x02"
        assert run_and_capture(three + "-<.") == "\x02"

    def test_input(self) -> None:
        """, pushes ASCII input onto the stack."""
        assert run_and_capture(">,.", inputs=["Z"]) == "Z"

    def test_input_adds_a_cell_rather_than_overwriting_one(self) -> None:
        """``,`` pushes, so what was on top before is still underneath.

        ``test_input`` prints the byte immediately, which reads the same
        whether ``,`` pushed a cell or overwrote the one ``>`` made -- and
        the InputCursorContract's ``">,"`` reads as though a cell has to
        exist first, so the file pointed both ways at once.  Popping the
        read byte settles it: pushing leaves the 1 below it to print, while
        overwriting would have consumed it and left the stack empty.
        """
        assert run_and_capture(">+,<.", inputs=["Z"]) == "\x01"

    def test_loop(self) -> None:
        """A loop that zeroes its cell executes exactly once."""
        assert run_and_capture(">+[>+<-]>+.") == "\x01"

    def test_loop_skipped_when_zero(self) -> None:
        """[ jumps past its matching ] when the top is zero."""
        assert run_and_capture(">[>]") == ""

    def test_loop_skip_nested(self) -> None:
        """A skipped loop with nested [ brackets counts both."""
        assert run_and_capture(">[[-]]") == ""

    def test_loop_skip_unmatched(self) -> None:
        """A skipped [ with no closing ] is a malformed program.

        The message is matched whole rather than by the substring
        ``unmatched``, which any rewording keeping that one word would
        still satisfy.
        """
        with pytest.raises(ValueError, match=r"^unmatched '\['$"):
            run_and_capture(">[")

    def test_output_on_empty_stack_raises(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture(".")

    def test_loop_on_empty_stack_raises(self) -> None:
        """[ on an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("[")

    def test_unmatched_closing_bracket_raises(self) -> None:
        """] with no matching [ is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture(">]")

    def test_decrement(self) -> None:
        """- subtracts one from the top of the stack.

        Nothing in the suite used ``-`` outside a loop body whose output it
        never reached, so the whole line was unconstrained: subtracting,
        adding, or storing None to the top all passed.
        """
        assert run_and_capture(">+-.") == "\x00"
        assert run_and_capture(">++-.") == "\x01"

    def test_cells_wrap_at_a_byte(self) -> None:
        """+ and - wrap modulo 256, in both directions.

        ``test_increment_twice`` reaches 2, so the modulus was never
        approached from either side: one below zero and one above 255 are
        where a wrap at any other width would show.
        """
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
        """``lst`` is the loop stack: a ``[`` that is entered records itself.

        This is the piece of the machine nothing else names.  ``]`` does not
        scan backwards for its partner -- it pops the position the matching
        ``[`` pushed -- so the loop stack is what decides where a jump goes,
        and two runs on the same command with different loop stacks go
        different places.  ``state_views`` lists ``lst`` but the shared
        contract only checks that the name resolves and that *some* view
        moves, which ``ip`` alone satisfies, so a property returning a
        constant passed.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+[", ScriptedIO())
        for _ in range(3):
            machine.step()
        assert machine.lst == (2,)  # the [ at index 2, entered with a 1 on top

    def test_memory_is_empty_because_the_store_is_the_stack(self) -> None:
        """``memory`` and ``stack`` are different views, not one field twice.

        BFStack addresses no cells, so the VM's ``memory`` is deliberately
        empty and ``stack`` carries the data.  The contract's non-aliasing
        check compares the views before and after a run and passes as soon
        as any one of them moves, so ``memory`` quietly returning the data
        stack -- the exact aliasing that check is named for -- went unseen.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">+", ScriptedIO())
        for _ in range(2):
            machine.step()
        assert machine.memory == []
        assert machine.stack == [1]

    def test_an_unmatched_bracket_leaves_the_machine_halted(self) -> None:
        """The cursor is moved to the end before the error is raised.

        ``test_loop_skip_unmatched`` checks the message, and the message is
        all it checks -- the machine it was raised from is thrown away by
        ``run_and_capture``.  But where the cursor is left is deliberate:
        the scan that fails runs to the end of the code, and a caller that
        catches the ValueError should find a halted machine rather than one
        still sitting on the bracket, which is what stepping it again would
        otherwise re-raise from.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bfstack import _Machine

        machine = _Machine(">[", ScriptedIO())
        machine.step()  # > pushes 0
        with pytest.raises(ValueError, match=r"^unmatched '\['$"):
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
    state_views = ("lst", "ip", "memory")
    # The loop test's own program: it enters a loop, so the loop stack
    # moves.  `memory` is empty by design here -- BFStack addresses no
    # cells, its store is `stack` -- so it cannot move and says so.
    viewing_program = ">+[>+<-]>+."
    constant_views = frozenset({"memory"})
    reader = staticmethod(_reader)
    reading_program = ">,"  # > pushes 0, then , reads the first byte
    reading_stdin = "A\nB"
    steps_to_read = 2
