"""fargo generator tests."""

import itertools
import random

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_fargo,
)


class TestFargo:
    """The Fargo boolean generator: a recursively factored ANF, arms chosen."""

    @pytest.mark.parametrize("n", [4, 5, 8])
    def test_higher_arity_tables(self, n: int) -> None:
        """The construction is uncapped: no arity limit, no search."""
        rng = random.Random(20260830 + n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = boolean.fargo(table)
            for _ in range(10):
                combo = rng.randrange(2**n)
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_fargo(program, bits) == table[combo]

    def test_constant_tables_need_no_reads(self) -> None:
        """A constant table is its degree-zero coefficient alone."""
        assert boolean.fargo("00000000") == "% 0 0\n$\n"
        assert boolean.fargo("11111111") == "% 0 1\n$\n"

    def test_an_all_zero_table_wraps_to_a_constant(self) -> None:
        """No terms to combine: the factored path indexed an empty list."""
        for width in (1, 2, 3, 4):
            assert boolean.fargo("0000", width=width) == "% 0 0\n$\n"
            assert boolean.fargo("00000000", width=width) == "% 0 0\n$\n"

    def test_narrow_dense_anf_keeps_constant_and_long_names(self) -> None:
        """Wrapping NOR keeps the constant term; wrapped, it shrinks vs the ANF form."""
        table = "1" + "0" * 31
        program = boolean.fargo(table, width=1)
        for row in range(32):
            assert run_fargo(program, list(format(row, "05b"))) == table[row]

    def test_narrow_one_input_keeps_literal_one(self) -> None:
        """Literal 1 is not input 1 when only input 0 exists."""
        for table in ("01", "10"):
            program = boolean.fargo(table, width=1)
            assert [run_fargo(program, [b]) for b in "01"] == list(table)

    def test_parity_is_one_term_per_input(self) -> None:
        """Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        """The size tracks algebraic complexity, so parity is O(n log n)."""
        sizes = [
            len(boolean.fargo("".join(str(bin(r).count("1") % 2) for r in range(2**n))))
            for n in (2, 4, 6, 8)
        ]
        gaps = [b - a for a, b in itertools.pairwise(sizes)]
        # Each step of two inputs costs a bounded amount, nowhere near the
        # doubling per input a decision tree would pay.
        assert all(12 <= gap <= 20 for gap in gaps), f"not linear: {sizes}"
        # A decision tree over n == 8 would be thousands of characters.
        assert sizes[-1] < 100, f"growing too fast: {sizes}"

    def test_a_one_dependency_table_folds(self) -> None:
        """One term whatever the arity, which is what the catalogue checks."""
        assert boolean.fargo("11110000") == "% 0 ^ 1 @ 10\n$\n"
        assert len(boolean.fargo("11110000")) < len(boolean.fargo("01101001"))

    def test_dense_anf_growth_is_linear(self) -> None:
        """NOR has every ANF coefficient set, but its source only doubles."""
        sizes = [len(boolean.fargo("1" + "0" * ((1 << n) - 1))) for n in (7, 8)]
        assert sizes[1] < 2 * sizes[0] + 16

    def test_choosing_arms_shrinks_the_corpus(self) -> None:
        """Tables to two inputs never grow; the three-input corpus shrinks 11%."""
        from esolangs.tools.helpers import anf_coefficients
        from tests.tools.fargo_oracle import _anf_expression

        before = after = 0
        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                at = tuple(range(n))
                positive = _anf_expression(anf_coefficients(table), n, at)
                old = len(f"% 0 {positive}\n$\n")
                built = len(boolean.fargo(table))
                if n < 3:
                    assert built <= old, table
                else:
                    before += old
                    after += built
        assert (before, after) == (9556, 8468)

    @pytest.mark.parametrize(
        ("table", "expression"),
        [
            # NOR3: each 1-arm is zero, so each node keeps its 0-arm negated
            # where the positive factoring spelled all eight ANF terms.
            ("10000000", "& ^ 1 @ 10 & ^ 1 @ 1 ^ 1 @ 0"),
            # OR3: each 1-arm is constant one, so each node is ``f0 | x``.
            ("01111111", "| | @ 0 @ 1 @ 10"),
        ],
    )
    def test_a_node_keeps_its_cheap_arm(self, table: str, expression: str) -> None:
        """Polarity is chosen per node by the construction, not by the fill."""
        program = boolean.fargo(table)
        assert program == f"% 0 {expression}\n$\n"
        for combo in range(8):
            bits = list(format(combo, "03b"))
            assert run_fargo(program, bits) == table[combo]
