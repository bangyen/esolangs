"""Unit tests for the ASCII art interpreter."""

import importlib
import io
from contextlib import redirect_stdout

ascii_art = importlib.import_module("esolangs.interpreters.tape_based.ascii-art")

# A '+' block has 4 newlines and ends in '|'; a '.' block has 1 newline and ends in '#'.
PLUS = "|\n|\n|\n|\n|"
DOT = "##\n##"


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
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
