"""Unit tests for the ASCII art interpreter."""

import importlib
import io
from contextlib import redirect_stdout
from unittest.mock import patch

ascii_art = importlib.import_module("esolangs.interpreters.tape_based.ascii-art")

# ASCII-art blocks mapping to brainfuck commands:
PLUS = "|\n|\n|\n|\n|"  # +
MINUS = "-"  # -
DOT = "##\n##"  # .
LEFT = "\\\n\\\n\\\n\\"  # <
RIGHT = "/\n/\n/\n/"  # >
LOOP_OPEN = "_\n_\n_\n_\n_\n_"  # [
LOOP_CLOSE = "|\n|\n|\n|\n|\n|"  # ]
INPUT = "|\n|\n|"  # ,


def program(*blocks: str) -> str:
    return "\n\n".join(blocks)


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        ascii_art.run(code)
    return buffer.getvalue()


class TestASCIIArt:
    def test_output_A(self) -> None:
        assert run_and_capture((PLUS + "\n\n") * 65 + DOT) == "A"

    def test_output_B(self) -> None:
        assert run_and_capture((PLUS + "\n\n") * 66 + DOT) == "B"

    def test_unknown_block_ignored(self) -> None:
        """Blocks that do not map to a brainfuck command are ignored."""
        assert run_and_capture("abc") == ""

    def test_minus(self) -> None:
        assert run_and_capture(program(MINUS)) == ""

    def test_movement(self) -> None:
        assert run_and_capture(program(PLUS, PLUS, RIGHT, MINUS, LEFT, DOT)) == "\x02"

    def test_input_echo(self) -> None:
        assert run_and_capture(program(PLUS, INPUT, DOT), inputs=["A"]) == "A"

    def test_loop_zeroing(self) -> None:
        """+[-] enters a loop, zeroes the cell, and exits."""
        assert run_and_capture(program(PLUS, LOOP_OPEN, MINUS, LOOP_CLOSE)) == ""

    def test_loop_skipped_when_zero(self) -> None:
        """:[.] skips the body when the cell is zero."""
        assert run_and_capture(program(LOOP_OPEN, DOT, LOOP_CLOSE)) == ""

    def test_loop_iterates_while_nonzero(self) -> None:
        """++[>+<-] iterates twice before the cell reaches zero."""
        assert (
            run_and_capture(
                program(PLUS, PLUS, LOOP_OPEN, RIGHT, PLUS, LEFT, MINUS, LOOP_CLOSE)
            )
            == ""
        )

    def test_unmatched_open_bracket(self) -> None:
        """An unmatched [ with a zero cell halts cleanly."""
        assert run_and_capture(program(LOOP_OPEN)) == ""

    def test_nested_open_brackets(self) -> None:
        """Nested [ brackets are counted during the skip."""
        assert run_and_capture(program(LOOP_OPEN, LOOP_OPEN)) == ""
