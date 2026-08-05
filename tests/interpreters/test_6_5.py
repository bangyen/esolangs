"""Unit tests for the 6-5 interpreter."""

import importlib
import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

sixfive = importlib.import_module("esolangs.interpreters.tape_based.6-5")


def run_and_capture(code: str, inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            sixfive.run(code)
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
