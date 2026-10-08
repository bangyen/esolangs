"""FRACTRAN's shared decision diagram: linear text, a firing a level."""

from __future__ import annotations

import random

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import PAIR, _primes, _tree, fractran
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    constant_span_test,
    fill_runs,
)

#: Cost band; see ``__main__.py``.  Cheap because a run is a firing a level:
#: the size claim is a text measurement, and the rows it executes are the
#: correctness claim, which no spot check would make.
BAND = "ci"
COST = 4.0


def row_addressed(truth_table: str) -> str:
    """Return the tree this generator used to be: one prime a row."""
    n = len(truth_table).bit_length() - 1
    constant = constant_span_test(truth_table)
    nodes: list[tuple[int, int, int]] = []

    def walk(depth: int, lo: int, hi: int) -> int:
        if depth == n or constant(lo, hi):
            nodes.append((-1, int(truth_table[lo]), 0))
        else:
            mid = (lo + hi) // 2
            zero = walk(depth + 1, lo, mid)
            nodes.append((depth, zero, walk(depth + 1, mid, hi)))
        return len(nodes) - 1

    walk(0, 0, len(truth_table))
    primes = _primes(1 + n + len(nodes))
    inputs, states = primes[1 : 1 + n], primes[1 + n :]
    fractions = []
    for index, (depth, first, second) in enumerate(nodes):
        if depth < 0:
            fractions.append(f"{2 if first else 1}/{states[index]}")
            continue
        fractions.append(f"{states[second]}/{states[index] * inputs[depth]}")
        fractions.append(f"{states[first]}/{states[index]}")
    fractions += [f"1/{prime}" for prime in inputs]
    start = "*".join(
        [str(states[-1])] + [f"{prime}^{TEMPLATE_CHAR}" for prime in inputs]
    )
    return " ".join([start, *fractions])


def run(code: str) -> tuple[int, int, int]:
    """Return the halt value, the step count, and the widest value seen."""
    value, fractions, _offsets = _parse(code)
    steps, widest = 0, value.bit_length()
    while (index := _choose(value, fractions)) is not None:
        numerator, denominator = fractions[index]
        value = value * numerator // denominator
        steps += 1
        widest = max(widest, value.bit_length())
    return value, steps, widest


def rows(template: str, truth_table: str) -> tuple[int, int]:
    """Run every row; return the worst step count and widest value."""
    n = len(truth_table).bit_length() - 1
    worst = widest = 0
    for row in range(len(truth_table)):
        bits = [(row >> (n - 1 - index)) & 1 for index in range(n)]
        code = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
        value, steps, bits_seen = run(code)
        want = 2 if truth_table[row] == "1" else 1
        assert value == want, (truth_table[:16], row, value, want)
        worst, widest = max(worst, steps), max(widest, bits_seen)
    return worst, widest


def spelled(template: str) -> set[int]:
    """The primes the text names -- the set the address budget prices."""
    primes: set[int] = set()
    for token in template.split():
        for side in token.split("/"):
            for factor in side.split("*"):
                base, p = int(factor.split("^")[0]), 2
                while p * p <= base:
                    while base % p == 0:
                        primes.add(p)
                        base //= p
                    p += 1
                if base > 1:
                    primes.add(base)
    return primes


def cap(n: int) -> int:
    """Distinct subtables a depth can hold, summed: ``O(T / log T)`` states."""
    return sum(min(1 << d, 1 << (1 << (n - d))) for d in range(n + 1))


def _tables(n: int) -> list[str]:
    """One random table, and the shapes a random one never covers."""
    half = 1 << (n - 1) if n else 1
    return [
        "".join(random.choice("01") for _ in range(1 << n)),
        "0" * (1 << n),
        "1" * (1 << n),
        "".join(str(bin(row).count("1") & 1) for row in range(1 << n)),
        "0" * half + "1" * ((1 << n) - half),
    ]


def _check_rows(failures: list[str]) -> int:
    """Every row of every table, against both constructions."""
    checked = 0
    for n in range(1, 10):
        worst = widest = 0
        for table in _tables(n):
            try:
                steps, bits = rows(fractran(table), table)
                tree_steps, _bits = rows(row_addressed(table), table)
            except AssertionError as error:
                failures.append(f"n={n} answered wrongly: {error}")
                continue
            checked += 2 << n
            worst, widest = max(worst, steps), max(widest, bits)
            if steps > n + 1:
                failures.append(f"n={n} fired {steps} > n + 1 fractions")
            if tree_steps > 2 * n + 1:
                failures.append(f"n={n} tree ran {tree_steps} > 2n+1 steps")
        print(
            f"  n={n:>2} rows={5 << n:>5} ok  "
            f"steps<={worst:>3}  value<={widest:>4} bits"
        )
    return checked


def _check_sizes(failures: list[str]) -> None:
    """Characters an entry: falling for the diagram, climbing for the tree."""
    print(
        f"\n  {'n':>3} {'T':>6} {'shared':>8} {'/T':>6} {'tree':>8} {'/T':>6} "
        f"{'states':>7} {'cap':>7}"
    )
    worst = 0.0
    for n in range(4, 15):
        table = "".join(random.choice("01") for _ in range(1 << n))
        template, tree_text = fractran(table), row_addressed(table)
        size, tree = len(template), len(tree_text)
        states = len(_tree(table, n))
        if states > cap(n):
            failures.append(f"n={n} built {states} states over the cap {cap(n)}")
        if n >= 8:
            worst = max(worst, size / (1 << n))
            if tree <= size:
                failures.append(f"n={n} the row-addressed tree was not beaten")
        print(
            f"  {n:>3} {1 << n:>6} {size:>8} {size / (1 << n):>6.2f} "
            f"{tree:>8} {tree / (1 << n):>6.2f} {states:>7} {cap(n):>7}"
        )
    if worst > 8.0:
        failures.append(f"shared size reached {worst:.2f} characters an entry")


def main() -> int:
    random.seed(20260927)
    failures: list[str] = []
    checked = _check_rows(failures)
    _check_sizes(failures)
    print(f"\n  rows executed against their table   : {checked}")
    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        return 1
    print("  the shared diagram is linear, and answers every row it was given")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
