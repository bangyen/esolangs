"""Unit tests for the ROTfuck interpreter.

The rotation makes a raw program's characters drift along ``+-><,.[]``, so
the interesting property is that a position ``i`` whose source character is
the ``i``-fold inverse rotation of a command executes exactly that command
when the pointer reaches it.  ``build`` encodes a sequence of *effective*
commands that way, letting the tests read like plain brainfuck while pinning
the rotation semantics.
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
    def test_loop_skipped_when_zero(self) -> None:
        """A [ with a zero cell jumps past its partner, skipping the dot."""
        assert run_program("[.]") == ""

    def test_backward_jump_fires(self) -> None:
        # raw '+[]': the '+' sets the cell, the ']' (rotated in) jumps to
        # its partner, then the program runs out and halts.
        assert run_program("+[]") == ""

    def test_unmatched_bracket_halts_when_executed(self) -> None:
        """An executed bracket with no partner is an invalid operation."""
        with pytest.raises(HaltError):
            run_program(build("+]"))
        with pytest.raises(HaltError):
            run_program("[")

    def test_unmatched_bracket_that_never_runs_is_fine(self) -> None:
        """Unbalanced sources are legal; only execution matters."""
        assert run_program(build(".")) == "\x00"
