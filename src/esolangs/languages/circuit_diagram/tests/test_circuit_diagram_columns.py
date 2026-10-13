"""Recycled-column successor allocation against a set oracle."""

import random

import pytest

from esolangs.languages.circuit_diagram.generator.columns import _FreeColumns


def test_successors_survive_growth_recycling_and_band_reset() -> None:
    rng = random.Random(8109)
    allocator = _FreeColumns()
    free = set()
    for step in range(2000):
        if step % 317 == 0:
            allocator.clear()
            free.clear()
        column = rng.randrange(1024)
        if rng.randrange(3) == 0 and column not in free:
            allocator.add(column)
            free.add(column)
        after = rng.randrange(-4, 1100)
        expected = min((item for item in free if item > after), default=None)
        assert allocator.first_after(after) == expected
        assert allocator.take_after(after) == expected
        if expected is not None:
            free.remove(expected)


def test_a_double_release_aborts() -> None:
    allocator = _FreeColumns()
    allocator.add(6)
    with pytest.raises(AssertionError, match="released twice"):
        allocator.add(6)
