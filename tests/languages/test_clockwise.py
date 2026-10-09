"""Clockwise through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs.tui import render, replay
from tests.stdin_check import _check_stdin
from tests.test_tui import _frame, _highlighted


class TestPrivateStdinCheckSaysWhatItCanActuallyCheck:
    """Its help listed "the wrong number of lines" among what it catches
    without a table.  For most languages it cannot.
    """

    def test_a_line_per_bit_language_accepts_any_count(self) -> None:
        """Not a bug -- a count needs an arity, and only a table has one."""
        for stdin in ("", "1", "101"):
            _check_stdin("brainfuck", stdin)

    def test_the_table_is_what_catches_the_count(self) -> None:
        """The other half of the claim: with one, the count is checked."""
        with pytest.raises(esolangs.ArgumentError):
            _check_stdin("brainfuck", "1\n0\n1\n", "0110")

    def test_a_one_line_language_does_catch_a_stray_line(self) -> None:
        """Which is why the help can still claim a shape check at all."""
        with pytest.raises(esolangs.ArgumentError, match="unexpected character"):
            _check_stdin("Clockwise", "1\n0\n")


class TestAgainstTheInterpreter:
    """That the highlighted character is the op the VM is about to run."""

    @pytest.mark.parametrize("step", [0, 5, 11])
    def test_brainfuck_highlight_is_the_next_command(self, step: int) -> None:
        program = "+++>++[<->]<."
        frame = replay("brainfuck", program, "", step)
        marked = _highlighted(render(frame))
        if frame.ip is None:
            pytest.skip("halted with no position")
        assert isinstance(frame.ip, int)
        assert marked == program[frame.ip]
        assert marked in "+-<>[].,"

    def test_a_grid_language_highlight_is_a_real_cell(self) -> None:
        program = "\n".join(["o  v", "   <"])
        frame = _frame(program, (1, 3), language="Clockwise", ip_shape="grid")
        assert _highlighted(render(frame)) == "<"
