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

    @pytest.mark.parametrize("n", [1, 2, 3])
    @pytest.mark.medium
    def test_every_table_at_small_arity(self, n: int) -> None:
        """Exhaustive: every table, every input combination."""
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            program = boolean.fargo(table)
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                got = run_fargo(program, bits)
                assert got == table[combo], f"table {table} inputs {bits}"

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
        """No terms to combine: the factored path indexed an empty list.

        ``width`` below the compact program's 5 columns routes to the
        factored builder, which ``combine``d an empty term list for the
        all-zero table.
        """
        for width in (1, 2, 3, 4):
            assert boolean.fargo("0000", width=width) == "% 0 0\n$\n"
            assert boolean.fargo("00000000", width=width) == "% 0 0\n$\n"

    def test_narrow_dense_anf_keeps_constant_and_long_names(self) -> None:
        """Wrapping NOR needs the constant coefficient and more than 26 labels."""
        table = "1" + "0" * 31
        program = boolean.fargo(table, width=1)
        assert "aa " in program
        for row in range(32):
            assert run_fargo(program, list(format(row, "05b"))) == table[row]

    def test_parity_is_one_term_per_input(self) -> None:
        """Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        """The size tracks algebraic complexity, so parity is O(n log n).

        This is the property that makes Fargo's generator unlike the
        tree-shaped ones: a decision tree spends O(2**n) on parity, the
        table that folds nothing.  Parity's ANF is one single-variable
        term per input, so each extra input adds one ``^ @ i`` -- a
        constant plus the index's own binary width, which is why the
        steps widen by one every time ``i`` gains a digit rather than
        staying exactly equal.
        """
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

    def test_choosing_arms_never_grows_a_program(self) -> None:
        """No table to three inputs is longer than its positive factoring.

        The positive factoring oracle in name order is the build before
        arms and orders were chosen: three-input totals fall from 9,556 to
        8,202 with the arms, 7,576 with four orders, and 7,467 with
        character-cost splits.
        """
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
                assert built <= old, table
                if n == 3:
                    before += old
                    after += built
        assert (before, after) == (9556, 7740)

    @pytest.mark.medium
    def test_character_cost_five_input_corpus(self) -> None:
        """The seeded ship gate: no growth, 7.79% smaller, every row executed."""
        from esolangs.tools.fargo import _expression, _orders

        rng = random.Random(20260929)
        for _ in range(12 * 16):
            rng.choice("01")
        before = after = 0
        for _ in range(200):
            table = "".join(rng.choice("01") for _ in range(32))
            lengths = []
            for order in _orders(5, compact=True):
                expression = _expression(table, 5, order)
                assert expression is not None
                lengths.append(len(f"% 0 {expression}\n$\n"))
            old = min(lengths)
            program = boolean.fargo(table)
            assert len(program) <= old, table
            before += old
            after += len(program)
            for row in range(32):
                assert run_fargo(program, list(format(row, "05b"))) == table[row]
        assert (before, after) == (25611, 23615)

    def test_character_cost_ties_use_executed_steps(self) -> None:
        """Selector-frame overhead is included in the size tie breaker."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.fargo import _Machine
        from esolangs.tools.fargo import _cost_key

        table = "10101111011001100111100001010100"
        program = boolean.fargo(table)
        assert program.startswith("M ")
        for row in (0, 31):
            io = ScriptedIO(str(row))
            machine = _Machine(program, io)
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            assert io.getvalue() == table[row]
            assert _cost_key(program) == (len(program), steps - 4)

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
