"""Piet++'s Read-addressed Boolean generator, executed."""

import random

import pytest

import esolangs
from esolangs.languages.piet_plus_plus.generator import piet_plus_plus as generate
from esolangs.raster import Raster
from esolangs.runtime._evaluate import _evaluate
from tests.support.witness_tables import parity, witnesses


@pytest.mark.parametrize("inputs", [1, 2, 3])
def test_witness_tables_execute_through_png(inputs: int) -> None:
    for table in witnesses(inputs):
        program = Raster.from_png(generate(table).to_png())
        assert _evaluate("Piet++", program, inputs=inputs) == table


@pytest.mark.parametrize("inputs", [4, 5, 6, 7])
def test_larger_tables_execute(inputs: int) -> None:
    rng = random.Random(20261028 + inputs)
    tables = ["".join(rng.choice("01") for _ in range(2**inputs)) for _ in range(3)]
    for table in (*tables, parity(inputs)):
        program = Raster.from_png(esolangs.generate("Piet++", table).to_png())
        assert _evaluate("Piet++", program, inputs=inputs) == table


@pytest.mark.parametrize("inputs", [4, 5, 7])
def test_ignored_inputs_are_read_and_dropped(inputs: int) -> None:
    rng = random.Random(inputs)
    core = "".join(rng.choice("01") for _ in range(2 ** (inputs - 2)))
    for table in (
        "".join(bit * 4 for bit in core),
        core * 4,
        "".join(bit * 2 for bit in core) * 2,
    ):
        assert _evaluate("Piet++", generate(table), inputs=inputs) == table


def test_the_table_is_in_the_pixels() -> None:
    """Flipping one data bit changes exactly that row: Read is load-bearing."""
    table = parity(6)
    rows = [list(row) for row in generate(table).rows]
    assert rows[2][-3] == (0, 0, 0)
    pixel = next(x for x, p in enumerate(rows[2]) if p != (0, 0, 0))
    red, green, blue = rows[2][pixel]
    rows[2][pixel] = (red, green, blue ^ 1)
    flipped = Raster(tuple(tuple(row) for row in rows))
    wrong = [
        row
        for row in range(64)
        if esolangs.run(
            "Piet++",
            flipped,
            stdin="".join(f"{row >> (5 - i) & 1}\n" for i in range(6)),
        )
        != table[row]
    ]
    assert len(wrong) == 1


def test_data_pixels_are_never_palette_colours() -> None:
    """A data pixel is no block (red byte 1), so none can join a program block."""
    image = generate(parity(8))
    assert all(pixel[0] == 1 for pixel in image.rows[2][:-1] if pixel != (0, 0, 0))
