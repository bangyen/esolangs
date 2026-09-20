"""Piet's linear Boolean generator."""

from itertools import product

import pytest

import esolangs
from esolangs.line import Raster
from esolangs.piet import generate


@pytest.mark.parametrize(
    "truth_table",
    ["0", "1", "01", "10", "0001", "0110", "10010110", "0110100110010110"],
)
def test_every_row_executes(truth_table: str) -> None:
    program = generate(truth_table)
    inputs = len(truth_table).bit_length() - 1
    for bits in product((0, 1), repeat=inputs):
        stdin = "".join(f"{bit}\n" for bit in bits)
        row = int("".join(map(str, bits)), 2) if bits else 0
        assert esolangs.run("Piet", program, stdin) == truth_table[row]


def test_png_round_trip_executes_the_same_program() -> None:
    program = generate("0110")
    assert esolangs.run("Piet", Raster.from_png(program.to_png()), "1\n0\n") == "1"


@pytest.mark.medium
def test_every_three_input_function_executes() -> None:
    for encoded in range(256):
        truth_table = f"{encoded:08b}"
        program = generate(truth_table)
        for row in range(8):
            stdin = "".join(f"{bit}\n" for bit in f"{row:03b}")
            assert esolangs.run("Piet", program, stdin) == truth_table[row]


def test_public_generate_returns_a_piet_raster() -> None:
    program = esolangs.generate("Piet", "01")
    assert isinstance(program, Raster)
    assert esolangs.run("Piet", program, "1\n") == "1"
    assert esolangs.verify("Piet", "0110")


def test_emitted_pixels_are_linear_in_the_table() -> None:
    for inputs in range(9):
        entries = 2**inputs
        program = generate("01" * (entries // 2) if entries > 1 else "0")
        assert len(program.rows) * len(program.rows[0]) <= 64 * entries
        assert len(program.to_png()) <= 110 * entries


@pytest.mark.parametrize("truth_table", ["", "010", "0121"])
def test_invalid_truth_table_is_rejected(truth_table: str) -> None:
    with pytest.raises(ValueError, match="truth table"):
        generate(truth_table)
