"""Execute direct chunks, including exact cleanup and dense zero-table state."""

# ruff: noqa: SLF001

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse
from esolangs.tools.fractran import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs._fractran_chunks import chunk_template, chunk_width


def _run(template: str, table: str, row: int, k: int) -> int:
    n = len(table).bit_length() - 1
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
    source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    machine = _Machine(source, io)
    if k >= 64:
        assert machine._cursor is not None
        assert len(machine._cursor.watchers.get(7, ())) == 4
    for _steps in range(200 * k + 100):
        if machine.halted:
            break
        machine.step()
    else:
        pytest.fail("direct chunk program exceeded control budget")
    assert io.getvalue().strip() == str(1 + int(table[row]))
    return _steps - 1


@pytest.mark.medium
@pytest.mark.parametrize("n", [0, 1, 2, pytest.param(3, marks=pytest.mark.slow)])
def test_direct_chunks_realize_every_small_table(n: int) -> None:
    size = 1 << n
    width = chunk_width(n)
    k = (size + width - 1) // width
    for value in range(1 << size):
        table = format(value, f"0{size}b")
        template = chunk_template(table)
        assert len(template.split()) - 1 == 5 * k + n + 257
        for row in range(size):
            _run(template, table, row, k)


@pytest.mark.medium
@pytest.mark.parametrize(
    "n",
    [
        4,
        6,
        8,
        10,
        pytest.param(12, marks=pytest.mark.slow),
        pytest.param(14, marks=pytest.mark.slow),
        pytest.param(16, marks=pytest.mark.slow),
    ],
)
def test_direct_chunks_wider_queries(n: int) -> None:
    rng = random.Random(20261007)
    for arity in range(4, n + 1, 2):
        table = "".join(str(rng.randrange(2)) for _ in range(1 << arity))
    size = 1 << n
    width = chunk_width(n)
    k = (size + width - 1) // width
    template = chunk_template(table)
    assert len(template.split()) - 1 == 5 * k + n + 257
    assert 1 << width <= k
    for row in (0, size // 3, size - 1):
        _run(template, table, row, k)


@pytest.mark.medium
def test_direct_chunks_zero_and_one_cleanup() -> None:
    n = 8
    size = 1 << n
    width = chunk_width(n)
    k = (size + width - 1) // width
    for bit in "01":
        table = bit * size
        template = chunk_template(table)
        _run(template, table, size - 1, k)


@pytest.mark.medium
@pytest.mark.parametrize("n", range(3))
def test_direct_chunks_literal_arithmetic(n: int) -> None:
    size = 1 << n
    for value in range(1 << size):
        table = format(value, f"0{size}b")
        template = chunk_template(table)
        for row in range(size):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
            state, fractions, _ = _parse(source)
            for _ in range(200 * size + 100):
                index = _choose(state, fractions)
                if index is None:
                    break
                numerator, denominator = fractions[index]
                state = state * numerator // denominator
            else:
                pytest.fail("literal chunk program exceeded control budget")
            assert state == 1 + int(table[row])
