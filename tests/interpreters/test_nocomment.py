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

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""

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

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine

        assert hash(_Machine("co", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("ciio", ScriptedIO())) is True

    def test_back_jump_is_detected_as_a_cycle(self) -> None:
        """A jump back to a command that never changes state loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("inbb", ScriptedIO())) is False
