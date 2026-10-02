"""brainfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_bf,
)


class TestBf:
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
        program = boolean.brainfuck(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bf_is_the_tree(self) -> None:
        """bf is the folded tree, for constant and sparse tables alike.

        There used to be a minterm construction here and ``bf`` returned
        whichever was shorter.  Folding left the tree ahead on every table
        but the two constant ones -- where it costs about 2.5x, a bounded
        factor on two tables out of 65536 -- so the minterm went away and
        the constant tables go to the tree with everything else.
        """
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        for table in ("0" * 16, "0" * 15 + "1", xor6):  # constant, AND4, dense
            assert boolean.brainfuck(table) == boolean.bf_tree(table)


class TestBfTree:
    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),
        ],
    )
    @pytest.mark.medium
    def test_truth_table(self, table: str, n: int) -> None:
        """Every input combination produces the truth-table result."""
        program = boolean.bf_tree(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = run_bf(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_tree_small_on_dense_tables(self) -> None:
        """The tree shares bit tests, so dense tables stay small."""
        xor6 = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.bf_tree(xor6)) < 10_000

    def test_constant_subtrees_fold(self) -> None:
        """A constant slice emits a leaf instead of branching on more bits.

        Both tables have the same number of ones, so the difference is the
        arrangement alone: ``11110000`` is two constant halves and folds to
        one leaf each, while the parity table has no constant subtree above
        a single row and emits the full tree.
        """
        assert len(boolean.bf_tree("11110000")) < len(boolean.bf_tree("10010110"))

    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row.

        The guard against a fold that fires too eagerly: parity has no
        constant slice above one row, so the tree keeps all ``2**n - 1``
        nodes and every one of the ``2**n`` rows keeps its own leaf.

        Counted through the arm-opening ``[-`` rather than through ``.``:
        leaves no longer print, they record a bit for the single print below
        the tree, so a ``'0'`` leaf emits nothing at all and counting leaves
        directly is not possible.  Every loop in the tree opens by clearing
        what it tested, and each of the 7 nodes opens two -- one for the bit
        and one for the flag -- giving 14; the same table folded to a single
        node (``11110000``) gives 2.
        """
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count("[-") == 14
        assert boolean.bf_tree("11110000").count("[-") == 2
