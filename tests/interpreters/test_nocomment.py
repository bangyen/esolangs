"""Unit tests for the NoComment interpreter.

NoComment is a full wiki language: 10 commands (``i d c l r n f s b o``)
over a byte tape and a byte stack.  Non-command characters are errors (the
wiki allows no comments), as are stack underflow and jumps out of code
space.  These tests pin the plain semantics and the parity with the
transpiled brainfuck subset.
"""

import importlib
import io
from contextlib import redirect_stdout

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

nocomment = importlib.import_module("esolangs.interpreters.tape_based.nocomment")


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        nocomment.run(code, IO())
    return buffer.getvalue()


class TestNoComment:
    def test_output_character(self) -> None:
        assert run_and_capture("c" + "i" * 65 + "o") == "A"

    def test_cell_clears(self) -> None:
        """c resets the cell, so a following o prints a NUL."""
        assert run_and_capture("ciio") == "\x02"
        assert run_and_capture("co") == "\x00"

    def test_cell_wraps(self) -> None:
        assert run_and_capture("c" + "i" * 256 + "o") == "\x00"
        assert run_and_capture("do") == "\xff"

    def test_pointer_wraps(self) -> None:
        """The static tape's pointer wraps to the opposite end (per the wiki)."""
        assert run_and_capture("c" + "i" * 65 + "r" + "o") == "\x00"
        assert run_and_capture("c" + "i" * 65 + "r" + "i" * 70 + "o") == "F"
        # l at cell 0 wraps to cell 4095, a fresh zero cell
        assert run_and_capture("c" + "i" * 65 + "l" + "o") == "\x00"
        assert run_and_capture("c" + "i" * 65 + "r" + "l" + "o") == "A"

    def test_tape_size_is_configurable(self) -> None:
        """The wiki fixes the wrap but not the size, so the size is a knob.

        The size is observable through that wrap -- cell 0 steps left to
        ``tape - 1`` -- so this pins the argument reaching *both* wrap sites
        rather than only the allocation.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _TAPE, _Machine

        assert _TAPE == 4096  # the default stays put; moving it moves behaviour

        for size in (2, 512, 8192):
            left = _Machine("l", ScriptedIO(), size)
            left.step()
            assert left.ptr == size - 1

            right = _Machine("r" * size, ScriptedIO(), size)
            while not right.halted:
                right.step()
            assert right.ptr == 0  # a full lap returns to the origin

    def test_tape_size_must_be_positive(self) -> None:
        """A tape with no cells has no cell to point at."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine

        for size in (0, -1):
            with pytest.raises(ValueError, match="at least one cell"):
                _Machine("i", ScriptedIO(), size)

    def test_stack_push_pop(self) -> None:
        """n pushes the cell; f pops into it."""
        assert run_and_capture("c" + "i" * 65 + "n" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "r" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "n" + "f" + "f" + "o") == "A"

    def test_skip_forward(self) -> None:
        """s skips X commands forward when the current cell is nonzero."""
        # cell = 2, push 2: skip the two i's, print cell 2
        assert run_and_capture("cii" + "n" + "s" + "ii" + "o") == "\x02"
        assert run_and_capture("ci" + "n" + "s" + "i" + "o") == "\x01"

    def test_jump_back(self) -> None:
        """b jumps back X-1 and loops until the cell reaches zero.

        The suite reached ``b`` only through the out-of-range error, so a
        backward jump was never actually taken.  Here ``n`` pushes 2 and the
        body decrements, so the jump fires once and the loop ends: the
        stack still holds its 2 afterwards, which is what makes the jump a
        peek rather than a pop.
        """
        assert run_and_capture("ciindbo") == "\x00"
        assert run_and_capture("ciindbdo") == "\xff"

    def test_jump_needs_a_nonzero_cell(self) -> None:
        """s and b do nothing when the current cell is zero.

        Both jumps are guarded on the cell *and* the stack, and every test
        ran them with both satisfied -- so requiring either one alone would
        have passed.  Clearing the cell first leaves the jump untaken and
        the skipped commands run.
        """
        assert run_and_capture("ciincsio") == "\x01"
        assert run_and_capture("cbo") == "\x00"

    def test_jump_needs_a_stacked_value(self) -> None:
        """s and b do nothing when the stack is empty.

        Nothing is pushed here, so the jump has no distance to read: it is
        skipped silently rather than raising, and the following commands
        all run.
        """
        assert run_and_capture("cisio") == "\x02"
        assert run_and_capture("cibo") == "\x01"

    def test_jump_target_is_checked_one_past_the_jump(self) -> None:
        """The range check looks at the command the jump lands on.

        ``test_jump_out_of_range_is_error`` overshoots by a wide margin, so
        the exact edge went unchecked: the target could be computed one
        either side and still be far outside.  Here the skip of 2 from the
        ``s`` targets one past the last command -- rejected by a single
        position, which computing the target one lower, or comparing the
        upper bound inclusively, would have allowed.
        """
        with pytest.raises(HaltError):
            run_and_capture("ciinsio")

    def test_backward_jump_of_zero_leaves_the_code(self) -> None:
        """A backward jump of 0 targets one past the jump, which is off the end.

        Pushing a zero and jumping back by it gives a target of ``ind + 1``
        -- past the last command here, so it is rejected.  It is the only
        way to reach the low edge of the range check, where a bound of 1 or
        an exclusive comparison would behave differently.
        """
        with pytest.raises(HaltError):
            run_and_capture("nib")

    def test_a_backward_jump_landing_on_the_first_command_is_allowed(self) -> None:
        """Zero is a legal target: the jump lands on the first command.

        ``test_backward_jump_of_zero_leaves_the_code`` names the low edge but
        does not reach it -- jumping back by zero targets ``ind + 1``, which
        is above it.  The edge is reached only when the stacked value is one
        more than the jump's own index, and it is a *valid* landing: the
        program continues from the top and runs to completion, printing 6.
        A floor of 1, or an exclusive comparison, halts here instead.
        """
        assert run_and_capture("iisbinbo") == "\x06"

    def test_every_non_command_character_is_rejected(self) -> None:
        """No character outside the ten commands is executable -- no no-ops exist.

        The jump commands share one branch, so ``s`` and ``b`` form a set,
        and a set can be widened to swallow a character that should have
        been malformed.  Pinning that with one chosen sentinel would only
        pin the sentinel, so this sweeps the whole printable range against
        the command set itself: whatever a widened set admits, it is in here.
        The preceding ``iin`` leaves a nonzero cell and a stacked value, so
        a character wrongly read as a jump would act rather than be ignored.
        """
        for char in map(chr, range(0x20, 0x7F)):
            if char in "idclrnfsbo":
                continue
            with pytest.raises(ValueError, match="unrecognized NoComment command"):
                run_and_capture("iin" + char + "o")

    def test_unrecognized_command_is_error(self) -> None:
        """The wiki allows no comments; a non-command is a malformed program."""
        with pytest.raises(ValueError, match="unrecognized NoComment command"):
            run_and_capture("x" + "c" + "i" * 65 + "o")

    def test_stack_underflow_is_error(self) -> None:
        """Popping an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 65 + "f" + "o")

    def test_jump_out_of_range_is_error(self) -> None:
        """A forward or backward jump leaving the code space is invalid."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "s" + "o")
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "b" + "o")

    def test_generator_round_trips(self) -> None:
        for text in ("Hello, World!", "Hi", "\x00\x01"):
            assert (
                esolangs.run("NoComment", esolangs.generate("NoComment", text)) == text
            )


class TestStepMachine:
    def test_step_tracks_tape_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine

        machine = _Machine("cino", ScriptedIO())
        assert (machine.ptr, machine.ind, machine.stack) == (0, 0, [])
        machine.step()  # c clears the cell
        machine.step()  # i increments it
        machine.step()  # n pushes the cell
        assert machine.stack == [1]
        machine.step()  # o prints the cell
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 4


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.nocomment import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "co"
    halting_program = "ciio"
    looping_program = "inbb"
