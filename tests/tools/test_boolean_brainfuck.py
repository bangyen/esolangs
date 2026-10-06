"""brainfuck generator tests."""

from esolangs import tools as boolean


class TestBfTree:
    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row."""
        xor3 = "10010110"
        assert boolean.bf_tree(xor3).count("[-") == 14
        assert boolean.bf_tree("11110000").count("[-") == 2
