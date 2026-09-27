"""The construction that refutes FRACTRAN's `Omega(T log T)` size claim.

Run:  just proofs   (or python tests/proofs/deep/fractran_packed.py)

``docs/proofs/fractran.md`` proves an address budget: live fractions have
pairwise distinct guards, so ``m`` of them cost ``(1 + o(1)) m log m``
characters, and the ``k`` primes a text spells cost ``(1 + o(1)) k log10 k``.
Any program that gives each of ``T`` rows its own guard or its own prime
therefore needs ``Omega(T log T)``.  The roadmap read that as a wall for the
language.  It is not one, and this module is the counterexample: a program
does not have to address rows.

A block-packed program stops the tree ``v`` levels early, at ``T / w`` blocks
of ``w = 2**v`` entries.  Each leaf loads its whole block as a single exponent
of one prime -- ``w`` bits for ``w * log10 2`` characters, since this port
parses ``p^e`` -- and one shared, constant-size decoder shifts that exponent
right by the block offset and answers with its parity.  The offset is the low
``v`` bits of the row, accumulated in unary by ``v`` fractions that sit at the
top of the list.  With ``w = Theta(log T)`` the tree addresses
``Theta(T / log T)`` blocks, so the budget it pays is ``Theta(T)``, the block
literals cost ``0.302 * T``, and the decoder is a constant.

What it costs is the clock, and that is the real content of the wall: the
block is held in an exponent, so the value carries ``Theta(2**w)`` bits and
the shift traverses them.  The shipped tree runs ``2n + 1`` steps on a value
of ``O(log T)`` bits; this runs ``Theta(T)`` steps on a value of
``Theta(T)`` bits.  Both ends are executed here.  Neither is linear on all
four audit axes at once, and which one ships is a curator's trade.
"""

from __future__ import annotations

import random
from math import ceil, log2

from esolangs.interpreters.other.fractran import _choose, _parse
from esolangs.tools.fractran import PAIR, _primes, fractran
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs

#: Cost band; see ``__main__.py``.  Cheap because the widths a run can afford
#: are small ones: the size claim is a text measurement, and the rows it
#: executes are the correctness claim, which no spot check would make.
BAND = "ci"
COST = 4.0

#: How many control primes the decoder needs, before the inputs and states.
_CONTROL = 12


def width_exponent(n: int) -> int:
    """The ``v`` that makes the construction linear: ``2**v >= n``.

    The tree addresses ``T / 2**v`` blocks and so pays
    ``Theta((T / 2**v) * log(T / 2**v))`` characters.  That is ``O(T)``
    exactly when ``2**v`` grows like ``log T = n``, which is the whole design.
    """
    return min(n, max(1, ceil(log2(n))))


def packed(truth_table: str, v: int) -> str:
    """Return a block-packed FRACTRAN template for ``truth_table``.

    Same contract as :func:`esolangs.tools.fractran.fractran`: each run of
    :data:`TEMPLATE_CHAR` is one input's exponent, filled with :data:`PAIR`,
    and the instantiated program halts on ``2`` for a one and ``1`` for a zero.
    """
    n = len(truth_table).bit_length() - 1
    high = n - v
    blocks = len(truth_table) >> v

    pool = _primes(_CONTROL + n + 2 * blocks)
    carry, work, count = pool[1:4]
    ready, read, halve, shift, back, drop, move, cycle = pool[4:_CONTROL]
    inputs = pool[_CONTROL : _CONTROL + n]
    states = pool[_CONTROL + n :]

    # The offset, in unary, at the top of the list: nothing else guards on a
    # low input prime, so these fire first and to exhaustion.
    fractions = [f"{count}^{1 << (v - 1 - r)}/{inputs[high + r]}" for r in range(v)]
    tree, root = _tree(truth_table, v, high, inputs, states, ready, carry)
    fractions += tree
    fractions += [
        # One shift left to do?  Spend a unit of the offset counter.
        f"{shift}/{ready * count}",
        # Halve: two of the carry prime make one of the work prime.
        f"{halve}*{work}/{shift}*{carry}^2",
        f"{shift}/{halve}",
        f"{back}/{shift}",
        # The bit shifted out, if there was one, is not the answer.
        f"{move}/{back}*{carry}",
        f"{move}/{back}",
        # Move the halved value back, so the next shift reads it.
        f"{cycle}*{carry}/{move}*{work}",
        f"{move}/{cycle}",
        f"{ready}/{move}",
        # The counter is spent: the answer is the low bit of what is left.
        f"{read}/{ready}",
        f"{drop}/{read}*{carry}^2",
        f"{read}/{drop}",
        f"2/{read}*{carry}",
        f"1/{read}",
    ]
    # A folded-over input prime is unread, so it is cleared last of all.
    fractions += [f"1/{prime}" for prime in inputs]
    start = "*".join(
        [str(states[root])] + [f"{prime}^{TEMPLATE_CHAR}" for prime in inputs]
    )
    return " ".join([start, *fractions])


def _tree(
    truth_table: str,
    v: int,
    high: int,
    inputs: list[int],
    states: list[int],
    ready: int,
    carry: int,
) -> tuple[list[str], int]:
    """Return the block tree's fractions, and the root's state index."""
    # Post-order, root last, so a child's state prime is fixed before its
    # parent names it -- the shipped generator's own shape.
    order: list[tuple[int, ...]] = []

    def build(depth: int, lo: int, hi: int) -> int:
        if depth == high:
            order.append((-1, lo >> v))
        else:
            mid = (lo + hi) // 2
            zero = build(depth + 1, lo, mid)
            one = build(depth + 1, mid, hi)
            order.append((depth, zero, one))
        return len(order) - 1

    build(0, 0, len(truth_table))
    fractions: list[str] = []
    for index, entry in enumerate(order):
        if entry[0] == -1:
            block = entry[1]
            chunk = sum(
                int(truth_table[(block << v) + offset]) << offset
                for offset in range(1 << v)
            )
            load = f"{carry}^{chunk}*{ready}" if chunk else f"{ready}"
            fractions.append(f"{load}/{states[index]}")
        else:
            depth, zero, one = entry
            fractions.append(f"{states[one]}/{states[index] * inputs[depth]}")
            fractions.append(f"{states[zero]}/{states[index]}")
    return fractions, len(order) - 1


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


def _check_rows(failures: list[str]) -> int:
    """Every row of every table, at every width a run can afford."""
    checked = 0
    for n in range(2, 9):
        # Two tables where the runs are cheap; the widest width at the widest
        # arity is a thousand steps a row, and one table of those will do.
        for trial in range(1 if n > 6 else 2):
            table = "".join(random.choice("01") for _ in range(1 << n))
            for v in range(1, min(n, 3) + 1):
                try:
                    worst, widest = rows(packed(table, v), table)
                except AssertionError as error:
                    failures.append(f"n={n} v={v} answered wrongly: {error}")
                    continue
                checked += 1 << n
                if trial:
                    continue
                print(
                    f"  n={n:>2} w={1 << v:>2}  rows={1 << n:>4} ok  "
                    f"steps<={worst:>5}  value<={widest:>6} bits"
                )
    return checked


def _check_sizes(failures: list[str]) -> None:
    """The size table: the packed constant is bounded, the tree's is not."""
    print(
        f"\n  {'n':>3} {'T':>6} {'w':>3} {'packed':>8} {'/T':>6} "
        f"{'tree':>8} {'/T':>6} {'ratio':>6} {'m':>6} {'k':>6}"
    )
    worst_packed, least_tree = 0.0, 1e9
    for n in range(4, 15):
        table = "".join(random.choice("01") for _ in range(1 << n))
        v = width_exponent(n)
        template = packed(table, v)
        size, tree = len(template), len(fractran(table))
        per, tree_per = size / (1 << n), tree / (1 << n)
        fractions, primes = len(template.split()) - 1, len(spelled(template))
        if n >= 9:
            worst_packed, least_tree = max(worst_packed, per), min(least_tree, tree_per)
            # Not a counterexample to the address budget: it pays the budget,
            # for far fewer addresses than there are rows.
            if max(fractions, primes) >= 1 << n:
                failures.append(f"n={n} addressed {fractions} of {1 << n} rows")
        print(
            f"  {n:>3} {1 << n:>6} {1 << v:>3} {size:>8} {per:>6.2f} "
            f"{tree:>8} {tree_per:>6.2f} {tree / size:>6.2f} "
            f"{fractions:>6} {primes:>6}"
        )
    # The packed characters-per-entry stays inside a band while the tree's
    # climbs past it: the tree's log is its own, not the language's.
    if worst_packed > 4.0:
        failures.append(f"packed size reached {worst_packed:.2f} characters an entry")
    if least_tree < worst_packed:
        failures.append("the tree was not beaten at every arity from nine up")


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
    print("  a block-packed FRACTRAN program is linear in the table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
