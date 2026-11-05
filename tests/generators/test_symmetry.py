"""Popcount classification agrees with invariance under input permutations."""

from itertools import permutations, product

from esolangs.generation.helpers import symmetric_outputs


def test_symmetry_is_invariant_under_every_input_permutation():
    for n in (1, 2, 3):
        _check_permutations(n)


def _check_permutations(n):
    rows = list(product((0, 1), repeat=n))
    orders = list(permutations(range(n)))
    for bits in product("01", repeat=1 << n):
        table = "".join(bits)
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
