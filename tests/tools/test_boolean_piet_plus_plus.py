"""Piet++'s linear Boolean generator, executed."""

import random

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.raster import Raster
from esolangs.tools.piet_plus_plus import piet_plus_plus as generate
from tests.witness_tables import witnesses


@pytest.mark.parametrize("inputs", [1, 2, 3])
def test_witness_tables_execute_through_png(inputs: int) -> None:
    for table in witnesses(inputs):
        program = Raster.from_png(generate(table).to_png())
        assert _evaluate("Piet++", program, inputs=inputs) == table


def test_larger_tables_execute() -> None:
    rng = random.Random(20261007)
    for inputs in (4, 5, 6):
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**inputs))
            program = esolangs.generate("Piet++", table)
            assert _evaluate("Piet++", program, inputs=inputs) == table


def test_emitted_pixels_are_linear_in_the_table() -> None:
    for inputs in range(1, 9):
        program = generate("01" * (2**inputs // 2) if inputs > 1 else "01")
        assert len(program.rows) * len(program.rows[0]) <= 64 * 2**inputs
