"""Shared block thresholds: linear text and O(n) fraction firings."""

from __future__ import annotations

import random

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import (
    PAIR,
    _Block,
    _Leaf,
    _Node,
    _power,
    _primes,
    _start,
    _tree,
    fractran,
)
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.proofs.deep.fractran_packed import rows

BAND = "by-hand"
COST = 5.0


def threshold(table: str) -> str:
    """Return a template with one threshold dictionary per distinct block."""
    n = len(table).bit_length() - 1
    v = max(0, (max(1, n // 2)).bit_length() - 1)
    nodes = _tree(table, n, v, 0)
    chunks = list(dict.fromkeys(e.chunk for e in nodes if isinstance(e, _Block)))
    primes = _primes(2 + n + len(nodes) + len(chunks))
    count = primes[1]
    inputs, states = primes[2 : 2 + n], primes[2 + n : 2 + n + len(nodes)]
    patterns = dict(zip(chunks, primes[2 + n + len(nodes) :], strict=True))
    routing, dispatch = [], []
    for index, entry in enumerate(nodes):
        state = states[index]
        if isinstance(entry, _Node):
            routing.extend(
                [
                    f"{states[entry.one]}/{state * inputs[entry.depth]}",
                    f"{states[entry.zero]}/{state}",
                ]
            )
        elif isinstance(entry, _Leaf):
            dispatch.append(f"{2 if entry.answer == '1' else 1}/{state}")
        else:
            assert isinstance(entry, _Block)
            routing.append(f"{patterns[entry.chunk]}/{state}")
    for chunk, state in patterns.items():
        for offset in reversed(range(1 << v)):
            bit = (chunk >> offset) & 1
            if offset and bit == ((chunk >> (offset - 1)) & 1):
                continue
            guard = f"{state}*{_power(count, offset)}" if offset else str(state)
            dispatch.append(f"{2 if bit else 1}/{guard}")
    offsets = [
        f"{_power(count, 1 << (n - 1 - level))}/{inputs[level]}"
        for level in range(n - v, n)
    ]
    cleanup = [f"1/{p}" for p in [*inputs, count]]
    return " ".join([_start(states, inputs), *routing, *offsets, *dispatch, *cleanup])


def sample(template: str, table: str, indices: list[int]) -> tuple[int, int]:
    """Execute selected rows; return maximum firings and guard inspections."""
    n = len(table).bit_length() - 1
    worst = inspections = 0
    for row in indices:
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        code = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
        value, fractions, _ = _parse(code)
        steps = probes = 0
        while (index := _choose(value, fractions)) is not None:
            probes += index + 1
            numerator, denominator = fractions[index]
            value = value * numerator // denominator
            steps += 1
            assert steps <= 100_000, (n, row, steps)
        probes += len(fractions)
        assert value == (2 if table[row] == "1" else 1), (n, row, value)
        worst, inspections = max(worst, steps), max(inspections, probes)
    return worst, inspections


def main() -> int:
    """Execute small tables and measure rendered sizes at wider arities."""
    rng = random.Random(20260930)
    checked = 0
    for n in range(1, 7):
        length = 1 << n
        tables = (
            [format(t, f"0{length}b") for t in range(1 << length)]
            if n <= 3
            else [
                "0" * length,
                "1" * length,
                "".join(str(i.bit_count() % 2) for i in range(length)),
            ]
            + ["".join(rng.choice("01") for _ in range(length)) for _ in range(12)]
        )
        size = baseline = steps = 0
        for table in tables:
            code = threshold(table)
            worst, _ = rows(code, table)
            size += len(code)
            baseline += len(fractran(table))
            assert worst <= 3 * n + 2, (n, table, worst)
            steps = max(steps, worst)
            checked += length
        print(n, len(tables), size, baseline, steps)
    print("rows", checked)
    for n in range(8, 17, 2):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        code = threshold(table)
        indices = [0, 1, len(table) // 2, len(table) - 1]
        steps, probes = sample(code, table, indices)
        assert steps <= 3 * n + 2, (n, steps)
        sample(fractran(table), table, indices)
        print(
            "size",
            n,
            len(code),
            len(fractran(table)),
            "sample steps/scans",
            steps,
            probes,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
