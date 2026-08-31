"""Unit tests for the Circlefuck interpreter."""

from esolangs.interpreters.tape_based.circlefuck import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.interpreters.runner import run_program


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

    def test_loop_skip_finds_matching_bracket(self) -> None:
        assert run_and_capture("\\0[.]@") == ""

    def test_decrement(self) -> None:
        assert run_and_capture("-@") == ""

    def test_empty_program_rejected(self) -> None:
        """A program with no instructions is malformed."""
        import pytest

        with pytest.raises(ValueError, match="empty"):
            run_and_capture("")

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
