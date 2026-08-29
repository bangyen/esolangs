"""Unit tests for the 6-5 interpreter."""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO

sixfive = importlib.import_module("esolangs.interpreters.tape_based.six_five")


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        sixfive.run(code, IO())
    return buffer.getvalue()


HELLO_WORLD = "\n".join(
    [
        "666666666666A C",
        "66665A C",
        "662AA C",
        "626262A C",
        "9999999999995A C",
        "99A C",
        "55555555555A C",
        "6666A C",
        "626262A C",
        "9A C",
        "95959A C",
    ]
)


class TestSixFive:
    def test_add_six(self) -> None:
        assert run_and_capture("66666666A0") == "0"

    def test_add_five(self) -> None:
        assert run_and_capture("5555555A0") == "#"

    def test_input_echo(self) -> None:
        assert run_and_capture("BA0", inputs=["X"]) == "X"

    def test_halt(self) -> None:
        assert run_and_capture("0") == ""

    def test_hello_world(self) -> None:
        """Hello World program from esolangs.org."""
        assert run_and_capture(HELLO_WORLD) == "Hello, World"

    def test_move_right_twice(self) -> None:
        """1 moves the pointer right two cells."""
        assert run_and_capture("15555555555A0") == "2"

    def test_move_left(self) -> None:
        """3 moves the pointer left."""
        assert run_and_capture("313A0") == "\x00"

    def test_the_two_moves_are_different_sizes(self) -> None:
        """``1`` goes right by two, ``3`` left by one, and the tape follows.

        Both moves were only ever made in combinations that return to the
        cell they started from -- ``313`` is right two, left one, left one
        -- so neither step size was pinned, and neither was how far the
        tape grows to meet the pointer.  Writing a distinct value either
        side of one move says where it landed.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        # 1 lands on cell 2, growing the tape to three; 3 steps back to 1
        machine = _Machine("166666666A366666666A0", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "00"
        assert (machine.cell, machine.tape) == (1, [0, 48, 48])

        # two moves right compound rather than landing on a fixed cell
        twice = _Machine("11", ScriptedIO())
        while not twice.halted:
            twice.step()
        assert (twice.cell, len(twice.tape)) == (4, 5)

    def test_zero_halts_before_the_rest_of_the_program(self) -> None:
        """``0`` halts, so nothing after it runs.

        Every program ends with ``0``, where halting and simply running out
        of tokens look the same.  Putting it first says which one happened.
        """
        assert run_and_capture("066666666A0") == ""

    def test_multiple_outputs(self) -> None:
        assert run_and_capture("5A5A0") == "\x05\n"

    def test_input_adds_to_cell(self) -> None:
        """B stores input in the cell, then arithmetic applies on top."""
        assert run_and_capture("B5A0", inputs=["A"]) == "F"

    def test_jump_to_four(self) -> None:
        """8n jumps to the nth 4 marker."""
        assert run_and_capture("81A4A0") == "\x00"

    def test_jump_to_second_four(self) -> None:
        """8n jumps past the nth 4, skipping code before it."""
        assert run_and_capture("825A46A4A0") == "\x00"

    def test_skip_when_equal(self) -> None:
        """7n skips the next instruction when the cell equals n."""
        assert run_and_capture("55A7A5A0") == "\n\n"

    def test_negative_cell_output_halts(self) -> None:
        """Outputting a negative cell value is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("2A")


class TestComments:
    """``C`` starts a comment, unless it is the operand of a ``7`` or ``8``.

    No test used a ``C`` at all, so the whole comment path in the tokenizer
    ran only on programs that had none: the pattern could have matched a
    different letter, or nothing, and every program still agreed.
    """

    def test_a_comment_hides_the_rest_of_its_line(self) -> None:
        # without the strip, the commented-out program would run and print
        assert run_and_capture("6C66666666A0") == ""
        assert run_and_capture("66666666A0C66666666A0") == "0"

    def test_a_comment_ends_at_the_newline(self) -> None:
        assert run_and_capture("6C hidden\n66666666A0") == "6"

    def test_c_after_a_skip_is_its_operand(self) -> None:
        """A ``C`` following ``7``/``8`` is the value 12, not a comment.

        ``66`` leaves the cell at 12, so ``7C`` skips the instruction after
        it -- which is what distinguishes the operand reading from the
        comment one, since a comment would swallow the rest instead.
        """
        assert run_and_capture("667C66666666A0") == "6"

    def test_the_tokenizer_pairs_an_operand_with_its_skip(self) -> None:
        """Directly, because the pairing is invisible in the output.

        A ``7``/``8`` takes the single character after it, and a trailing
        one with nothing after it stands alone.  Reading two characters
        instead, or refusing to pair at the end of the program, changes the
        token list without changing what any program prints.
        """
        from esolangs.interpreters.tape_based.six_five import _tokens

        assert _tokens("7C") == ["7C"]
        assert _tokens("78") == ["78"]
        assert _tokens("7") == ["7"]
        assert _tokens("8") == ["8"]
        assert _tokens("7C1") == ["7C", "1"]
        assert _tokens("6C hidden") == ["6"]
        # Only 7 and 8 take an operand.  Any other character stands alone,
        # however the pair is spelled -- a wider set would swallow the
        # command after it.
        assert _tokens("X6") == ["X", "6"]
        assert run_and_capture("X66666666A0") == "0"


class TestStepMachine:
    def test_step_tracks_tape_cell_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        machine = _Machine("55A", ScriptedIO())
        assert (machine.ind, machine.cell, machine.tape) == (0, 0, [0])
        machine.step()  # 5 adds 5 to the cell
        assert machine.tape == [5]
        machine.step()  # 5 adds 5 more
        assert machine.tape == [10]
        machine.step()  # A prints the cell
        assert machine.io.getvalue() == "\n"
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 3

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine

        assert hash(_Machine("55A", ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("55A", ScriptedIO())) is True

    def test_8_jump_is_detected_as_a_cycle(self) -> None:
        """A 8n jump back to a 4 marker that never fires loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.six_five import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("481", ScriptedIO())) is False
