"""Execute direct chunks, including exact cleanup and dense zero-table state."""

# ruff: noqa: SLF001

import random

import pytest

from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.languages.fractran.generator import PAIR
from esolangs.languages.fractran.interpreter import _choose, _Machine, _parse
from esolangs.languages.fractran.interpreter import index as fractran_index
from esolangs.languages.fractran.tests.proofs._fractran_chunks import (
    chunk_template,
    chunk_width,
    decimal_progression,
    mapped_chunk_template,
    mapped_chunk_width,
)
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import row_bits


def _run(template: str, table: str, row: int, k: int, watchers: int | None = 4) -> int:
    n = len(table).bit_length() - 1
    bits = row_bits(row, n)
    source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    machine = _Machine(source, io)
    if k >= 64 and watchers is not None:
        assert machine._cursor is not None
        assert len(machine._cursor.watchers.get(7, ())) == watchers
    for _steps in range(200 * k + 100):
        if machine.halted:
            break
        machine.step()
    else:
        pytest.fail("direct chunk program exceeded control budget")
    assert io.getvalue().strip() == str(1 + int(table[row]))
    if watchers is None:
        assert machine._cursor is None
        assert machine.inspections <= 32 * (_steps + n + 1)
    return _steps - 1


@pytest.mark.medium
@pytest.mark.parametrize(
    "n", [0, 1, 2, 6, 10, pytest.param(16, marks=pytest.mark.slow)]
)
def test_mapped_chunks_execute(n: int, monkeypatch: pytest.MonkeyPatch) -> None:
    size = 1 << n
    width = mapped_chunk_width(n)
    k = (size + width - 1) // width
    rng = random.Random(20261011)
    bisect = fractran_index.bisect_left
    mapping_queries = 0

    def count_bisections(keys: tuple[int, ...], value: int) -> int:
        nonlocal mapping_queries
        mapping_queries += len(keys) > 256
        return bisect(keys, value)

    monkeypatch.setattr(fractran_index, "bisect_left", count_bisections)
    tables = (
        [format(value, f"0{size}b") for value in range(1 << size)]
        if n <= 3
        else ["0" * size, "1" * size, "".join(rng.choices("01", k=size))]
    )
    for table in tables:
        template = mapped_chunk_template(table)
        assert len(template.split()) - 1 == k + n + 256
        rows = (
            range(size)
            if n <= 3
            else sorted({0, width - 1, width, size // 3, size - 1})
        )
        for row in rows:
            mapping_queries = 0
            _run(template, table, row, k, watchers=None)
            assert mapping_queries <= n
            if n == 16 and row == size - 1:
                assert mapping_queries == n
            if n <= 2 or n == 6:
                source = fill_runs(
                    template, TEMPLATE_CHAR, [PAIR] * n, row_bits(row, n)
                )
                state, fractions, _ = _parse(source)
                for _ in range(200 * size + 100):
                    index = _choose(state, fractions)
                    if index is None:
                        break
                    numerator, denominator = fractions[index]
                    state = state * numerator // denominator
                else:
                    pytest.fail("literal mapped chunk program exceeded control budget")
                assert state == 1 + int(table[row])


@pytest.mark.parametrize("step", [1, 3, 11, 99, 1001])
def test_decimal_progression_carries(step: int) -> None:
    assert list(decimal_progression(2049, step)) == [str(i * step) for i in range(2049)]


@pytest.mark.medium
@pytest.mark.parametrize("n", [0, 1, 2])
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
            bits = row_bits(row, n)
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
