"""Unit tests for The Temporary Stack interpreter."""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from esolangs.interpreters.stack_based.temporary import run


def run_and_capture(code: str, inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            run(code)
    return buffer.getvalue()


class TestTemporaryStack:
    def test_hello_world(self) -> None:
        """Hello World program from esolangs.org."""
        assert run_and_capture('o *Ifmmp-!xpsme" v11 v2297') == "Hello, world!\n"

    def test_squish(self) -> None:
        """The bottom value is squished and output when the rest outweigh it."""
        assert run_and_capture("v1 v3") == "0"

    def test_ascii_output_mode(self) -> None:
        """o switches output to ASCII characters."""
        assert run_and_capture("o v66 v133") == "A"

    def test_integer_output_mode(self) -> None:
        """O switches output to integer values (the default)."""
        assert run_and_capture("O v1 v3") == "0"

    def test_input_command(self) -> None:
        """@ pushes the ASCII values of each input character."""
        assert run_and_capture("o @ v1 v133", inputs=["A"]) == "@\x00"

    def test_duplicate(self) -> None:
        """+ duplicates the top of the stack."""
        assert run_and_capture("v66 +") == ""

    def test_duplicate_affects_squish(self) -> None:
        assert run_and_capture("O v1 v3 + v1 v3") == "02"

    def test_repeat_instruction(self) -> None:
        """: repeats the next instruction until the stack changes."""
        assert run_and_capture("v66 : v1") == ""

    def test_stack_reset_every_fifteen(self) -> None:
        """The stack is cleared every 15 commands."""
        program = " ".join(["v1"] * 15)
        assert run_and_capture(program) == "0" * 12

    def test_repeat_until_empty(self) -> None:
        """:math:`\\` repeats until the stack is empty; after a reset it runs once."""
        program = " ".join(["v1"] * 15 + ["\\", "v1"])
        assert run_and_capture(program) == "0" * 12

    def test_random_command(self) -> None:
        """€ performs a random (here, forced) action."""
        with patch(
            "esolangs.interpreters.stack_based.temporary.secrets.choice",
            return_value="o",
        ):
            assert run_and_capture("€ v66") == ""
