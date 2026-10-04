"""Forþ state and generated programs against independently derived semantics."""

import random

import pytest

from esolangs.interpreters.io import IO
from esolangs.interpreters.stack_based.forth import _advance, _Frame, _Machine
from esolangs.tools.forth import forth
from esolangs.vm import run_until_halt_or_ancestor, run_until_halt_or_cycle
from tests.interpreters.forth_cases import finite_cases
from tests.interpreters.forth_observer import check


@pytest.mark.parametrize("shard", range(8))
def test_finite_state(shard):
    for source, text in finite_cases()[shard::8]:
        check(source, text)


@pytest.mark.parametrize(
    "left",
    [-2147483648, -2147483647, -65537, -1, 0, 1, 2, 15, 65537, 2147483646, 2147483647],
)
def test_integer_transitions(left):
    for right in [
        -2147483648,
        -2147483647,
        -65537,
        -1,
        0,
        1,
        2,
        15,
        65537,
        2147483646,
        2147483647,
    ]:
        for op in "+-*/%v":
            state = _advance(((left, right), {}, (_Frame(op),), False))
            if op in "/%" and right == 0:
                assert state == ((), {}, (), True)
                continue
            if op == "v":
                expected = (right, left)
            else:
                q = abs(left) // abs(right) if right else 0
                if (left < 0) != (right < 0):
                    q = -q
                value = {
                    "+": left + right,
                    "-": left - right,
                    "*": left * right,
                    "/": q,
                    "%": left - q * right,
                }[op]
                value &= 0xFFFFFFFF
                expected = (value if value < 0x80000000 else value - 0x100000000,)
            assert state == (expected, {}, (_Frame(op, 1),), False)


@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_small_generated_state(n, shard):
    for value in range(shard, 2 ** (2**n), 16 if n == 3 else 1):
        table = format(value, f"0{2**n}b")
        source = forth(table)
        for row, answer in enumerate(table):
            result = check(source, "\n".join(format(row, f"0{n}b")) + "\n")
            assert result["output"] == answer
            assert result["reads"] == n


class Cursorless(IO):
    def __init__(self, lines):
        super().__init__()
        self.lines = iter(lines)
        self.successful = 0

    def _read(self, _prompt):
        try:
            value = next(self.lines)
        except StopIteration:
            raise EOFError from None
        self.successful += 1
        return value

    def _write(self, value):
        pass


@pytest.mark.parametrize(
    ("source", "driver"),
    [("1[,]", run_until_halt_or_cycle), ("1{,1;}1;", run_until_halt_or_ancestor)],
)
def test_cursorless_reads_reach_eof(source, driver):
    io = Cursorless([""] * 7 + ["0"])
    vm = _Machine(source, io)
    with pytest.raises(EOFError):
        driver(vm, limit=100)
    assert io.successful == 8
    assert vm.snapshot()[-1] == 8


@pytest.mark.parametrize(
    ("source", "driver"),
    [("1[]", run_until_halt_or_cycle), ("1{1;}1;", run_until_halt_or_ancestor)],
)
def test_no_input_recurrence(source, driver):
    assert driver(_Machine(source, Cursorless([])), limit=100) is False


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "family", "shard", "shards"),
    [
        (n, family, shard, shards)
        for n in range(4, 11)
        for family in ("zero", "one", "parity", "sparse", "dense", "random")
        for shards in (128 if n == 10 and family == "random" else 16,)
        for shard in range(shards)
    ],
)
def test_wide_generated_state(n, family, shard, shards):
    rng = random.Random(1000 + n)
    tables = {
        "zero": "0" * (2**n),
        "one": "1" * (2**n),
        "parity": "".join(str(i.bit_count() % 2) for i in range(2**n)),
        "sparse": "".join(
            "1" if i in (0, 2**n - 1, 2 ** (n - 1)) else "0" for i in range(2**n)
        ),
        "dense": "".join(
            "0" if i in (0, 2**n - 1, 2 ** (n - 1)) else "1" for i in range(2**n)
        ),
        "random": "".join(rng.choice("01") for _ in range(2**n)),
    }
    table = tables[family]
    source = forth(table)
    for row in range(shard, 2**n, shards):
        result = check(source, "\n".join(format(row, f"0{n}b")) + "\n")
        assert result["output"] == table[row]
        assert result["reads"] == n
