"""Popcount classification agrees with invariance under input permutations."""

from bisect import bisect_right
from itertools import pairwise, permutations, product

from esolangs.generation import helpers
from esolangs.generation.lookup import (
    change_points,
    constant_output,
    packed_cells,
    prefix_counts,
    symmetric_outputs,
)


def test_symmetry_is_invariant_under_every_input_permutation():
    for n in (1, 2, 3):
        _check_permutations(n)


def _check_permutations(n):
    rows = list(product((0, 1), repeat=n))
    orders = list(permutations(range(n)))
    for bits in product("01", repeat=1 << n):
        table = "".join(bits)
        for width in (1, 3, 6):
            for complement in (False, True):
                cells = packed_cells(table, width, offset=32, complement=complement)
                decoded = "".join(
                    format(ord(cell) - 32, f"0{min(width, len(table) - start)}b")[::-1]
                    for start, cell in zip(
                        range(0, len(table), width), cells, strict=True
                    )
                )
                assert decoded == (
                    table.translate(str.maketrans("01", "10")) if complement else table
                )
        assert constant_output(table) == (table[0] if len(set(table)) == 1 else None)
        boundaries = change_points(table)
        runs = [0, *boundaries, len(table)]
        assert boundaries == sorted(set(boundaries))
        assert all(len(set(table[lo:hi])) == 1 for lo, hi in pairwise(runs))
        assert all(table[row] != table[row - 1] for row in boundaries)
        constant = helpers.constant_span_test(table)
        for value in "01":
            counts = prefix_counts(table, value)
            assert len(counts) == len(table) + 1
            assert counts[0] == 0
            for lo in range(len(table) + 1):
                for hi in range(lo, len(table) + 1):
                    count = counts[hi] - counts[lo]
                    assert count == table[lo:hi].count(value)
                    assert constant(lo, hi) == (len(set(table[lo:hi])) <= 1)
                    if count == 1:
                        assert bisect_right(counts, counts[lo], lo, hi + 1) - 1 == (
                            table.index(value, lo, hi)
                        )
        invariant = all(
            table[row]
            == table[sum(values[i] << (n - 1 - j) for j, i in enumerate(order))]
            for row, values in enumerate(rows)
            for order in orders
        )
        outputs = symmetric_outputs(table, n)
        assert (outputs is not None) == invariant, table
        if outputs is not None:
            assert len(outputs) == n + 1
            assert all(
                outputs[sum(values)] == table[row] for row, values in enumerate(rows)
            )
