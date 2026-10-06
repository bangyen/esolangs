"""bit_tilde generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bit_tilde,
)


class TestBitTilde:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # single one (AND4)
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bit_tilde(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bit_tilde(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_every_small_table(self, n: int) -> None:
        """Execute every table and row through three inputs."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.bit_tilde(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert run_bit_tilde(program, [str(b) for b in bits]) == table[combo]

    def test_full_table_growth_is_linear(self) -> None:
        """Parity folds nothing, but one cell an entry stays linear."""
        sizes = []
        for n in (7, 8):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            sizes.append(len(boolean.bit_tilde(table)))
        assert sizes[1] < 2 * sizes[0] + 256

    def test_single_read_and_output(self) -> None:
        """One read per input and a single final output."""
        program = boolean.bit_tilde("0110")
        # The prologue paints the table and walks to the top of it, so the
        # opening is moves and flips -- no loop, read or print among them.
        assert set(program[: program.index(")")]) <= {">", "~"}
        assert program.count(")") == 2
        assert program.count("(") == 1
        assert program.endswith("(")
