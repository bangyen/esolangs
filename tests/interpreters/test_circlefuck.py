"""Unit tests for the Circlefuck interpreter."""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from esolangs.interpreters.tape_based.circlefuck import run


def run_and_capture(code: str, inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            run(code)
    return buffer.getvalue()


class TestCirclefuck:
    def test_hello_world(self) -> None:
        """Canonical Hello, World! program from esolangs.org."""
        program = "<[.<]@\\0\\n!dlroW\\ ,olleH"
        assert run_and_capture(program) == "Hello, World!\n"

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
