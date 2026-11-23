"""Popcount classification agrees with invariance under input permutations."""

from bisect import bisect_right
from itertools import pairwise, permutations, product

from esolangs.generation import helpers
from esolangs.generation.lookup import (
    change_points,
    constant_output,
    majority_bias,
    packed_cells,
    prefix_counts,
    symmetric_outputs,
)


def test_symmetry_is_invariant_under_every_input_permutation():
    for n in (1, 2, 3):
        _check_permutations(n)


def test_prefix_counts_accepts_other_characters_and_empty_tables():
    assert prefix_counts("", "0") == [0]
    assert prefix_counts("01x1", "1") == [0, 0, 1, 1, 2]
    assert prefix_counts("0é1", "1") == [0, 0, 0, 1]
    assert prefix_counts("0é1", "é") == [0, 0, 1, 1]


def test_large_constant_span_counts_cover_the_whole_table():
    half = 1 << 16
    constant = helpers.constant_span_test("0" * half + "1" * half)
    assert constant(0, half)
    assert constant(half, 2 * half)
    assert constant(2 * half, 2 * half)
    assert not constant(half - 1, half + 1)
    assert not constant(0, 2 * half)


def test_symmetric_profiles_cover_every_block():
    for n in (10, 11, 12, 16):
        profile = ("01101" * (n // 5 + 1))[: n + 1]
        table = "".join(profile[row.bit_count()] for row in range(1 << n))
        assert symmetric_outputs(table, n) == profile
        for row in (2, 1024 + 3, len(table) - 2):
            if row >= len(table):
                continue
            flipped = table[:row] + str(1 - int(table[row])) + table[row + 1 :]
            assert symmetric_outputs(flipped, n) is None


def test_majority_requires_the_threshold_in_every_block():
    for n in (10, 11, 12):
        for inverted in (False, True):
            table = "".join(
                str(int((row.bit_count() > n // 2) ^ inverted)) for row in range(1 << n)
            )
            assert majority_bias(table, n) is inverted
            for row in (1, len(table) - 2, len(table) - 1):
                mismatch = table[:row] + str(1 - int(table[row])) + table[row + 1 :]
                assert majority_bias(mismatch, n) is None


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
