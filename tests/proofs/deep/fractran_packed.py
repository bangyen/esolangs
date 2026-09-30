"""Why FRACTRAN's generator packs blocks, and what that cost and bought.

Run:  just proofs   (or python tests/proofs/deep/fractran_packed.py)

``docs/proofs/fractran.md`` proves an address budget: live fractions have
pairwise distinct guards, so ``m`` of them cost ``(1 + o(1)) m log m``
characters, and the ``k`` primes a text spells cost ``(1 + o(1)) k log10 k``.
Any program that gives each of ``T`` rows its own guard or its own prime
therefore needs ``Omega(T log T)``.  That was read as a wall for the
language.  It is not one -- a program need not address rows -- and the
generator that used to hit it is kept here, as ``row_addressed``, because the
comparison is the evidence.

The legacy builder stops the tree ``v`` levels early, at ``T / w`` blocks of
``w = 2**v`` entries, and loads each block as a single exponent: ``w`` bits of
table for ``w log10 2`` characters, since this port parses ``p^e``.  One
fixed decoder shifts that exponent right by the offset -- the low ``v`` input
bits, in unary -- and answers with the parity of what is left.

What it costs is the clock, and that is the real content of the wall: the
block sits in an exponent, so a run traverses ``O(2**w)`` of it.  Hence
``w <= n / 2``, which keeps a run under ``2.5 * sqrt(T)`` steps while leaving
the text linear -- ``2**v = Omega(n)`` is all linearity asks.  Both halves
are measured below, against the tree that pays ``Theta(T log T)`` characters
to answer in ``2n + 1`` steps.
"""

from __future__ import annotations

import random

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import PAIR, _packed, _plain, _plan, _primes
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    constant_span_test,
    fill_runs,
)

#: Cost band; see ``__main__.py``.  Cheap because the legacy width keeps a
#: run short: the size claim is a text measurement, and the rows it executes
#: are the correctness claim, which no spot check would make.
BAND = "ci"
COST = 4.0


def legacy_packed(truth_table: str) -> str:
    """Return the pre-indexed construction, preserving its measured tradeoff."""
    n = len(truth_table).bit_length() - 1
    packed = _packed(truth_table, n)
    if n <= 4:
        plain = _plain(truth_table, n)
        return plain if len(plain) <= len(packed) else packed
    return packed


def row_addressed(truth_table: str) -> str:
    """Return the tree this generator used to be: one prime a row.

    Kept because the budget is proved about *this* shape and attained by it,
    so the lemmas in ``tests/proofs/test_fractran_bound.py`` need a program
    that addresses rows, and the size comparison needs the other end of the
    trade.  Same contract, and ``2n + 1`` steps a run.
    """
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
    """Run every row; return the worst step count and widest value.

    The only claim that needs every row is correctness, and it is the one
    claim a spot check would not make.
    """
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
    bases: set[int] = set()
    for token in template.split():
        for side in token.split("/"):
            for factor in side.split("*"):
                bases.add(int(factor.split("^")[0]))
    return bases


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
                steps, bits = rows(legacy_packed(table), table)
                tree_steps, _bits = rows(row_addressed(table), table)
            except AssertionError as error:
                failures.append(f"n={n} answered wrongly: {error}")
                continue
            checked += 2 << n
            worst, widest = max(worst, steps), max(widest, bits)
            if tree_steps > 2 * n + 1:
                failures.append(f"n={n} tree ran {tree_steps} > 2n+1 steps")
        print(
            f"  n={n:>2} plan={_plan(n)}  "
            f"rows={5 << n:>5} ok  steps<={worst:>4}  value<={widest:>5} bits"
        )
    return checked


def _check_sizes(failures: list[str]) -> None:
    """Characters an entry: bounded for the legacy builder, not for a tree."""
    print(
        f"\n  {'n':>3} {'T':>6} {'w':>3} {'packed':>8} {'/T':>6} "
        f"{'tree':>8} {'/T':>6} {'ratio':>6} {'m':>6} {'k':>6}"
    )
    worst_packed, least_tree = 0.0, 1e9
    for n in range(4, 15):
        table = "".join(random.choice("01") for _ in range(1 << n))
        template, tree_text = legacy_packed(table), row_addressed(table)
        size, tree = len(template), len(tree_text)
        per, tree_per = size / (1 << n), tree / (1 << n)
        fractions, primes = len(template.split()) - 1, len(spelled(template))
        if n >= 8:
            worst_packed, least_tree = max(worst_packed, per), min(least_tree, tree_per)
            # Not a counterexample to the address budget: it pays the budget,
            # for far fewer addresses than there are rows.
            if max(fractions, primes) >= 1 << n:
                failures.append(f"n={n} addressed {fractions} of {1 << n} rows")
        print(
            f"  {n:>3} {1 << n:>6} {1 << _plan(n)[0]:>3} {size:>8} "
            f"{per:>6.2f} {tree:>8} {tree_per:>6.2f} {tree / size:>6.2f} "
            f"{fractions:>6} {primes:>6}"
        )
    if worst_packed > 12.0:
        failures.append(f"packed size reached {worst_packed:.2f} characters an entry")
    if least_tree < worst_packed:
        failures.append("the tree was not beaten at every arity from eight up")


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
    print("  the legacy builder is linear, and answers every row it was given")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
