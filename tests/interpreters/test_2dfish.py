"""Unit tests for the 2dFish interpreter."""

import importlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO

run = importlib.import_module("esolangs.interpreters.other.2dfish").run


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
        # the reference pushes the last row twice when the file ends in \n
        assert run_program("/i@\n") == ""
