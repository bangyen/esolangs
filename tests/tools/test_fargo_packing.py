"""Packed Fargo coefficients, word work, and executed layout scaling."""

import random
import sys
from types import FrameType

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fargo import run
from esolangs.tools.fargo import _arm_expression, fargo
from esolangs.tools.helpers import anf_coefficients
from tests.witness_tables import nested_dense


def _scalar_coefficients(table: str) -> list[int]:
    values = [int(bit) for bit in table]
    stride = 1
    while stride < len(values):
        for start in range(0, len(values), stride * 2):
            for offset in range(start, start + stride):
                values[offset + stride] ^= values[offset]
        stride *= 2
    return values


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17])
def test_packed_coefficients_match_elementwise_transform(n: int) -> None:
    rng = random.Random(20260929 + n)
    table = format(rng.getrandbits(1 << n), f"0{1 << n}b")
    assert anf_coefficients(table) == _scalar_coefficients(table)


@pytest.mark.parametrize("table", ["0", "1"])
def test_reduced_constants_keep_their_coefficient(table: str) -> None:
    assert anf_coefficients(table) == [int(table)]


@pytest.mark.medium
@pytest.mark.parametrize("n", [6, 7, 8, 9, 15, 16, 17])
def test_packed_arm_word_work_and_execution(n: int) -> None:
    """Word visits stay bounded per row; dense inputs are positive controls."""
    table = nested_dense(n)
    coefficients = anf_coefficients(table)
    visits = 0

    def profile(frame: FrameType, event: str, _arg: object) -> None:
        nonlocal visits
        if (
            event == "call"
            and frame.f_code.co_name == "count"
            and frame.f_code.co_filename == _arm_expression.__code__.co_filename
        ):
            visits += 1

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        expression = _arm_expression(table, coefficients, n, tuple(range(n)))
    finally:
        sys.setprofile(previous)
    assert len(table) // 4 <= visits <= 12 * len(table)
    row = (1 << n) // 3
    io = ScriptedIO(str(row))
    run(f"% 0 {expression}\n$\n", io)
    assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 1])
def test_packed_layout_scaling_executes(width: int | None) -> None:
    """Measure rendered text past the bounded route and execute every build."""
    sizes = []
    for n in (8, 10, 12):
        table = nested_dense(n)
        program = fargo(table, width=width)
        sizes.append(len(program))
        for row in (0, (1 << n) // 3, (1 << n) - 1):
            io = ScriptedIO(str(row))
            run(program, io)
            assert io.getvalue() == table[row]
    assert sizes[1] - sizes[0] > 0
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


def test_narrow_packed_constants_consume_input() -> None:
    for bit in "01":
        program = fargo(bit * 64, width=1)
        io = ScriptedIO("63")
        run(program, io)
        assert io.getvalue() == bit
        assert io.reads == 1
