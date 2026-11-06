"""Popcount classification agrees with invariance under input permutations."""

from bisect import bisect_right
from itertools import permutations, product

from esolangs.generation import helpers
from esolangs.generation.lookup import prefix_counts, symmetric_outputs


def test_symmetry_is_invariant_under_every_input_permutation():
    assert (
        not {"AffineForm", "affine_form", "parity_bias", "symmetric_outputs"}
        & vars(helpers).keys()
    )
    for n in (1, 2, 3):
        _check_permutations(n)


def _check_permutations(n):
    rows = list(product((0, 1), repeat=n))
    orders = list(permutations(range(n)))
    for bits in product("01", repeat=1 << n):
        table = "".join(bits)
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
