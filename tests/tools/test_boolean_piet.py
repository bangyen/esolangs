"""Piet's linear Boolean generator."""

import random
from itertools import pairwise, product

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.raster import Raster
from esolangs.tools.helpers import essential_inputs, read_at
from esolangs.tools.piet import piet as generate
from tests.generator_support import verify_generated


@pytest.mark.parametrize(
    "truth_table",
    ["01", "10", "0001", "0110", "10010110", "0110100110010110"],
)
def test_every_row_executes(truth_table: str) -> None:
    program = generate(truth_table)
    inputs = len(truth_table).bit_length() - 1
    for bits in product((0, 1), repeat=inputs):
        stdin = "".join(f"{bit}\n" for bit in bits)
        row = int("".join(map(str, bits)), 2) if bits else 0
        assert esolangs.run("Piet", program, stdin=stdin) == truth_table[row]


def test_png_round_trip_executes_the_same_program() -> None:
    program = generate("0110")
    assert (
        esolangs.run("Piet", Raster.from_png(program.to_png()), stdin="1\n0\n") == "1"
    )


@pytest.mark.medium
def test_every_three_input_function_executes_through_png() -> None:
    total = 0
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
        total += pixels
        for row in range(8):
            stdin = "".join(f"{bit}\n" for bit in f"{row:03b}")
            assert esolangs.run("Piet", program, stdin=stdin) == truth_table[row]
    # Parent table lookup emitted 38,997 codels over this exhaustive corpus.
    assert total == 34_638


@pytest.mark.slow
def test_larger_functions_execute_through_png() -> None:
    rng = random.Random(20261001)
    for inputs in (4, 5, 6):
        tables = [
            "".join(rng.choice("01") for _ in range(2**inputs)) for _ in range(12)
        ]
        for row in (0, 2**inputs - 1, 2**inputs // 3):
            table = "".join(str(int(i == row)) for i in range(2**inputs))
            tables.extend((table, table.translate(str.maketrans("01", "10"))))
        for table in tables:
            for balanced in (False, True):
                image = esolangs.generate("Piet", table, balance=balanced)
                decoded = Raster.from_png(image.to_png())
                assert _evaluate("Piet", decoded, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("balanced", [False, True])
def test_larger_asymmetric_function_executes_through_png(*, balanced: bool) -> None:
    table = "".join(str(int(row in (0, 7, 31, 63))) for row in range(64))
    image = esolangs.generate("Piet", table, balance=balanced)
    assert _evaluate("Piet", Raster.from_png(image.to_png()), inputs=6) == table


def test_public_generate_returns_a_piet_raster() -> None:
    program = esolangs.generate("Piet", "01")
    assert isinstance(program, Raster)
    assert esolangs.run("Piet", program, stdin="1\n") == "1"
    assert verify_generated("Piet", "0110")


def test_emitted_pixels_are_linear_in_the_table() -> None:
    for inputs in range(1, 9):
        entries = 2**inputs
        program = generate("01" * (entries // 2) if entries > 1 else "0")
        assert len(program.rows) * len(program.rows[0]) <= 64 * entries
        assert len(program.to_png()) <= 110 * entries


def test_ignored_inputs_are_read_but_not_indexed() -> None:
    """An ignored input costs its read and a pop, never table entries."""
    widths = [len(generate("0" * 2**inputs).rows[0]) for inputs in range(1, 9)]
    assert [b - a for a, b in pairwise(widths)] == [2] * 7
    # The second input is ignored: the stored table is the one-input one.
    assert len(generate("0011").rows[0]) == len(generate("01").rows[0]) + 2
    assert esolangs.run("Piet", generate("0" * 8), stdin="1\n1\n1\n") == "0"


@pytest.mark.parametrize("truth_table", ["", "0", "1", "010", "0121"])
def test_invalid_truth_table_is_rejected(truth_table: str) -> None:
    with pytest.raises(ValueError, match="truth table"):
        generate(truth_table)


def test_piet_generator_and_interpreter() -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.piet import run
    from esolangs.tools.piet import piet as generate

    program = generate("01", scale=2)
    io = ScriptedIO("1")
    run(program, io)
    assert io.getvalue() == "1"
