"""Befunge's folded header addresses the table below its steering rows."""

import random

import pytest

import esolangs
from esolangs.tools.befunge import befunge


@pytest.mark.parametrize("inputs", [1, 3, 4, 5, 8, 9, 10])
@pytest.mark.parametrize("width", [1, 5, 11, 27, 80, 81, 1000, None])
def test_befunge_folded_header_reads_the_table(inputs: int, width: int | None) -> None:
    rng = random.Random(inputs)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << inputs))
    program = esolangs.generate("Befunge", table, width)
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
    with pytest.raises(ValueError, match="at most ten inputs"):
        befunge("01" * 1024, width)
