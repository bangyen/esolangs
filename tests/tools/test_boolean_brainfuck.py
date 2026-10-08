"""brainfuck generator tests."""

from esolangs.tools.brainfuck import bf_tree


class TestBfTree:
    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row."""
        xor3 = "10010110"
        assert bf_tree(xor3).count("[-") == 14
        assert bf_tree("11110000").count("[-") == 2
