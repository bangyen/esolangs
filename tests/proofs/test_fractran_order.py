"""State-dependent order encoding retains the whole permutation channel."""


# ruff: noqa: SLF001

import itertools
import random
from collections import Counter

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse
from esolangs.interpreters.other.fractran import index as fractran_index
from esolangs.tools.fractran import PAIR, _primes, fractran
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs._fractran_order import (
    _Available,
    _linear_primes,
    capacity,
    decoder,
    digit_order,
    order_template,
    permutation,
    reader,
    stream_template,
)


@pytest.mark.medium
def test_order_reader_recovers_every_permutation() -> None:
    for k in (3, 4):
        features = (37, 41, 43, 47)[:k]
        outputs = set()
        lengths = set()
        for order in itertools.permutations(range(k)):
            source = " ".join(
                ["3*" + "*".join(map(str, features)), *reader(order, features)]
            )
            lengths.add(len(source))
            value, fractions, _offsets = _parse(source)
            for _ in range(10000):
                index = _choose(value, fractions)
                if index is None:
                    break
                numerator, denominator = fractions[index]
                value = value * numerator // denominator
            else:
                pytest.fail("order reader exceeded its control budget")
            encoded = 0
            for i in order:
                encoded = (k + 1) * encoded + i + 1
            assert value == 7**encoded
            outputs.add(encoded)
        assert len(outputs) == (6 if k == 3 else 24)
        assert lengths == ({119} if k == 3 else {134})


def test_fixed_counter_decoder_returns_factorial_rank_bits() -> None:
    assembly, rules = decoder()
    assert len(assembly.code) == 259
    assert len(rules) == 736
    for k in (3, 4):
        for rank, order in enumerate(itertools.permutations(range(k))):
            assert permutation(rank, k) == order
            encoded = 0
            for i in order:
                encoded = (k + 1) * encoded + i + 1
            for row in range(2 if k == 3 else 4):
                values, _steps = assembly.run(
                    {"E": encoded, "B": k + 1, "F": 1, "two": 2, "row": row}
                )
                assert values.get("answer", 0) == ((rank >> row) & 1)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "k"), [(1, 3), pytest.param(2, 4, marks=pytest.mark.slow)]
)
def test_order_alone_realizes_every_table(n: int, k: int) -> None:
    multiset = None
    start = None
    lengths = set()
    for table_number in range(1 << (1 << n)):
        table = format(table_number, f"0{1 << n}b")
        template = order_template(table, k)
        tokens = template.split()
        if multiset is None:
            multiset = Counter(tokens[1:])
            start = tokens[0]
        assert Counter(tokens[1:]) == multiset
        assert tokens[0] == start
        lengths.add(len(template))
        for row in range(1 << n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
            io = ScriptedIO("")
            machine = _Machine(source, io)
            assert machine._index is not None
            for _ in range(50000):
                if machine.halted:
                    break
                machine.step()
            else:
                pytest.fail("fixed order decoder exceeded its control budget")
            assert io.getvalue().strip() == str(1 + int(table[row]))
    assert len(lengths) == 1


def test_independent_lehmer_capacity_and_prime_bound() -> None:
    for k in range(1, 513):
        assert capacity(k) == sum(m.bit_length() - 1 for m in range(1, k + 1))
    for count in (40, 64, 128, 512):
        assert _linear_primes(count) == _primes(count)
    with pytest.raises(ValueError, match="not enough"):
        digit_order("0000", 3)


def test_rank_deletion_updates_each_fenwick_interval_once_per_symbol() -> None:
    class Cells(list[int]):
        def __init__(self, values: list[int]) -> None:
            super().__init__(values)
            self.writes = [0] * len(values)
            self.flips = [0] * len(values)

        def __setitem__(self, index: int, value: int) -> None:
            self.writes[index] += 1
            self.flips[index] += (self[index] ^ value).bit_count()
            super().__setitem__(index, value)

    for k in (1, 3, 64, 255, 256, 1024, 4096):
        for mode in ("first", "last", "seeded"):
            available = _Available(k)
            cells = Cells(available.tree)
            available.tree = cells
            rng = random.Random(20261007)
            order = []
            for remaining in range(k, 0, -1):
                rank = (
                    0
                    if mode == "first"
                    else remaining - 1
                    if mode == "last"
                    else rng.randrange(remaining)
                )
                order.append(available.pop(rank))
            assert sorted(order) == list(range(k))
            assert cells.writes == [0, *(i & -i for i in range(1, k + 1))]
            assert cells.flips == [0, *(2 * (i & -i) - 1 for i in range(1, k + 1))]
            assert cells == [0] * (k + 1)


def _execute_stream(
    template: str, table: str, rows: range | tuple[int, ...], k: int
) -> int:
    n = len(table).bit_length() - 1
    worst = 0
    for row in rows:
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
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
@pytest.mark.parametrize(
    ("n", "k", "length", "worst"),
    [
        (1, 3, 4065, 89),
        (2, 4, 4175, 254),
        pytest.param(3, 6, 4379, 265, marks=pytest.mark.slow),
    ],
)
def test_stream_order_realizes_every_table(
    n: int, k: int, length: int, worst: int
) -> None:
    multiset = None
    start = None
    measured = 0
    for table_number in range(1 << (1 << n)):
        table = format(table_number, f"0{1 << n}b")
        template = stream_template(table, k)
        tokens = template.split()
        if multiset is None:
            multiset = Counter(tokens[1:])
            start = tokens[0]
        assert Counter(tokens[1:]) == multiset
        assert tokens[0] == start
        assert len(template) == length
        assert len(tokens) - 1 == 7 * k + n + 258
        measured = max(measured, _execute_stream(template, table, range(1 << n), k))
    assert measured == worst


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
    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
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
        (4, 9, 4682, 113, (500, 4511, 3515), (5, 11, 15)),
        (6, 23, 6156, 456, (650, 19909, 9206), (7, 16, 28)),
        (8, 63, 10354, 1395, (1120, 84935, 34090), (9, 21, 45)),
        (10, 182, 23739, 4802, (10767, 1039816, 357107), (11, 26, 66)),
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
def test_stream_prefix_inspections_positive_control() -> None:
    for n, k in ((4, 9), (6, 23), (8, 63), (10, 182)):
        table = "0" * (1 << n)
        position = k // 2
        row = sum(m.bit_length() - 1 for m in range(k - position + 1, k + 1))
        assert row < len(table)
        template = stream_template(table, k)
        source = fill_runs(
            template,
            TEMPLATE_CHAR,
            [PAIR] * n,
            [(row >> (n - 1 - i)) & 1 for i in range(n)],
        )
        io = ScriptedIO("")
        machine = _Machine(source, io)
        ready_probes = steps = 0
        while not machine.halted:
            assert machine._index is not None
            selected, probes = machine._index.choose(machine._factors)
            assert machine._next() == selected
            if (3, 1) in machine._factors:
                ready_probes += probes
            machine.step()
            steps += 1
            assert steps < 200 * k + 100
        assert io.getvalue().strip() == "1"
        assert ready_probes == 2 * position + 3


@pytest.mark.medium
def test_dense_cursor_work_and_sparse_threshold_routing() -> None:
    rng = random.Random(20261007)
    for n in (4, 6, 8, 10):
        size = 1 << n
        table = "".join(str(rng.randrange(2)) for _ in range(size))
        if n < 8:
            continue
        k = 63 if n == 8 else 182
        streamed = stream_template(table, k)
        shipped = fractran(table)
        for row in (0, size // 3, size - 1):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            for template in (streamed, shipped):
                source = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
                io = ScriptedIO("")
                machine = _Machine(source, io)
                assert machine._index is not None
                assert (machine._cursor is not None) == (template == streamed)
                steps = 0
                while not machine.halted:
                    machine.step()
                    steps += 1
                    assert steps < 200 * k + 100
                assert io.getvalue().strip() == str(1 + int(table[row]))
                if machine._cursor is not None:
                    assert machine.inspections == steps - 1
                    assert machine._cursor.factor_updates <= 3 * steps
                    assert machine._cursor.guard_updates <= 4 * (steps + k)


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
