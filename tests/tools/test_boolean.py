"""Unit tests for the boolean-function program generators."""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.tools import boolean


def run_sophie(program: str, inputs: list) -> str:
    from esolangs.interpreters.register_based.sophie import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs):
        with redirect_stdout(buffer):
            run(program)
    return buffer.getvalue()


class TestSophie:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111110", 4),  # NAND4
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.sophie(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_sophie(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_structure(self) -> None:
        """A one-input function is a single conditional pair."""
        assert boolean.sophie("10", 1) == ";@$48{#$49,&}{#$48,&}"
