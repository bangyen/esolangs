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


@pytest.mark.medium
def test_every_small_function_executes_without_growing() -> None:
    from esolangs.tools.piet import _operations, strip
    from esolangs.tools.piet_plus_plus import _next_colour

    total = 0
    for inputs in range(1, 4):
        for encoded in range(2 ** (2**inputs)):
            table = f"{encoded:0{2**inputs}b}"
            old = strip(_operations(table, inputs), (0, 170, 0), _next_colour)
            image = generate(table)
            area = len(image.rows) * len(image.rows[0])
            assert area <= len(old.rows) * len(old.rows[0])
            assert (
                _evaluate("Piet++", Raster.from_png(image.to_png()), inputs=inputs)
                == table
            )
            if inputs == 3:
                total += area
    assert total == 34_512


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [4, 5, 6])
def test_folded_functions_execute_through_png(inputs: int) -> None:
    rng = random.Random(20261009)
    for _ in range(12):
        table = "".join(rng.choice("01") for _ in range(2**inputs))
        image = generate(table)
        assert (
            _evaluate("Piet++", Raster.from_png(image.to_png()), inputs=inputs) == table
        )


def test_large_function_uses_a_smaller_fold() -> None:
    from esolangs.tools.piet import _operations, strip
    from esolangs.tools.piet_plus_plus import _next_colour

    rng = random.Random(20261009)
    table = "".join(rng.choice("01") for _ in range(256))
    old = strip(_operations(table, 8), (0, 170, 0), _next_colour)
    image = generate(table)
    assert len(image.rows) > 3
    assert len(image.rows) * len(image.rows[0]) < len(old.rows) * len(old.rows[0]) * 0.9
    for row in (0, 85, 255):
        assert (
            esolangs.run(
                "Piet++",
                Raster.from_png(image.to_png()),
                stdin="\n".join(f"{row:08b}"),
                max_steps=10_000,
            )
            == table[row]
        )
