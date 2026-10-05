"""Piet's linear Boolean generator."""

from itertools import pairwise

import pytest

import esolangs
from esolangs.raster import Raster
from esolangs.tools.helpers import essential_inputs, read_at
from esolangs.tools.piet import piet as generate


@pytest.mark.medium
def test_three_input_rendered_area_bound() -> None:
    for encoded in range(256):
        truth_table = f"{encoded:08b}"
        program = Raster.from_png(generate(truth_table).to_png())
        pixels = sum(map(len, program.rows))
        essential = essential_inputs(truth_table, 3)
        reduced = read_at(truth_table, essential, 3)
        parent_width = (
            18
            + 2 * len(reduced)
            + reduced.count("0")
            + 5 * len(essential)
            + 2 * (3 - len(essential))
        )
        assert pixels <= 3 * parent_width


def test_public_generate_returns_a_piet_raster() -> None:
    program = esolangs.generate("Piet", "01")
    assert isinstance(program, Raster)


def test_emitted_pixels_are_linear_in_the_table() -> None:
    for inputs in range(1, 9):
        entries = 2**inputs
        program = generate("".join(str(row.bit_count() % 2) for row in range(entries)))
        assert len(program.rows) * len(program.rows[0]) <= 64 * entries
        assert len(program.to_png()) <= 110 * entries


def test_ignored_inputs_add_only_reader_columns() -> None:
    """An ignored input adds its reader columns without table entries."""
    widths = [len(generate("0" * 2**inputs).rows[0]) for inputs in range(1, 9)]
    assert [b - a for a, b in pairwise(widths)] == [2] * 7
    assert len(generate("0011").rows[0]) == len(generate("01").rows[0]) + 2


@pytest.mark.parametrize("truth_table", ["", "0", "1", "010", "0121"])
def test_invalid_truth_table_is_rejected(truth_table: str) -> None:
    with pytest.raises(ValueError, match="truth table"):
        generate(truth_table)
