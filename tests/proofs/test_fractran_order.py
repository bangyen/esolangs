"""State-dependent order encoding retains the whole permutation channel."""


# ruff: noqa: SLF001

import itertools
from collections import Counter

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _choose, _Machine, _parse
from esolangs.tools.fractran import PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs._fractran_order import decoder, order_template, permutation, reader


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
