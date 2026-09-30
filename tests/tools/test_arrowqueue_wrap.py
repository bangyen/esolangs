"""ArrowQueue's narrow cascade preserves the termination answer."""

import pytest

import esolangs
from esolangs.tools.arrowqueue import arrowqueue
from tests.divergence import diverges
from tests.tools.fills import _instantiate_arrowqueue


@pytest.mark.parametrize("width", [1, 5, 6, 11, 80, None])
@pytest.mark.parametrize(
    "table",
    [
        "01",
        "10",
        "0000",
        "1111",
        "0110",
        "00010111",
        "0110100110010110",
        "01101001" * 4,
    ],
)
def test_arrowqueue_width_preserves_every_row(table: str, width: int | None) -> None:
    template = esolangs.generate("ArrowQueue", table, width)
    plain = arrowqueue(table)
    if width is None:
        assert template == plain
    else:
        assert max(map(len, template.splitlines())) <= max(6, width)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        source = _instantiate_arrowqueue(template, bits)
        assert diverges("ArrowQueue", source, "") is (expected == "1")


def test_arrowqueue_replaces_an_overwide_tree() -> None:
    table = "0110100110010110"
    assert max(map(len, arrowqueue(table).splitlines())) > 6
    assert arrowqueue(table, 6) != arrowqueue(table)
    assert arrowqueue(table, 80) == arrowqueue(table)
