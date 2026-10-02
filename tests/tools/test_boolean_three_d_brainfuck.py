"""three_d_brainfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_three_d_brainfuck,
)


class TestThreeDBf:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("1111111111111111", 4),  # constant one
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.three_d_brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_three_d_brainfuck(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_array_moves_use_the_3d_axes(self) -> None:
        """3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program

    def test_a_constant_zero_side_needs_no_flag(self) -> None:
        """Pin the three-input total: 35,488 characters before, 28,734 after.

        A node whose zero-side is constant adds it up front and keeps only
        the bit's loop, so AND is two nested loops; the run starts on the
        multiplier rather than walking to it.
        """
        assert boolean.three_d_brainfuck("0001").endswith("e[-n[-e+w]s]ne.")
        tables = [f"{value:08b}" for value in range(256)]
        assert sum(len(boolean.three_d_brainfuck(t)) for t in tables) == 28734
