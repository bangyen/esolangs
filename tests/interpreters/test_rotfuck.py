"""Unit tests for the ROTfuck interpreter.

The rotation makes a raw program's characters drift along ``+-><,.[]``, so
the interesting property is that a position ``i`` whose source character is
the ``i``-fold inverse rotation of a command executes exactly that command
when the pointer reaches it.  ``build`` encodes a sequence of *effective*
commands that way, letting the tests read like plain brainfuck while pinning
the rotation semantics.

Brackets match dynamically: when a ``[`` or ``]`` fires it rotates the
program first and then seeks for its partner in the rotated program, so
partners need not (and usually do not) exist at the same positions in the
source.  A bracket that fires with no partner in the rotated program is a
runtime error.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.rotfuck import run

_CHAIN = "+-><,.[]"


def build(commands: str) -> str:
    """Encode ``commands`` as a ROTfuck program.

    The character at position ``i`` is the ``i``-fold inverse rotation of
    the command it should execute when the pointer reaches it.
    """
    return "".join(_CHAIN[(_CHAIN.index(c) - i) % 8] for i, c in enumerate(commands))


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestRotation:
    def test_program_rotates_after_every_command(self) -> None:
        # two raw ','s: the first reads 'A', then the program rotates so the
        # second ',' is now '.', which prints the cell.
        assert run_program(",,", "A") == "A"

    def test_single_command(self) -> None:
        assert run_program(build(".")) == "\x00"

    def test_build_encoding(self) -> None:
        assert run_program(build("+" * 65 + ".")) == "A"


class TestTape:
    def test_cell_wraps(self) -> None:
        assert run_program(build("+" * 256 + ".")) == "\x00"

    def test_movement(self) -> None:
        assert run_program(build("++>++<.>.>")) == "\x02\x02"

    def test_left_clamped(self) -> None:
        """< at the left edge does nothing (matches the Brainfuck semantics)."""
        assert run_program(build("<<.")) == "\x00"

    def test_empty_program(self) -> None:
        assert run_program("") == ""

    def test_comments_ignored(self) -> None:
        # trailing comments are skipped by the pointer and never rotate
        assert run_program(build("+.") + "abc") == "\x01"
        assert run_program("xyz") == ""


class TestIO:
    def test_input_echo(self) -> None:
        assert run_program(build(",>,<.>."), "A\nB") == "AB"

    def test_input_running_out_raises_eof(self) -> None:
        io = ScriptedIO("")
        with pytest.raises(EOFError):
            run(build(","), io)


class TestBrackets:
    def test_wiki_cat_example_runs(self) -> None:
        """The wiki's `,[` cat no longer errors: the ] finds a [ dynamically."""
        assert run_program(",[", "x") == ""

    def test_backward_jump_fires_in_rotated_program(self) -> None:
        """A ] fires, rotates, and jumps back to a [ found in the result.

        In ``+<.]>`` the fired ``]`` first jumps back to the ``[`` of ``[+``
        and later to the ``[`` of ``[-<.``: neither partner exists in the
        source, so a static match (as a raw brainfuck would do) has no
        target at all.
        """
        assert run_program("+<.]>", "x") == ""

    def test_forward_skip_over_nested_bracket(self) -> None:
        """A skipped ``[`` seeks its partner past a nested ``[``."""
        assert run_program("[[.].]") == ""

    def test_backward_jump_over_nested_bracket(self) -> None:
        """A fired ``]`` jumps back across a nested ``]`` in the rotation."""
        assert run_program("<+..>[]") == "\x01"

    def test_unmatched_bracket_halts_when_executed(self) -> None:
        """A fired bracket with no partner in the rotated program errors."""
        with pytest.raises(HaltError):
            run_program("[.]")
        with pytest.raises(HaltError):
            run_program("+[]")
        with pytest.raises(HaltError):
            run_program(build("+]"))
        with pytest.raises(HaltError):
            run_program("[")

    def test_unmatched_bracket_that_never_runs_is_fine(self) -> None:
        """Unbalanced sources are legal; only execution matters."""
        assert run_program(build(".")) == "\x00"


class TestStepMachine:
    def test_step_tracks_tape_cursor_and_rotation(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        machine = _Machine(build("+."), ScriptedIO())
        assert (machine.ind, machine.ptr, list(machine.tape)) == (0, 0, [0])
        machine.step()  # + increments the cell and rotates the program
        assert machine.tape == [1]
        assert machine.prog.rotation() == 1
        machine.step()  # . prints the cell and rotates again
        assert machine.io.getvalue() == "\x01"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _Machine

        assert hash(_Machine(".", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.tape_based.rotfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine(".", ScriptedIO())) is True
