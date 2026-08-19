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
