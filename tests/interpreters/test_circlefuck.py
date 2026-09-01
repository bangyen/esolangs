"""Unit tests for the Circlefuck interpreter."""

from esolangs.interpreters.tape_based.circlefuck import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program
from tests.raises import raises_message


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    return run_program(run, code, "".join(f"{line}\n" for line in inputs or []))


class TestCirclefuck:
    def test_hello_world(self) -> None:
        """Canonical Hello, World! program from esolangs.org."""
        program = "<[.<]@\\0\\n!dlroW\\ ,olleH"
        assert run_and_capture(program) == "Hello, World!\n"

    def test_truth_machine_zero(self) -> None:
        """A 0 input prints 0 and halts.

        The 1 branch prints 1 forever by definition, so only the terminating
        branch is exercised.
        """
        program = "," + "-" * 48 + "[[-]" + "+" * 49 + ".]" + "+" * 48 + ".@"
        assert run_and_capture(program, inputs=["0"]) == "0"

    def test_halt(self) -> None:
        assert run_and_capture("++@") == ""

    def test_output_cell_value(self) -> None:
        """. outputs the cell under the data pointer (self-modified)."""
        assert run_and_capture("+.@") == ","

    def test_skip_instruction(self) -> None:
        """# skips the next instruction."""
        assert run_and_capture("+#.@") == ""

    def test_skip_passes_over_exactly_one_instruction(self) -> None:
        """# steps over the next cell and no further.

        With two prints after it the second still runs, printing the ``#``
        itself from cell 0 -- a wider skip would swallow both.
        """
        assert run_and_capture("#..@") == "#"

    def test_increment_wraps_at_two_hundred_fifty_six(self) -> None:
        """255 + 1 comes back to zero, which no smaller cell can show."""
        assert run_and_capture("\\xFF+.@") == "\x00"

    def test_decrement_wraps_at_zero(self) -> None:
        """0 - 1 comes back as 255, the other end of the same wrap."""
        assert run_and_capture("\\0-.@") == "\xff"

    def test_a_letter_is_not_a_bracket(self) -> None:
        """Only ``[`` and ``]`` jump; every other letter is inert.

        A letter admitted into the jump would search a tape with no
        brackets at all and come back round to its start, rejecting the
        program as unmatched.
        """
        assert run_and_capture("+X@") == ""

    def test_input(self) -> None:
        """, stores a byte of input in the current cell."""
        assert run_and_capture(",.@", inputs=["A"]) == "A"

    def test_insert_cell(self) -> None:
        """{ inserts a new zero cell before the current one."""
        assert run_and_capture("{+.@") == "\x01"

    def test_delete_cell(self) -> None:
        """} deletes the current cell."""
        assert run_and_capture("+}.@") == ""


class TestStepMachine:
    def test_step_tracks_cells_and_pointers(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("+.@", ScriptedIO())
        assert (machine.ind, machine.ptr, machine.cells) == (0, 0, [43, 46, 64])
        machine.step()  # + sets the cell
        assert machine.cells == [44, 46, 64]
        machine.step()  # . prints it
        assert machine.io.getvalue() == ","
        machine.step()  # @ halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.ind == 2

    def test_move_right(self) -> None:
        """> moves the data pointer to the next cell (wrap-around)."""
        assert run_and_capture("{>[.>]@") == "{>[.>]@"

    def test_decimal_escape(self) -> None:
        """:math:`\\NNN` escape sequences decode to a single byte."""
        assert run_and_capture("\\065.@") == "A"

    def test_hex_escape(self) -> None:
        assert run_and_capture("\\x41.@") == "A"

    def test_bare_hex_digit_escape_is_uppercase(self) -> None:
        """A lone ``\\F`` is a hex digit; the lowercase run is not one."""
        assert run_and_capture("\\F.@") == "\x0f"

    def test_a_leading_o_is_dropped_from_an_escape(self) -> None:
        """``\\o101`` names the same octal byte as ``\\101``."""
        assert run_and_capture("\\o101.@") == "A"

    def test_decimal_escape_keeps_its_leading_digit(self) -> None:
        """``\\065`` reads the same whichever digit the decode starts at.

        165 does not: dropping its leading digit would leave 65 and print
        an ``A`` instead of the byte the program asked for.
        """
        assert run_and_capture("\\165.@") == "\xa5"

    def test_the_unit_separator_is_not_a_command(self) -> None:
        """Cells below the space are stripped, so only the ``.`` remains."""
        assert run_and_capture("\x1f.@") == "."

    def test_delete_is_not_a_command(self) -> None:
        """127 is stripped too, so the printable range is open at both ends."""
        assert run_and_capture("\x7f.@") == "."

    def test_a_skipped_loop_scans_forward_for_its_partner(self) -> None:
        """``[`` on a zero cell jumps to its own ``]``, not a bracket behind it.

        Two loops make the direction visible: landing on the second loop's
        closing bracket would carry the pointer past the print between them.
        """
        assert run_and_capture("\\0[.].[.]@") == "\x00"

    def test_newline_escape(self) -> None:
        assert run_and_capture("\\n.@") == "\n"

    def test_loop_skipped_when_cell_zero(self) -> None:
        """[ skips its body when the current cell is zero."""
        assert run_and_capture("\\0[.].@") == "\x00"

    def test_unmatched_bracket_rejected(self) -> None:
        """An unmatched [ is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="unmatched"):
            run_and_capture("\\0[.@")

    def test_the_unmatched_bracket_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""

        with raises_message(ValueError, "unmatched bracket"):
            run_and_capture("\\0[.@")

    def test_loop_skip_finds_matching_bracket(self) -> None:
        assert run_and_capture("\\0[.]@") == ""

    def test_decrement(self) -> None:
        assert run_and_capture("-@") == ""

    def test_empty_program_rejected(self) -> None:
        """A program with no instructions is malformed."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run_and_capture("")

    def test_the_empty_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""

        with raises_message(ValueError, "Circlefuck program cannot be empty"):
            run_and_capture("")

    def test_insert_leaves_the_cursor_on_the_cell_after_the_new_one(self) -> None:
        """``{`` steps the cursor past the cell it just pushed forward.

        The existing insert runs at cell 0, where advancing the cursor and
        setting it to one land in the same place; putting a command in
        front of the ``{`` separates them.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.circlefuck import _Machine

        machine = _Machine("+{+.@", ScriptedIO())
        machine.step()  # + raises cell 0
        machine.step()  # { inserts a zero before it and steps past both
        assert machine.ind == 3
        assert machine.cells == [0, 44, 123, 43, 46, 64]

    def test_delete_last_cell_halts(self) -> None:
        """Deleting the last cell is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("}")
        # a pop that would leave the pointer out of bounds wraps instead of
        # leaking an IndexError
        with pytest.raises(HaltError):
            run_and_capture("<}}@")


def _machine(code: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.circlefuck import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes. ``><`` orbits the pointer forever; ``+.@`` halts."""

    machine = staticmethod(_machine)
    stepping_program = "><"
    halting_program = "+.@"
    looping_program = "><"
