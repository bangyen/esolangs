r"""Unit tests for Dig interpreter."""

from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.dig import run
from esolangs.interpreters.io import IO, ScriptedIO
from tests.interpreters.contract import CycleContract, InputCursorContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    r"""Run a Dig program and return its stdout."""
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestDigHaltAndMovement:
    r"""Test overground movement commands."""

    def test_halt_command(self) -> None:
        r"""Test @ halt command."""
        assert run_and_capture(["@"]) == ""

    def test_move_right_then_halt(self) -> None:
        r"""Test simple movement with halt."""
        assert run_and_capture([">@"]) == ""

    def test_work_commands_ignored_overground(self) -> None:
        r"""Test that work commands do nothing while overground."""
        assert run_and_capture([">H:@", "  2 "]) == ""

    def test_a_letter_overground_does_not_steer(self) -> None:
        r"""Only ``^>'<`` set the heading; the mole keeps going right."""
        assert run_and_capture(["X$5:", " 2  "]) == "5"

    def test_the_halt_stops_code_that_follows_it(self) -> None:
        r"""``@`` ends the run, rather than the mole walking off the end."""
        assert run_and_capture(["@$5:", " 2  "]) == ""

    def test_the_mole_stops_at_the_bottom_row(self) -> None:
        r"""Walking off the bottom ends the run as cleanly as off the side."""
        assert run_and_capture(["'"]) == ""

    def test_a_right_turn_from_the_last_heading_wraps_to_the_first(self) -> None:
        r"""The heading is taken modulo four, the number of headings."""
        assert run_and_capture([" 1'", " #<"]) == ""


class TestDigUndergroundCommands:
    r"""Test work commands that only function underground."""

    def test_print_initial_zero(self) -> None:
        r"""Test that : prints the mole's initial value of 0."""
        assert run_and_capture([">$:", " 2 "]) == "0"

    def test_print_digit(self) -> None:
        r"""Test that a digit sets the mole and : outputs it."""
        assert run_and_capture([">$5:", " 2 "]) == "5"

    def test_last_digit_wins(self) -> None:
        r"""Test that consecutive digits keep only the last value."""
        assert run_and_capture([">$99:", " 3 "]) == "9"

    def test_print_character(self) -> None:
        r"""Test that letters set the mole to their ASCII value."""
        assert run_and_capture([">$H:", " 2 "]) == "H"

    def test_a_letter_underground_is_not_an_input_command(self) -> None:
        r"""Only ``=`` and ``~`` read; ``X`` is a letter like any other."""
        assert run_and_capture([">$X:", " 2 "]) == "X"

    def test_printing_clears_the_mole(self) -> None:
        r"""``:`` resets the mole to zero, which a second ``:`` reveals."""
        assert run_and_capture([">$3::", " 3   "]) == "30"

    def test_newline_output(self) -> None:
        r"""Test that % with a 1 beside it outputs a newline."""
        assert run_and_capture([">$%:", " 21"]) == "\n"

    def test_space_output(self) -> None:
        r"""Test that % with a 0 beside it outputs a space."""
        assert run_and_capture([">$%:", " 20"]) == " "


class TestDigArithmetic:
    r"""Test the arithmetic operators against an adjacent digit."""

    def test_addition(self) -> None:
        assert run_and_capture([">$ 3+:", " 4  2 "]) == "5"

    def test_subtraction(self) -> None:
        assert run_and_capture([">$ 7-:", " 4  3 "]) == "4"

    def test_multiplication(self) -> None:
        assert run_and_capture([">$ 4*:", " 4  2 "]) == "8"

    def test_division(self) -> None:
        assert run_and_capture([">$ 9/:", " 4  3 "]) == "3"

    def test_division_keeps_the_quotient_not_the_divisor(self) -> None:
        r"""9 over 3 is 3 either way, so divide where the two differ."""
        assert run_and_capture([">$ 8/:", " 4  2 "]) == "4"

    def test_large_result_printed_as_character(self) -> None:
        r"""Test that values >= 10 are printed as characters."""
        assert run_and_capture([">$ 6+:", " 4  5 "]) == "\x0b"


class TestDigInput:
    r"""Test the input commands."""

    def test_integer_input(self) -> None:
        r"""Test that ~ reads a single integer."""
        assert run_and_capture([">$~:", " 2 "], inputs=["7"]) == "7"

    def test_character_input(self) -> None:
        r"""Test that = reads a single character."""
        assert run_and_capture([">$=:", " 2 "], inputs=["A"]) == "A"


class TestDigExamplePrograms:
    r"""Test example programs from esolangs.org."""

    def test_hello_world(self) -> None:
        r"""Test the Hello World program from esolangs.org."""
        hello_world = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]
        assert run_and_capture(hello_world) == "Hello World!"

    def test_nand_gate(self) -> None:
        r"""Test the NAND gate program from esolangs.org."""
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
    r"""Test edge cases and error conditions."""

    def test_the_empty_program_message_reads_exactly(self) -> None:
        r"""``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "Dig program cannot be empty"):
            run([], io=IO())

    def test_blank_only_program_is_empty(self) -> None:
        r"""Programs of only blank lines are rejected, not crashing the mole."""
        with pytest.raises(ValueError, match="empty"):
            run(["\n"], io=IO())
        with pytest.raises(ValueError, match="empty"):
            run(["   ", "\t"], io=IO())

    def test_no_adjacent_digit_halts(self) -> None:
        r"""A work command with no adjacent digit is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$+:", "    "], io=IO())

    def test_divide_by_zero_halts(self) -> None:
        r"""Dividing by an adjacent zero is an invalid operation."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run([">$/", " 10"], io=IO())

    def test_empty_input_line_reads_zero(self) -> None:
        r"""An empty input line stores 0 in the mole."""
        assert run_and_capture([">$=:", " 2 "], inputs=[""]) == "0"

    def test_a_steer_digit_outside_zero_and_one_goes_straight(self) -> None:
        r"""``#`` turns on 1 and 0; every other digit holds the heading."""
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.interpreters.io import ScriptedIO

        def heading_after(digit: str) -> int:
            # "#" steers overground, so no.
            # heading right and reads the.
            machine = _Machine([" #  ", f" {digit}  "], ScriptedIO(""))
            machine.step()  # the blank the mole starts on.
            machine.step()  # "#".
            return machine.move

        straight = heading_after("2")
        assert heading_after("1") == (straight + 1) % 4, "1 turns right"
        assert heading_after("0") == (straight - 1) % 4, "0 turns left"
        for digit in "23456789":
            assert heading_after(digit) == straight, digit

    def test_a_whitespace_digit_outside_zero_and_one_is_inert(self) -> None:
        r"""``%`` loads a newline for 1 and a space for 0, nothing otherwise."""
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.interpreters.io import ScriptedIO

        def mole_after(digit: str) -> int:
            # "%" is a work command, so "$".
            # budget first; it reads the 1.
            machine = _Machine(["$%  ", f"1{digit}  "], ScriptedIO(""))
            machine.step()  # "$" loads the work budget.
            machine.step()  # "%" selects.
            return machine.mole

        assert mole_after("1") == 10  # newline.
        assert mole_after("0") == 32  # space.
        for digit in "23456789":
            assert mole_after(digit) == 0, digit


class TestStepMachine:
    def test_step_tracks_position_direction_and_mole(self) -> None:
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$5:", " 2 "], IO())
        assert (machine.row, machine.col, machine.move, machine.mole) == (0, 0, 1, 0)
        machine.step()  # > keeps facing right.
        assert (machine.row, machine.col, machine.move) == (0, 1, 1)
        machine.step()  # $ digs: reads the adjacent.
        assert machine.num == 5
        machine.step()  # 5 sets the mole and consumes.
        assert (machine.mole, machine.num) == (5, 4)

    def test_the_read_lands_in_the_mole(self) -> None:
        r"""``=`` puts the line it read where the language says it goes."""
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$=:", " 2 "], ScriptedIO("A"))
        for _ in range(3):  # move over, dig, read.
            machine.step()
        assert machine.mole == ord("A")


def _machine(code: object) -> object:
    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import IO

    return _Machine(code, IO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.grid_based.dig import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(CycleContract, InputCursorContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    halting_program: ClassVar[list[str]] = [">@"]
    looping_program: ClassVar[list[str]] = [">'", "^<"]
    reader = staticmethod(_reader)
    reading_program: ClassVar[list[str]] = [">$=:", " 2 "]
    reading_stdin = "A"
    steps_before_read = 2  # move over, dig, and only then.
