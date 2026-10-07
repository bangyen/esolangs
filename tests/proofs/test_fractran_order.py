"""State-dependent order encoding retains the whole permutation channel."""


# ruff: noqa: SLF001

import itertools
import random
from collections import Counter

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse
from esolangs.tools.fractran import PAIR, _primes
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs._fractran_order import (
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
