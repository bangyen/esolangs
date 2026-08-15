"""Unit tests for The The Temporary Stack Stack interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.the_temporary_stack import run


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestTemporaryStack:
    def test_hello_world(self) -> None:
        """Hello World program from esolangs.org."""
        assert run_and_capture('o *Ifmmp-!xpsme" v11 v2297') == "Hello, world!\n"

    def test_squish(self) -> None:
        """The bottom value is squished and output when the rest outweigh it."""
        assert run_and_capture("v1 v3") == "0"

    def test_ascii_output_mode(self) -> None:
        """O switches output to ASCII characters."""
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

    def test_comments_inside_commands(self) -> None:
        """The command is the first command char; comments may precede it."""
        # cOOde is O: switch to integer mode, so 4x v65 prints "64" not "@"
        assert run_and_capture("o cOOde v65 v65 v65 v65") == "64"
        # hv1no2th3ing is v123: a 123 bottom squishes 'z' under two 130s
        assert run_and_capture("o hv1no2th3ing v130 v130") == "z"

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

    def test_backslash_repeats_then_reset_empties(self) -> None:
        """:math:`\\` with a non-empty stack drains until the command reset."""
        assert run_and_capture("v1 \\ v1") == "0" * 12

    def test_random_command(self) -> None:
        """€ performs a random (here, forced) action."""
        with patch(
            "esolangs.interpreters.stack_based.the_temporary_stack.secrets.choice",
            return_value="o",
        ):
            assert run_and_capture("€ v66") == ""

    def test_duplicate_on_empty_stack_halts(self) -> None:
        """Duplicating an empty stack is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("+")

    def test_squish_negative_char_halts(self) -> None:
        """Squishing a negative value in byte mode is an invalid operation."""
        import pytest

        from esolangs.exceptions import HaltError

        with pytest.raises(HaltError):
            run_and_capture("o v0 v1")

    def test_repeat_without_following_instruction_rejected(self) -> None:
        """A : with no instruction after it is a malformed program."""
        import pytest

        with pytest.raises(ValueError, match="following instruction"):
            run_and_capture("v1 :")

    def test_multiple_commands_in_one_word_rejected(self) -> None:
        """A word with more than one distinct command is invalid (per talk)."""
        import pytest

        with pytest.raises(ValueError, match="multiple commands"):
            run_and_capture("o@\\@")
        with pytest.raises(ValueError, match="multiple commands"):
            run_and_capture("v1 @o")
