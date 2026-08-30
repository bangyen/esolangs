"""Unit tests for Dig interpreter.

Tests cover Dig commands and example programs from esolangs.org.
Dig is a 2D esoteric programming language with a mole (pointer) that moves on a
grid. Movement commands work overground; work commands only function underground
after digging with ``$``. The value read by ``$``/``#``/``%`` and the operators
is the first digit adjacent to the command (up, right, down, left).
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.grid_based.dig import run
from esolangs.interpreters.io import IO, ScriptedIO


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    """Run a Dig program (patching input) and return its stdout."""
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, io=IO())
    return buffer.getvalue()


class TestDigHaltAndMovement:
    """Test overground movement commands."""

    def test_halt_command(self) -> None:
        """Test @ halt command."""
        assert run_and_capture(["@"]) == ""

    def test_move_right_then_halt(self) -> None:
        """Test simple movement with halt."""
        assert run_and_capture([">@"]) == ""

    def test_work_commands_ignored_overground(self) -> None:
        """Test that work commands do nothing while overground."""
        assert run_and_capture([">H:@", "  2 "]) == ""


class TestDigUndergroundCommands:
    """Test work commands that only function underground."""

    def test_print_initial_zero(self) -> None:
        """Test that : prints the mole's initial value of 0."""
        assert run_and_capture([">$:", " 2 "]) == "0"

    def test_print_digit(self) -> None:
        """Test that a digit sets the mole and : outputs it."""
        assert run_and_capture([">$5:", " 2 "]) == "5"

    def test_last_digit_wins(self) -> None:
        """Test that consecutive digits keep only the last value."""
        assert run_and_capture([">$99:", " 3 "]) == "9"

    def test_print_character(self) -> None:
        """Test that letters set the mole to their ASCII value."""
        assert run_and_capture([">$H:", " 2 "]) == "H"

    def test_newline_output(self) -> None:
        """Test that % with a 1 beside it outputs a newline."""
        assert run_and_capture([">$%:", " 21"]) == "\n"

    def test_space_output(self) -> None:
        """Test that % with a 0 beside it outputs a space."""
        assert run_and_capture([">$%:", " 20"]) == " "


class TestDigArithmetic:
    """Test the arithmetic operators against an adjacent digit."""

    def test_addition(self) -> None:
        assert run_and_capture([">$ 3+:", " 4  2 "]) == "5"

    def test_subtraction(self) -> None:
        assert run_and_capture([">$ 7-:", " 4  3 "]) == "4"

    def test_multiplication(self) -> None:
        assert run_and_capture([">$ 4*:", " 4  2 "]) == "8"

    def test_division(self) -> None:
        assert run_and_capture([">$ 9/:", " 4  3 "]) == "3"

    def test_large_result_printed_as_character(self) -> None:
        """Test that values >= 10 are printed as characters."""
        assert run_and_capture([">$ 6+:", " 4  5 "]) == "\x0b"


class TestDigInput:
    """Test the input commands."""

    def test_integer_input(self) -> None:
        """Test that ~ reads a single integer."""
        assert run_and_capture([">$~:", " 2 "], inputs=["7"]) == "7"

    def test_character_input(self) -> None:
        """Test that = reads a single character."""
        assert run_and_capture([">$=:", " 2 "], inputs=["A"]) == "A"


class TestDigExamplePrograms:
    """Test example programs from esolangs.org."""

    def test_hello_world(self) -> None:
        """Test the Hello World program from esolangs.org."""
        hello_world = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]
        assert run_and_capture(hello_world) == "Hello World!"

    def test_nand_gate(self) -> None:
        """Test the NAND gate program from esolangs.org."""
        nand_gate = [
            "'2  > $~ >$ 1:@",
            ">$~;#@2   3",
            "    > $~;#@2",
            "         > $0:@",
        ]
        for a, b, expected in [
            ("0", "0", "1"),
            ("0", "1", "1"),
            ("1", "0", "1"),
            ("1", "1", "0"),
        ]:
            assert run_and_capture(nand_gate, inputs=[a, b]) == expected


class TestDigEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_program(self) -> None:
        """Test that an empty program raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            run([], io=IO())

    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashing the mole."""
        with pytest.raises(ValueError, match="empty"):
            run(["\n"], io=IO())
        with pytest.raises(ValueError, match="empty"):
            run(["   ", "\t"], io=IO())

    def test_single_character_program(self) -> None:
        """Test a program containing only a halt command."""
        assert run_and_capture(["@"]) == ""

    def test_no_adjacent_digit_halts(self) -> None:
        """A work command with no adjacent digit is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$+:", "    "], io=IO())

    def test_divide_by_zero_halts(self) -> None:
        """Dividing by an adjacent zero is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$/", " 10"], io=IO())

    def test_empty_input_line_reads_zero(self) -> None:
        """An empty input line stores 0 in the mole."""
        assert run_and_capture([">$=:", " 2 "], inputs=[""]) == "0"

    def test_a_steer_digit_outside_zero_and_one_goes_straight(self) -> None:
        """``#`` turns on 1 and 0; every other digit holds the heading.

        The wiki spells out all three cases -- "Rotates Mole to left when
        value beside it is 0, and right when 1.  When it's neither of those,
        keep straight." -- so going straight is specified behaviour, and a
        change to the two arms above must not quietly take it away.
        """
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.interpreters.io import ScriptedIO

        def heading_after(digit: str) -> int:
            # "#" steers overground, so no "$" -- the mole starts at (0, 0)
            # heading right and reads the cell below the "#" at (0, 1).
            machine = _Machine([" #  ", f" {digit}  "], ScriptedIO(""))
            machine.step()  # the blank the mole starts on
            machine.step()  # "#"
            return machine.move

        straight = heading_after("2")
        assert heading_after("1") == (straight + 1) % 4, "1 turns right"
        assert heading_after("0") == (straight - 1) % 4, "0 turns left"
        for digit in "23456789":
            assert heading_after(digit) == straight, digit

    def test_a_whitespace_digit_outside_zero_and_one_is_inert(self) -> None:
        """``%`` loads a newline for 1 and a space for 0, nothing otherwise.

        Unlike ``#``, the wiki gives ``%`` only those two cases, so the rest
        are a gap it does not fill.  Leaving the mole alone is this
        interpreter's choice, and pinning it keeps the choice deliberate.
        """
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.interpreters.io import ScriptedIO

        def mole_after(digit: str) -> int:
            # "%" is a work command, so "$" has to open the underground
            # budget first; it reads the 1 below it, leaving room for one.
            machine = _Machine(["$%  ", f"1{digit}  "], ScriptedIO(""))
            machine.step()  # "$" loads the work budget
            machine.step()  # "%" selects
            return machine.mole

        assert mole_after("1") == 10  # newline
        assert mole_after("0") == 32  # space
        for digit in "23456789":
            assert mole_after(digit) == 0, digit

    def test_func_callback_breaks_out(self) -> None:
        """A func callback returning True halts the run at the next ``$``."""
        from esolangs.interpreters.grid_based.dig import run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run([">$5:@", " 2 "], io=IO(), func=lambda: True)
        assert buffer.getvalue() == ""


class TestStepMachine:
    def test_step_tracks_position_direction_and_mole(self) -> None:
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$5:", " 2 "], IO())
        assert (machine.row, machine.col, machine.move, machine.mole) == (0, 0, 1, 0)
        machine.step()  # > keeps facing right
        assert (machine.row, machine.col, machine.move) == (0, 1, 1)
        machine.step()  # $ digs: reads the adjacent digit (5) as the count
        assert machine.num == 5
        machine.step()  # 5 sets the mole and consumes one count
        assert (machine.mole, machine.num) == (5, 4)

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$=:", " 2 "], ScriptedIO("A"))
        for _ in range(2):  # move over, dig
            machine.step()
        before = machine.snapshot()
        machine.step()  # = reads the input line into the mole
        assert machine.snapshot() != before
        assert machine.mole == ord("A")
        assert machine.io.position() == 1

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine([">@"], IO())) is True

    def test_looping_ring_is_detected_as_a_cycle(self) -> None:
        """A mole orbiting a closed direction ring never halts or leaves."""
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine([">'", "^<"], IO())) is False

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">"], io=IO())
        for _ in range(200):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        state = machine.snapshot()
        machine.step()  # stepping a halted machine must not raise
        assert machine.snapshot() == state
