"""brainfuck generator tests."""

import pytest

from esolangs.tools.brainfuck import bf_tree


class TestBfTree:
    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row."""
        xor3 = "10010110"
        assert bf_tree(xor3).count("[-") == 14
        assert bf_tree("11110000").count("[-") == 2


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.brainfuck import _bf_ordered
    from tests.generator_support import assert_shared_program

    zero = "0001011101101001" * 4
    one = "0110100100010111" * 4
    table = zero + one + one + zero
    plain = _bf_ordered(table, tuple(range(8)), share=False)
    assert_shared_program(
        "brainfuck",
        table,
        plain,
        69 * 8 + 44,
        lambda p: (
            2 * 8 + 6 + (2 * 8).bit_length() + (8).bit_length() + len(p).bit_length()
        ),
    )
