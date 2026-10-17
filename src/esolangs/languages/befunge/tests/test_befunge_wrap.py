"""Befunge's folded header addresses the table below its steering rows."""

import math
import random

import pytest

import esolangs
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.befunge.generator import (
    _BOUND_NARROW,
    _BOUND_PACKED,
    _BOUND_WIDE,
    _min_columns,
    balance_befunge,
    befunge,
)


@pytest.mark.parametrize("inputs", [1, 4, 13])
# 80 builds what None does.
@pytest.mark.parametrize("width", [1, 5, None])
def test_befunge_folded_header_reads_the_table(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width=width)
    lines = program.splitlines()
    floor = max(map(len, befunge(table, 1).splitlines()))
    assert max(map(len, lines)) <= max(80 if width is None else width, floor)
    assert max(map(len, lines)) <= 80
    assert len(lines) <= 25
    rows = (
        range(len(table))
        if inputs <= 5
        else [0, 1, 11, 27, len(table) // 2, len(table) - 2, len(table) - 1]
    )
    for row in rows:
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert esolangs.run("Befunge", program, stdin=stdin).strip() == table[row]


def test_befunge_keeps_a_header_that_already_fits() -> None:
    table = "01101001"
    assert befunge(table, 80) == befunge(table)
    assert befunge(table, 5) != befunge(table)


@pytest.mark.parametrize("width", [None, 1, 80, 1000])
def test_befunge_refuses_a_table_larger_than_the_torus(width: int | None) -> None:
    with pytest.raises(ValueError, match="at most thirteen inputs"):
        befunge("01" * 8192, width)


def test_single_digit_bound_reclaims_a_column() -> None:
    program = befunge("0110", 1)
    assert max(map(len, program.splitlines())) == 1
    assert len(program.splitlines()) <= 25


@pytest.mark.slow
@pytest.mark.parametrize("inputs", [11, 12, 13])
@pytest.mark.parametrize("width", [1, None])
def test_packed_ascii_lookup_answers_every_row(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width=width)
    assert program.isascii()
    assert set(' "?@\\') <= set(program)
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            esolangs.run("Befunge", program, stdin=stdin, max_steps=500).strip()
            == expected
        )


@pytest.mark.parametrize("inputs", [11, 12, 13])
@pytest.mark.parametrize("kind", ["zero", "one", "parity"])
def test_packed_ascii_lookup_controls_and_balance(inputs: int, kind: str) -> None:
    table = "".join(
        str(row.bit_count() % 2) if kind == "parity" else str(int(kind == "one"))
        for row in range(1 << inputs)
    )
    program = esolangs.generate("Befunge", table, balance=True)
    assert program.isascii()
    assert len(program.splitlines()) <= 25
    assert max(map(len, program.splitlines())) <= 80
    for row in (0, 1, 5, 6, 479, 480, len(table) - 1):
        bits = [int(bit) for bit in f"{row:0{inputs}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        assert (
            esolangs.run("Befunge", program, stdin=stdin, max_steps=500).strip()
            == table[row]
        )


def test_befunge_balance_rejects_oversized_table() -> None:
    with pytest.raises(ValueError, match="at most thirteen inputs"):
        balance_befunge("0" * 16384, "")


def test_xor_has_one_column() -> None:
    xor = esolangs.generate("Befunge", "0110", width=1)
    assert max(map(len, xor.splitlines())) == 1


@pytest.mark.parametrize("inputs", range(2, 14))
def test_balance_crossing_neighbours_match_the_wider_sweep(inputs: int) -> None:
    """Offsets -1..2 from the crossing tie the old -1..4 window on every layout."""
    table = "".join(random.Random(inputs).choice("01") for _ in range(1 << inputs))
    count = 1 << inputs
    layouts = [(5 * inputs + _BOUND_NARROW, 4, 9), (5 * inputs + _BOUND_WIDE, 10, 80)]
    if inputs > 10:
        count = (count + 5) // 6
        layouts = [(5 * inputs + _BOUND_PACKED, 10, 80)]
    for bound, low, high in layouts:
        floor = max(low, _min_columns(count, bound))
        if floor > high:
            continue
        side = math.isqrt(CELL_ASPECT * (count + bound) - 1) + 1

        found = [
            [
                balance_score(befunge(table, min(high, max(floor, side + off))))
                for off in offsets
            ]
            for offsets in (range(-1, 3), range(-1, 2 * CELL_ASPECT + 1))
        ]
        assert min(found[0]) == min(found[1])
