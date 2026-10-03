"""addsubjump generator tests."""

from itertools import pairwise

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_addsubjump,
    run_addsubjump_from,
)


class TestAddSubJump:
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
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.addsubjump(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_addsubjump(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_branch_normalizes_ascii_bits(self) -> None:
        """Each ASCII input contributes its zero-or-one value to the index."""
        program = boolean.addsubjump("0110")
        assert "48" in program
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """The packed decoder executes every three-input function."""
        for value in range(256):
            table = format(value, "08b")
            program = boolean.addsubjump(table)
            for row in range(8):
                bits = [str((row >> shift) & 1) for shift in (2, 1, 0)]
                assert run_addsubjump(program, bits) == table[row]

    def test_three_input_total(self) -> None:
        """Shared residuals reduce the n=3 total from 99,032 to 94,800."""
        total = sum(len(boolean.addsubjump(f"{value:08b}")) for value in range(256))
        assert total == 94800

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whatever the table.

        With the reads hoisted this is structural rather than something a
        folded leaf has to drain, but it is the contract callers depend on:
        several programs fed from one stream desync if a path leaves bits
        unconsumed.  An exhaustible iterator proves both directions -- an
        over-read raises, a leftover proves an under-read.
        """
        for table, n in (("01101001", 3), ("11111111", 3), ("10101010", 3)):
            program = boolean.addsubjump(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_addsubjump_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"

    def test_packed_growth_is_linear(self) -> None:
        """Wide parity tables grow by at most the table-size ratio."""
        sizes = [
            len(
                boolean.addsubjump(
                    "".join(str(row.bit_count() & 1) for row in range(2**n))
                )
            )
            for n in range(11, 15)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))
