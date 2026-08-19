"""Unit tests for the 2dFish interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.grid_based.two_d_fish").run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test2dFish:
    def test_single_row_right(self) -> None:
        assert run_program("/i@") == ""
        assert run_program("/ii@") == ""
        assert run_program("/iiio@") == "3"

    def test_accumulator(self) -> None:
        assert run_program("/iia@") == "\x02"
        assert run_program("/iaa@") == "\x01\x01"

    def test_print_decimal(self) -> None:
        assert run_program("/io@") == "1"

    def test_string_capture(self) -> None:
        assert run_program("/i(abc)*@") == "abc"
        assert run_program("/(abc)*@") == "abc"
        assert run_program("/i(abc)@") == ""  # captured, never printed

    def test_string_accumulator_output(self) -> None:
        # in string mode, a removes and prints the last captured character
        assert run_program("/i(ab)a@") == "b"

    def test_read_line(self) -> None:
        assert run_program("/$*@", "hi\n") == "hi"

    def test_read_number(self) -> None:
        assert run_program("/%o@", "42\n") == "42"

    def test_read_number_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match="invalid literal"):
            run_program("/%o@", "42abc\n")

    def test_multiple_rows(self) -> None:
        assert run_program("v\ni\n@\n") == ""
        assert run_program("v\nii\no\n@\n") == "1"

    def test_missing_initial_direction(self) -> None:
        with pytest.raises(ValueError, match="initial direction"):
            run_program("i@")

    def test_off_grid_halts(self) -> None:
        # a right-moving pointer runs off the end of the ragged row
        with pytest.raises(HaltError):
            run_program("/ii")

    def test_empty_program(self) -> None:
        with pytest.raises(ValueError, match="initial direction"):
            run_program("")

    def test_trailing_newline_phantom_row(self) -> None:
        # the cross-check pushes the last row twice when the file ends in \n
        assert run_program("/i@\n") == ""

    def test_square_and_string_mode_reset(self) -> None:
        # s squares the accumulator; i/d/s all leave string mode, so the
        # following a prints the accumulator byte instead of the string
        assert run_program("/iiso@") == "4"
        assert run_program("/i(ab)sa@") == "\x01"
        assert run_program("/i(ab)ia@") == "\x02"

    def test_left_turn_off_the_grid_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("v\n\\\n@")

    def test_up_off_the_top_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("^\ni\n@")

    def test_a_on_empty_string_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("/()a@")

    def test_unterminated_string_capture_rejected(self) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            run_program("/(abc@")

    def test_non_right_capture_resumes_from_the_paren(self) -> None:
        # a downward pointer resumes moving from the '(' after capturing
        assert run_program("v\n(a)\n@") == ""


class TestStepMachine:
    def test_step_tracks_position_and_accumulator(self) -> None:
        from esolangs.interpreters.grid_based.two_d_fish import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine("/iio@", ScriptedIO())
        assert (machine.x, machine.y, machine.d) == (1, 0, "/")
        machine.step()  # i
        assert machine.acc == 1
        assert (machine.x, machine.y) == (2, 0)
        machine.step()  # i
        assert machine.acc == 2
        machine.step()  # o
        machine.step()  # @ halts
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.x == 4  # the pointer did not move

    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.grid_based.two_d_fish import _Machine
        from esolangs.interpreters.io import ScriptedIO

        machine = _Machine("/%o@", ScriptedIO("42\n"))
        before = machine.snapshot()
        assert hash(before) is not None
        machine.step()  # % reads the input line
        assert machine.snapshot() != before
        assert machine.io.position() == 1  # the cursor advanced past "42"

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.grid_based.two_d_fish import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.vm import run_until_halt_or_cycle

        assert run_until_halt_or_cycle(_Machine("/io@", ScriptedIO())) is True
