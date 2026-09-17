"""Covers :mod:`esolangs.tools.arrowqueue`."""

import random
from itertools import pairwise

import pytest

from esolangs.tools.arrowqueue import arrowqueue_setters
from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from esolangs.tools.parameterized import _instantiate_arrowqueue


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue.

    ArrowQueue has no output, so the generator's answer is read from the
    termination convention: an instantiated program halts for a ``0`` table
    entry and loops forever for a ``1`` entry.  The run is bounded by
    state-cycle detection (the queue stays bounded on the sustaining rings),
    so the repeated-snapshot proof reports the ``1`` cases immediately.
    """

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input halts or loops per its table entry."""
        from esolangs.tools import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_arrowqueue(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
        from esolangs.tools import parameterized

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = parameterized.arrowqueue(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    def test_linear_marker_cascade_executes_every_row(self) -> None:
        """Wide inputs become marker counts and select one cascade stage."""
        from esolangs.tools import parameterized

        n = 6
        table = "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(2**n))
        template = parameterized.arrowqueue(table)
        sizes = set()
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run_arrowqueue(program) == table[row], row
        assert len(sizes) == 1

    def test_linear_marker_cascade_scales_with_table(self) -> None:
        """Dense wide templates grow no faster than the table doubles."""
        from esolangs.tools import parameterized

        sizes = [len(parameterized.arrowqueue("1" * (2**n))) for n in range(7, 11)]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.tools import parameterized

        template = parameterized.arrowqueue("0110")
        assert "{X" not in template
        setters = arrowqueue_setters(template, 2)
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in setters)
        assert len(runs(template, TEMPLATE_CHAR, setters)) == 2

    @pytest.mark.parametrize("table", ["0110", "0110100110010110" * 2])
    def test_each_run_is_a_block_of_rows(self, table: str) -> None:
        """A run counts a block's newlines, so a run is rows of its own.

        The tree route's first block is one row taller than the rest; the
        linear route's blocks are one row per marker, ``2**(n-1-i)`` for
        input ``i``.  Filled, the rows come back where the run stood.
        """
        from esolangs.tools import parameterized

        n = len(table).bit_length() - 1
        template = parameterized.arrowqueue(table)
        setters = arrowqueue_setters(template, n)
        lines = template.splitlines()
        for i, (zero, one) in enumerate(setters):
            assert len(zero) == len(one)
            rows = zero.count("\n") + 1
            if template.startswith(" *\n"):
                assert rows == 2 ** (n - 1 - i)
            else:
                assert rows == (5 if i == 0 else 4)
            assert TEMPLATE_CHAR * len(zero) in lines
        filled = self.instantiate(template, [1] * n)
        inside = sum(zero.count("\n") for zero, _ in setters)
        assert filled.count("\n") == template.count("\n") + inside

    @pytest.mark.parametrize(
        ("table", "mixed"),
        [
            ("1111", "1010"),
            ("11110000", "10010110"),
            ("1111111100000000", "1001011001101001"),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, mixed: str) -> None:
        """A constant subtree emits one drained leaf, not a full branch set.

        The comparison table has the same ones-count, so a shorter template
        means the tree folded rather than that something else shrank.
        """
        from esolangs.tools import parameterized

        assert len(parameterized.arrowqueue(table)) < len(
            parameterized.arrowqueue(mixed)
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1" * 16, 4),
            ("0" * 16, 4),
            ("1111111100000000", 4),
            ("1111000000000000", 4),
            ("1" * 32, 5),
            ("1" * 16 + "0" * 16, 5),
        ],
    )
    def test_folded_tables_past_three_inputs(self, table: str, n: int) -> None:
        """Folded leaves stay correct deeper than the exhaustive n <= 3 sweep."""
        from esolangs.tools import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    def test_folded_one_leaf_drains_the_bits_it_skipped(self) -> None:
        """The drain is required: a ring needs the queue it expects.

        A folded ``1`` leaf pops a direction at each of its ring's corners
        and requires exactly ``R, D, L, U``.  Without the drains, the bits
        the skipped branches never popped sit ahead of those components, the
        corners pop the wrong directions, the ring does not close, and the
        program halts -- reporting ``0`` for a ``1`` entry.  Dropping the
        drains here must therefore break the table.
        """
        from esolangs.tools.parameterized import _TREE_1, _drained_leaf

        undrained = _drained_leaf("1", 0)  # no drains at all
        assert [row.strip() for row in undrained if row.strip()] == [
            row.strip() for row in _TREE_1
        ]

        # With two levels skipped the drained leaf is strictly taller than
        # the bare ring, and that extra height is the drain chain.
        drained = _drained_leaf("1", 2)
        assert len(drained) == len(_TREE_1) + 2
        assert sum(row.count("+") for row in drained) == 4 + 2  # ring + drains

    def test_folded_zero_leaf_needs_no_drain(self) -> None:
        """A ``0`` leaf halts by leaving the grid, which the queue cannot stop."""
        from esolangs.tools import parameterized
        from esolangs.tools.parameterized import _TREE_0, _drained_leaf

        # It carries no drain at all.  Paying for one is not free: the
        # staircase sits a column right of the branches it replaces, so
        # ``_compact`` finds fewer all-blank columns and the instantiated
        # program grows -- which is what made AND-2 larger than before the
        # fold until this case was carved out.
        assert _drained_leaf("0", 3) == list(_TREE_0)
        for table, n in (("0000", 2), ("0" * 8, 3)):
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert self.run_arrowqueue(self.instantiate(template, bits)) == "0"

    def test_folding_never_grows_a_program(self) -> None:
        """No instantiated program is larger than its unfolded equivalent.

        A fold that costs characters is not a fold.  AND-2 briefly regressed
        (124 to 128 bytes) when ``0`` leaves were drained too: a folded
        ``00`` half gained a staircase where the branch pair it replaced was
        cheaper, and the extra column blocked ``_compact``.  This pins the
        whole n <= 2 space, where such a regression showed up.
        """
        from esolangs.tools.parameterized import (
            _TREE_0,
            _TREE_1,
            _connect,
            _tree,
        )

        def unfolded(values: list[str]) -> list[str]:
            """The pre-fold construction: a branch per level, never collapsed."""
            if len(values) == 2:
                return _connect(
                    _TREE_1 if values[0] == "1" else _TREE_0,
                    _TREE_1 if values[1] == "1" else _TREE_0,
                )
            half = len(values) // 2
            return _connect(unfolded(values[:half]), unfolded(values[half:]))

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                folded = _tree(list(table))
                plain = unfolded(list(table))
                assert sum(len(r.rstrip()) for r in folded) <= sum(
                    len(r.rstrip()) for r in plain
                ), table

    def test_fold_keeps_equal_width_embedding(self) -> None:
        """Every instantiation of a folded template is the same length.

        The fold shrinks the tree, which is shared by all instantiations, so
        the program's size still cannot leak which bits were embedded.
        """
        from esolangs.tools import parameterized

        for table, n in (("1111", 2), ("1100", 2), ("11110000", 3)):
            template = parameterized.arrowqueue(table)
            sizes = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"{table}: {sizes}"

    def test_bare_ring_is_entry_sensitive(self) -> None:
        """A bare ring sustains on right-entry and *halts* on down-entry.

        The two ways a subtree is entered are not interchangeable, which is
        the sharpest edge in the construction: the tree's top level is
        entered heading down at column 1, while every recursive subtree is
        entered heading right at its own ``(0, 0)``.  A bare
        :data:`_TREE_1` only loops under the second.  Pinned because a
        refactor that "simplified" the top-level entry to hand a bare ring
        the down-entry would silently turn every constant-``1`` table into
        a halt -- reporting ``0`` for every entry.

        See ``the relevant generator tests`` (lemmas L2/L2'/L4).
        """
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.tools.parameterized import _TREE_1
        from esolangs.vm import run_until_halt_or_cycle

        rdlu = (0, 1, 2, 3)

        def verdict(state: tuple[int, int, int, tuple[int, ...]]) -> str:
            machine = _Machine(list(_TREE_1))
            machine.state = (*state, not machine.grid)
            return "0" if run_until_halt_or_cycle(machine) else "1"

        assert verdict((0, 0, 0, rdlu)) == "1"  # right-entry: the ring closes
        assert verdict((0, 1, 1, rdlu)) == "0"  # down-entry: it does not

    def test_constant_one_never_tops_out_as_a_bare_ring(self) -> None:
        """The top-level tree always carries a drain, so down-entry is safe.

        What makes the entry-sensitivity above harmless: a constant table
        folds to ``_drained_leaf(v, n)`` with ``n >= 1`` (a one-entry table
        is refused), so the top-level leaf's first ``+`` sits at ``(0, 1)``
        -- exactly where the header's descent lands -- and the bare ring
        appears only nested at column offset 3, where entry is rightward.
        """
        from esolangs.tools.parameterized import (
            _TREE_1,
            _drained_leaf,
            _tree,
        )

        for n in range(1, 6):
            assert _tree(list("1" * (2**n))) == _drained_leaf("1", n)

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                assert _tree(list(table)) != list(_TREE_1), table
