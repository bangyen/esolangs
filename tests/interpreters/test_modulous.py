"""Unit tests for the Modulous interpreter."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.stack_based.modulous import run
from esolangs.interpreters.io import IO


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestModulous:
    def test_push_print_int(self) -> None:
        assert run_and_capture("[PSH INT 5][PRT INT][END]") == "5"

    def test_push_print_string(self) -> None:
        assert run_and_capture('[PSH STR "A"][PRT][END]') == "A"

    def test_push_string_then_pop(self) -> None:
        assert run_and_capture('[PSH STR "AB"][PRT][PRT][END]') == "AB"

    def test_add(self) -> None:
        assert run_and_capture("[PSH INT 5][PSH INT 2][ADD 3][PRT INT][END]") == "5"

    def test_subtract(self) -> None:
        assert run_and_capture("[PSH INT 8][SUB 3][PRT INT][END]") == "5"

    def test_duplicate(self) -> None:
        assert run_and_capture("[PSH INT 4][DUP][PRT INT][PRT INT][END]") == "44"

    def test_input(self) -> None:
        assert run_and_capture("[INP INT][PRT INT][END]", inputs=["42"]) == "42"

    def test_input_string(self) -> None:
        assert run_and_capture("[INP][PRT][PRT][END]", inputs=["AB"]) == "AB"

    def test_swap(self) -> None:
        assert (
            run_and_capture("[PSH INT 1][PSH INT 2][SWP][PRT INT][PRT INT][END]")
            == "12"
        )

    def test_jump_forward(self) -> None:
        """JMP F skips a module."""
        assert run_and_capture("[PSH INT 5][JMP F 1][PRT INT][END]") == "5"

    def test_conditional_jump(self) -> None:
        """JMP ... IF jumps only when the top matches."""
        assert run_and_capture("[PSH INT 5][JMP F 1 IF 5][PRT INT][END]") == "5"

    def test_conditional_jump_nif(self) -> None:
        """JMP ... NIF jumps only when the top does not match."""
        assert run_and_capture("[PSH INT 5][JMP F 1 NIF 5][PRT INT][END]") == "5"

    def test_backward_jump(self) -> None:
        """JMP B jumps backwards, eventually landing on END."""
        assert run_and_capture("[JMP B 1][END]") == ""

    def test_pop(self) -> None:
        """POP removes the top of the stack."""
        assert run_and_capture("[PSH INT 5][POP][PSH INT 7][PRT INT][END]") == "7"

    def test_reset(self) -> None:
        """RST restarts the module pointer, so output never happens."""
        assert run_and_capture("[RST][PRT INT][END]") == ""

    def test_push_variable(self) -> None:
        """PSH VAR stores the top of the stack in a variable."""
        assert run_and_capture("[PSH INT 7][PSH VAR1][PRT VAR1 INT][END]") == "7"

    def test_random(self) -> None:
        """RND pushes a random value below the given bound."""
        assert run_and_capture("[RND 1][PRT INT][END]") == "0"

    def test_variable_add(self) -> None:
        assert run_and_capture("[VAR1+3][PRT VAR1 INT][END]") == "3"

    def test_variable_subtract(self) -> None:
        assert run_and_capture("[VAR1-3][PRT VAR1 INT][END]") == "-3"
