"""Circlefuck boolean generation: the deleting lookup and its index."""

import random

import pytest

from esolangs import tools as boolean


class TestCirclefuck:
    def test_the_table_is_one_character_an_entry(self) -> None:
        """Doubling the arity doubles the program's table and nothing else.

        The decoder is a fixed number of characters whatever the arity --
        reads aside, which are linear in the input count -- so one added
        input costs the entries it adds and the growth itself doubles.
        """
        rng = random.Random(11)
        sizes = {}
        for n in (10, 11, 12):
            table = "".join(rng.choice("01") for _ in range(2**n))
            sizes[n] = len(boolean.circlefuck(table))
        grew = sizes[11] - sizes[10]
        assert abs(grew - 2**10) < 0.1 * 2**10, grew
        assert abs((sizes[12] - sizes[11]) - 2 * grew) < 0.1 * 2**10

    def test_dependency_reduction_shrinks_emitted_program(self) -> None:
        """Dependency reduction shrinks the emitted lookup table."""
        assert len(boolean.circlefuck("11111111")) < len(
            boolean.circlefuck("10101010"),
        )
        assert len(boolean.circlefuck("10101010")) < len(
            boolean.circlefuck("10010110"),
        )
        assert len(boolean.circlefuck("11110000")) < len(
            boolean.circlefuck("10010110"),
        )


@pytest.mark.parametrize("seed", range(40))
def test_circlefuck_essential_inputs_are_the_ones_flipping_changes(seed: int) -> None:
    """The sibling-block scan finds exactly the inputs the table depends on."""
    from esolangs.tools.circlefuck import _essential_byte_inputs

    rng = random.Random(seed)
    n = rng.randint(1, 8)
    # A function of a random subset of the inputs, so most are inessential.
    subset = sorted(rng.sample(range(n), rng.randint(0, n)))
    values = [rng.choice((48, 49, 7)) for _ in range(2 ** len(subset))]
    table = []
    for row in range(2**n):
        index = 0
        for i in subset:
            index = (index << 1) | ((row >> (n - 1 - i)) & 1)
        table.append(values[index])
    expected = [
        i
        for i in range(n)
        if any(table[row] != table[row ^ (1 << (n - 1 - i))] for row in range(2**n))
    ]
    assert _essential_byte_inputs(table, n) == expected


@pytest.mark.parametrize("seed", range(12))
def test_circlefuck_projection_is_the_table_over_its_essential_inputs(
    seed: int,
) -> None:
    """Projecting and then re-expanding gives the table back.

    The projection is the one place the emitted table stops being the given
    one, and a permuted or off-by-one projection still emits a runnable
    program -- for a different function.
    """
    from esolangs.tools.circlefuck import _essential_byte_inputs, _projected

    rng = random.Random(seed)
    n = rng.randint(1, 7)
    subset = sorted(rng.sample(range(n), rng.randint(1, n)))
    values = [rng.choice((48, 49)) for _ in range(2 ** len(subset))]
    table = []
    for row in range(2**n):
        key = 0
        for i in subset:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        table.append(values[key])
    essential = _essential_byte_inputs(table, n)
    rows = _projected(table, n, essential)
    assert len(rows) == 2 ** len(essential)
    for row in range(2**n):
        key = 0
        for i in essential:
            key = (key << 1) | ((row >> (n - 1 - i)) & 1)
        assert rows[key] == table[row], row
