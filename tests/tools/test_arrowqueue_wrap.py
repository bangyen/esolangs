"""ArrowQueue's narrow cascade preserves the termination answer."""

import random

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
        assert max(map(len, template.splitlines())) <= max(5, width)
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


@pytest.mark.parametrize("width", [1, 4, 5, 6, 80])
def test_arrowqueue_narrow_leaf_ring_executes_every_small_table(width: int) -> None:
    for inputs in range(1, 4):
        for value in range(2 ** (2**inputs)):
            table = format(value, f"0{2**inputs}b")
            template = arrowqueue(table, width)
            for row, expected in enumerate(table):
                bits = [int(bit) for bit in format(row, f"0{inputs}b")]
                source = _instantiate_arrowqueue(template, bits)
                assert diverges("ArrowQueue", source, "") is (expected == "1")


def test_arrowqueue_leaf_gap_floor_and_corpus_size() -> None:
    assert max(map(len, arrowqueue("0110", 1).splitlines())) == 5
    assert sum(len(arrowqueue(format(v, "08b"), 1)) for v in range(256)) == 54039


def test_arrowqueue_compact_rings_at_larger_arity() -> None:
    rng = random.Random(20260930)
    for inputs in (5, 8):
        table = format(rng.getrandbits(2**inputs), f"0{2**inputs}b")
        template = arrowqueue(table, 1)
        for row in rng.sample(range(2**inputs), 8):
            bits = [int(bit) for bit in format(row, f"0{inputs}b")]
            source = _instantiate_arrowqueue(template, bits)
            assert diverges("ArrowQueue", source, "") is (table[row] == "1")
