"""Unit tests for Dig interpreter."""

from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.dig import run
from esolangs.interpreters.io import IO, ScriptedIO
from tests.interpreters.contract import CycleContract, InputCursorContract
from tests.interpreters.runner import run_lines
from tests.raises import raises_message

run_and_capture = run_lines(run)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # overground movement
        pytest.param([">H:@", "  2 "], "", id="work_commands_ignored_overground"),
        # only ^>'< set the heading; the mole keeps going right
        pytest.param(["X$5:", " 2  "], "5", id="a_letter_overground_does_not_steer"),
        # @ ends the run, rather than the mole walking off the end
        pytest.param(["@$5:", " 2  "], "", id="the_halt_stops_code_that_follows_it"),
        # walking off the bottom ends the run as cleanly as off the side
        pytest.param(["'"], "", id="the_mole_stops_at_the_bottom_row"),
        # the heading is taken modulo four, the number of headings
        pytest.param(
            [" 1'", " #<"],
            "",
            id="a_right_turn_from_the_last_heading_wraps_to_the_first",
        ),
        # work commands, which only function underground
        pytest.param([">$:", " 2 "], "0", id="print_initial_zero"),
        pytest.param([">$99:", " 3 "], "9", id="last_digit_wins"),
        pytest.param([">$H:", " 2 "], "H", id="print_character"),
        # only = and ~ read; X is a letter like any other
        pytest.param(
            [">$X:", " 2 "], "X", id="a_letter_underground_is_not_an_input_command"
        ),
        # : resets the mole to zero, which a second : reveals
        pytest.param([">$3::", " 3   "], "30", id="printing_clears_the_mole"),
        # arithmetic against an adjacent digit
        pytest.param([">$ 3+:", " 4  2 "], "5", id="addition"),
        pytest.param([">$ 7-:", " 4  3 "], "4", id="subtraction"),
        pytest.param([">$ 4*:", " 4  2 "], "8", id="multiplication"),
        pytest.param([">$ 9/:", " 4  3 "], "3", id="division"),
        # 9 over 3 is 3 either way, so divide where the two differ
        pytest.param(
            [">$ 8/:", " 4  2 "], "4", id="division_keeps_the_quotient_not_the_divisor"
        ),
        pytest.param(
            [">$ 6+:", " 4  5 "], "\x0b", id="large_result_printed_as_character"
        ),
        # ; stores the mole's whole value in one cell (wiki, Lua implementation):
        # 12 lands in the ; cell; the : after it still prints chr(12)
        pytest.param([">$6+;:"], "\x0c", id="a_two_digit_store_does_not_shift_the_row"),
        # walking a ; cell again, underground, loads what it stored (A)
        pytest.param(
            ["'   : ", ">2$A;'", "    $ ", "    ^<"],
            "A",
            id="a_stored_value_is_read_back_underground",
        ),
    ],
)
def test_prints(code: list[str], expected: str) -> None:
    assert run_and_capture(code) == expected


class TestDigInput:
    """Test the input commands."""

    def test_integer_input_keeps_all_digits(self) -> None:
        """``~`` reads an integer, rather than only its first digit."""
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$~:", " 2 "], ScriptedIO("12"))
        for _ in range(3):  # move over, dig, read
            machine.step()
        assert machine.mole == 12

    def test_character_input(self) -> None:
        assert run_and_capture([">$=:", " 2 "], inputs=["A"]) == "A"

    def test_a_huge_integer_reads_and_prints_whole(self) -> None:
        """``~`` and ``:`` handle 5000 digits, past Python's str/int limit."""
        number = "-" + "9" * 5000
        assert run_and_capture([">$~:", " 2 "], inputs=[number]) == number

    def test_a_cursorless_read_loop_is_not_a_cycle(self) -> None:
        """Reads count in the snapshot: the loop runs to EOF, not a false cycle."""
        from esolangs.interpreters.grid_based.dig import _Machine
        from esolangs.vm import run_until_halt_or_cycle
        from tests.interpreters.cursorless_io import CursorlessIO

        machine = _Machine([">$=:'", "^1  <"], CursorlessIO("aaaaaaaa"))
        with pytest.raises(EOFError):
            run_until_halt_or_cycle(machine)


class TestDigStore:
    """``;`` stores the mole's whole value in one cell (wiki, Lua implementation)."""

    def test_a_stored_negative_digging_distance_halts(self) -> None:
        """``;`` stores -5 beside a ``$``; digging -5 tiles is refused."""
        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError, match="negative digging distance"):
            run_and_capture([">$ -;$", " 3 5  "])


class TestDigExamplePrograms:
    """Test example programs from esolangs.org."""

    def test_hello_world(self) -> None:
        hello_world = [">$H:e:l:l:$o:%:W:o:$r:l:d:!:@", " 8        8  0     8"]
        assert run_and_capture(hello_world) == "Hello World!"

    def test_nand_gate(self) -> None:
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

    def test_the_empty_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "Dig program cannot be empty"):
            run([], io=IO())

    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashing the mole."""
        with pytest.raises(ValueError, match="empty"):
            run(["\n"], io=IO())
        with pytest.raises(ValueError, match="empty"):
            run(["   ", "\t"], io=IO())

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

    def test_a_steer_digit_outside_zero_and_one_goes_straight(self) -> None:
        """``#`` turns on 1 and 0; every other digit holds the heading."""
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
        """``%`` loads a newline for 1 and a space for 0, nothing otherwise."""
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

    def test_the_read_lands_in_the_mole(self) -> None:
        """``=`` puts the line it read where the language says it goes."""
        from esolangs.interpreters.grid_based.dig import _Machine

        machine = _Machine([">$=:", " 2 "], ScriptedIO("A"))
        for _ in range(3):  # move over, dig, read
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
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    halting_program: ClassVar[list[str]] = [">@"]
    looping_program: ClassVar[list[str]] = [">'", "^<"]
    reader = staticmethod(_reader)
    reading_program: ClassVar[list[str]] = [">$=:", " 2 "]
    reading_stdin = "A"
    steps_before_read = 2  # move over, dig, and only then read
