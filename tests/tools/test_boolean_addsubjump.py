"""addsubjump generator tests."""

from itertools import pairwise

from esolangs import tools as boolean


class TestAddSubJump:
    def test_three_input_total(self) -> None:
        """Shared residuals reduce the n=3 total from 99,032 to 94,800."""
        total = sum(len(boolean.addsubjump(f"{value:08b}")) for value in range(256))
        assert total == 94800

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
