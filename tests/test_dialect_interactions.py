"""Postfix expressions retain behavior at chunk and layout boundaries."""

import pytest

import esolangs
from esolangs import DialectSettings


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 2, 4, 6])
@pytest.mark.parametrize("layout", [None, 1, 40, "balanced"])
def test_postfix_chunk_boundaries_across_sizes(inputs, layout):
    # Parity hides reversed input order; this deterministic mix exposes it.
    table = "".join(
        str(((row * 37) ^ (row >> 1)).bit_count() % 2) for row in range(1 << inputs)
    )
    if inputs > 1:
        reversed_inputs = "".join(
            table[int(format(row, f"0{inputs}b")[::-1], 2)]
            for row in range(1 << inputs)
        )
        assert table != reversed_inputs
    settings = DialectSettings(expression_syntax="postfix")
    options = {"balance": True} if layout == "balanced" else {"width": layout}
    source = esolangs.generate("Alight", table, settings=settings, **options)
    assert (
        esolangs.evaluate("Alight", source, inputs=inputs, settings=settings) == table
    )
