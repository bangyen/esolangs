r"""Unit tests for the NoComment interpreter."""

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
        r"""C resets the cell, so a following o prints a NUL."""
        assert run_and_capture("ciio") == "\x02"
        assert run_and_capture("co") == "\x00"

    def test_cell_wraps(self) -> None:
        assert run_and_capture("c" + "i" * 256 + "o") == "\x00"
        assert run_and_capture("do") == "\xff"

    def test_pointer_wraps(self) -> None:
        r"""The static tape's pointer wraps to the opposite end (per the wiki)."""
        assert run_and_capture("c" + "i" * 65 + "r" + "o") == "\x00"
        assert run_and_capture("c" + "i" * 65 + "r" + "i" * 70 + "o") == "F"
        # l at cell 0 wraps to cell.
        assert run_and_capture("c" + "i" * 65 + "l" + "o") == "\x00"
        assert run_and_capture("c" + "i" * 65 + "r" + "l" + "o") == "A"

    def test_tape_size_is_configurable(self) -> None:
        r"""The wiki fixes the wrap but not the size, so the size is a knob."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _TAPE, _Machine

        assert _TAPE == 4096  # the default stays put; moving.

        for size in (2, 512, 8192):
            left = _Machine("l", ScriptedIO(), size)
            left.step()
            assert left.ptr == size - 1

            right = _Machine("r" * size, ScriptedIO(), size)
            while not right.halted:
                right.step()
            assert right.ptr == 0  # a full lap returns to the.

    def test_tape_size_must_be_positive(self) -> None:
        r"""A tape with no cells has no cell to point at."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine

        for size in (0, -1):
            with pytest.raises(ValueError, match="at least one cell"):
                _Machine("i", ScriptedIO(), size)

    def test_a_one_cell_tape_is_accepted(self) -> None:
        r"""One cell is the smallest legal tape, and the guard's own edge."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            nocomment.run("c" + "i" * 65 + "rlo", IO(), tape=1)
        assert buffer.getvalue() == "A"

    def test_run_forwards_the_tape_size(self) -> None:
        r"""``run`` passes its ``tape`` through, rather than taking the default."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            nocomment.run("c" + "i" * 65 + "rro", IO(), tape=2)
        assert buffer.getvalue() == "A"

    def test_stack_push_pop(self) -> None:
        r"""N pushes the cell; f pops into it."""
        assert run_and_capture("c" + "i" * 65 + "n" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "r" + "f" + "o") == "A"
        assert run_and_capture("c" + "i" * 65 + "n" + "n" + "f" + "f" + "o") == "A"

    def test_skip_forward(self) -> None:
        r"""S skips X commands forward when the current cell is nonzero."""
        # cell = 2, push 2: skip the.
        assert run_and_capture("cii" + "n" + "s" + "ii" + "o") == "\x02"
        assert run_and_capture("ci" + "n" + "s" + "i" + "o") == "\x01"

    def test_jump_back(self) -> None:
        r"""B jumps back X-1 and loops until the cell reaches zero."""
        assert run_and_capture("ciindbo") == "\x00"
        assert run_and_capture("ciindbdo") == "\xff"

    def test_jump_needs_a_nonzero_cell(self) -> None:
        r"""S and b do nothing when the current cell is zero."""
        assert run_and_capture("ciincsio") == "\x01"
        assert run_and_capture("cbo") == "\x00"

    def test_jump_needs_a_stacked_value(self) -> None:
        r"""S and b do nothing when the stack is empty."""
        assert run_and_capture("cisio") == "\x02"
        assert run_and_capture("cibo") == "\x01"

    def test_jump_target_is_checked_one_past_the_jump(self) -> None:
        r"""The range check looks at the command the jump lands on."""
        with pytest.raises(HaltError):
            run_and_capture("ciinsio")

    def test_backward_jump_of_zero_leaves_the_code(self) -> None:
        r"""A backward jump of 0 targets one past the jump, which is off the."""
        with pytest.raises(HaltError):
            run_and_capture("nib")

    def test_a_backward_jump_landing_on_the_first_command_is_allowed(self) -> None:
        r"""Zero is a legal target: the jump lands on the first command."""
        assert run_and_capture("iisbinbo") == "\x06"

    def test_every_non_command_character_is_rejected(self) -> None:
        r"""No character outside the ten commands is executable -- no no-ops."""
        for char in map(chr, range(0x20, 0x7F)):
            if char in "idclrnfsbo":
                continue
            with pytest.raises(ValueError, match="unrecognized NoComment command"):
                run_and_capture("iin" + char + "o")

    def test_unrecognized_command_is_error(self) -> None:
        r"""The wiki allows no comments; a non-command is a malformed program."""
        with pytest.raises(ValueError, match="unrecognized NoComment command"):
            run_and_capture("x" + "c" + "i" * 65 + "o")

    def test_stack_underflow_is_error(self) -> None:
        r"""Popping an empty stack is an invalid operation."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 65 + "f" + "o")

    def test_jump_out_of_range_is_error(self) -> None:
        r"""A forward or backward jump leaving the code space is invalid."""
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "s" + "o")
        with pytest.raises(HaltError):
            run_and_capture("c" + "i" * 10 + "n" + "b" + "o")

    def test_a_long_increment_run_prints_hello_world(self) -> None:
        r"""Thirteen characters walked out on one cell with ``i``/``d``."""
        program = (
            "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
            "iiiioiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiooiiiodddddddddddddddddddd"
            "dddddddddddddddddddddddddddddddddddddddddddddddoddddddddddddoiiiiiii"
            "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiiiiiiiiiiiii"
            "iiiiioiiioddddddoddddddddodddddddddddddddddddddddddddddddddddddddddd"
            "dddddddddddddddddddddddddo"
        )
        assert esolangs.run("NoComment", program) == "Hello, World!"


class TestStepMachine:
    def test_step_tracks_tape_stack_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.nocomment import _Machine

        machine = _Machine("cino", ScriptedIO())
        assert (machine.ptr, machine.ind, machine.stack) == (0, 0, ())
        machine.step()  # c clears the cell.
        machine.step()  # i increments it.
        machine.step()  # n pushes the cell.
        assert machine.stack == (1,)
        machine.step()  # o prints the cell.
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.ind == 4


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.nocomment import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    r"""The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "co"
    halting_program = "ciio"
    looping_program = "inbb"
