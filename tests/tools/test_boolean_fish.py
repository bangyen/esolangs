"""Fish layout constraints; independent execution is checked in the semantics suite."""

from itertools import pairwise

import pytest

from esolangs.tools.fish import fish


@pytest.mark.parametrize("width", [1, 3, 4, 5, 7, 13, 40, 80])
def test_folded_lookup_respects_width(width: int) -> None:
    for value in range(256):
        program = fish(f"{value:08b}", width)
        assert max(map(len, program.split("\n"))) <= max(3, width)


def test_source_growth_is_linear_in_the_table() -> None:
    sizes = [len(fish("01" * (1 << (n - 1)))) for n in range(1, 13)]
    assert all(right <= 2 * left for left, right in pairwise(sizes))
