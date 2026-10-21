"""State-dependent order encoding retains the whole permutation channel."""


# ruff: noqa: SLF001

import random

import pytest

from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.languages.fractran.generator import PAIR, fractran
from esolangs.languages.fractran.interpreter import _Machine
from esolangs.languages.fractran.interpreter import index as fractran_index
from esolangs.languages.fractran.tests.proofs._fractran_order import (
    capacity,
    stream_template,
)
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import row_bits


def _execute_stream(
    template: str, table: str, rows: range | tuple[int, ...], k: int
) -> int:
    n = len(table).bit_length() - 1
    worst = 0
    for row in rows:
        bits = row_bits(row, n)
        source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
        io = ScriptedIO("")
        machine = _Machine(source, io)
        for _steps in range(200 * k + 100):
            if machine.halted:
                break
            machine.step()
        else:
            pytest.fail("streaming decoder exceeded its control budget")
        assert io.getvalue().strip() == str(1 + int(table[row]))
        # The final VM transition prints the answer without firing a fraction.
        worst = max(worst, _steps - 1)
    return worst


@pytest.mark.medium
def test_stream_order_wider_queries() -> None:
    rng = random.Random(20261007)
    for n in (4, 6, 8, 10):
        size = 1 << n
        k = (4 * size + n - 1) // n
        table = "".join(str(rng.randrange(2)) for _ in range(size))
        assert capacity(k) >= size
        template = stream_template(table, k)
        _execute_stream(template, table, (0, size // 3, size - 1), k)


def test_stream_order_constant_tables() -> None:
    for table in ("0", "1"):
        _execute_stream(stream_template(table, 2), table, range(1), 2)


def _evaluation_cost(
    template: str, table: str, row: int
) -> tuple[int, int, int | None]:
    n = len(table).bit_length() - 1
    bits = row_bits(row, n)
    source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
    io = ScriptedIO("")
    machine = _Machine(source, io)
    steps = visits = reference_probes = 0
    while not machine.halted:
        visits += len(machine._factors)
        if machine._index is None:
            selected = machine._next()
            reference_probes += (
                len(machine.fractions) if selected is None else selected + 1
            )
        else:
            selected, probes = machine._index.choose(machine._factors)
            assert machine._next() == selected
            reference_probes += probes
        machine.step()
        steps += 1
        assert steps <= 50000
    assert io.getvalue().strip() == str(1 + int(table[row]))
    return (
        steps - 1,
        reference_probes,
        visits if machine._index is not None else None,
    )


@pytest.mark.medium
def test_stream_and_shipped_evaluation_costs() -> None:
    rng = random.Random(20261007)
    controls = (
        (4, 9, 4682, 103, (500, 4511, 3515), (5, 11, 15)),
        (6, 23, 6156, 431, (650, 19909, 9206), (7, 16, 28)),
        (8, 63, 10354, 1343, (1120, 84935, 34090), (9, 21, 45)),
        (10, 182, 23739, 4733, (10767, 1039816, 357107), (11, 26, 66)),
    )
    for n, k, stream_length, shipped_length, stream_max, shipped_max in controls:
        size = 1 << n
        table = "".join(str(rng.randrange(2)) for _ in range(size))
        assert capacity(k - 1) < size <= capacity(k)
        stream = stream_template(table, k)
        shipped = fractran(table)
        assert (len(stream), len(shipped)) == (stream_length, shipped_length)
        for template, expected in ((stream, stream_max), (shipped, shipped_max)):
            costs = [
                _evaluation_cost(template, table, row)
                for row in (0, size // 3, size - 1)
            ]
            measured = tuple(
                max(values)
                for values in zip(*costs, strict=True)
                if values[0] is not None
            )
            assert measured == tuple(value for value in expected if value is not None)
            if template == stream:
                assert all(cost[2] >= k * (k + 1) // 2 for cost in costs)


@pytest.mark.medium
@pytest.mark.parametrize(
    "arity", [8, *(pytest.param(n, marks=pytest.mark.slow) for n in (10, 12, 14, 16))]
)
def test_stream_loading_sieve_and_wider_answers(
    monkeypatch: pytest.MonkeyPatch,
    arity: int,
) -> None:
    original = fractran_index._least_primes
    limits = []

    def record(limit: int) -> list[int]:
        limits.append(limit)
        return original(limit)

    monkeypatch.setattr(fractran_index, "_least_primes", record)
    rng = random.Random(20261007)
    for n, k, base in (
        (8, 63, 577),
        (10, 182, 1433),
        (12, 568, 4523),
        (14, 1842, 16273),
        (16, 6143, 61561),
    ):
        size = 1 << n
        table = "".join(str(rng.randrange(2)) for _ in range(size))
        if n != arity:
            continue
        assert capacity(k - 1) < size <= capacity(k)
        template = stream_template(table, k)
        source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, [1] * n)
        io = ScriptedIO("")
        machine = _Machine(source, io)
        assert machine._index is not None
        assert machine._cursor is not None
        assert limits[-1] == base <= 8 * size
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
            assert steps < 200 * k + 100
        assert io.getvalue().strip() == str(1 + int(table[-1]))
        break
    assert len(limits) == 1
