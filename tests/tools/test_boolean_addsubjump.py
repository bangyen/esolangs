"""addsubjump generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_addsubjump,
    run_addsubjump_from,
)
from tests.witness_tables import witnesses


class TestAddSubJump:
    def test_branch_normalizes_ascii_bits(self) -> None:
        """Each ASCII input contributes its zero-or-one value to the index."""
        program = boolean.addsubjump("0110")
        assert "48" in program
        assert run_addsubjump(program, ["0", "1"]) == "1"
        assert run_addsubjump(program, ["1", "0"]) == "1"

    @pytest.mark.medium
    def test_all_three_input_tables(self) -> None:
        """The packed decoder executes the three-input witnesses."""
        for table in witnesses(3):
            program = boolean.addsubjump(table)
            for row in range(8):
                bits = [str((row >> shift) & 1) for shift in (2, 1, 0)]
                assert run_addsubjump(program, bits) == table[row]

    def test_three_input_total(self) -> None:
        """Shared residuals reduce the n=3 total from 99,032 to 94,800."""
        total = sum(len(boolean.addsubjump(f"{value:08b}")) for value in range(256))
        assert total == 94800

    def test_every_path_reads_each_input_once(self) -> None:
        """A run consumes exactly ``n`` inputs, whatever the table."""
        for table, n in (("01101001", 3), ("11111111", 3), ("10101010", 3)):
            program = boolean.addsubjump(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                feed = iter([str(b) for b in bits])
                got = run_addsubjump_from(program, feed)
                assert got == table[combo], f"{table} inputs {bits}"
                assert not list(feed), f"{table} inputs {bits} left input unread"
