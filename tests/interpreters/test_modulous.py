"""Unit tests for the Modulous interpreter."""

import io
from contextlib import redirect_stdout
from typing import List, Optional
from unittest.mock import patch

from esolangs.interpreters.stack_based.modulous import run


def run_and_capture(code: str, inputs: Optional[List[str]] = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []):
        with redirect_stdout(buffer):
            run(code)
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
