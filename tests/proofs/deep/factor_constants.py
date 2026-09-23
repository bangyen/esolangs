"""Machine checks behind Factor's explicit constants.

Run:  just proofs   (or python tests/proofs/deep/factor_constants.py)

``docs/proofs/factor.tex`` makes the upper bound explicit in two pieces.  The
tree lemma is exact arithmetic, ``C <= 35T/2 + 55n + 25`` for ``n >= 2``, with
parity attaining it.  The prime walk rests on a computed class-gap constant:
for ``x <= X_GAP`` every class ``a = 1..8`` mod 11 has a prime in
``(x, x + GAP_C * ln(max(x, 37))**2]``.  ``scripts/factor_class_gaps.c``
measured the ratio through ``10**11`` (8.6184, class 2 at 4,160,719); this
module re-sieves a prefix in Python, which holds that maximum, and checks the
window that lets ``X_GAP`` stop ``10**4`` short of the sieved end.

L1  the tree bound, exhaustive at n = 2, 3, sampled above, parity exact.
L2  the class-gap constant on a Python-sieved prefix, and the end window.
L3  the resulting digit ceiling holds for parity, and so does its ``Q``.
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.factor_primes import prime_segments
from esolangs.tools.tape import _BF_RESIDUE, brainfuck

#: Cost band; see ``__main__.py``.  The parity encodings to n = 11 and the
#: prefix sieve dominate.
BAND = "by-hand"
COST = 2.0

#: The computed class-gap constant and the range it was verified over.
GAP_C = 8.62
SIEVED = 10**11
X_GAP = SIEVED - 10**4

#: Every instruction class has a prime at or below this, so the walk starts
#: there and the gap bound is stated from it.
FIRST = 37


def tree_bound(n: int) -> float:
    """The identity-order tree's worst length, attained by parity."""
    return 35 * (1 << n) / 2 + 55 * n + 25


def ceiling(n: int) -> tuple[int, int]:
    """``(Q*, digit ceiling)`` at arity ``n``: the walk's fixed point and D."""
    runs = int(tree_bound(n))

    def step(q: float) -> float:
        return FIRST + (runs - 1) * GAP_C * math.log(q) ** 2

    q = float(FIRST)
    for _ in range(200):  # rises to the least fixed point
        q = step(q)
    # Any y with step(y) <= y bounds the walk; certify one above the float.
    y = math.ceil(q) + 1
    assert step(y) <= y <= X_GAP, f"n={n}: {y} is not a certified ceiling"
    return y, math.floor(runs * math.log10(y)) + 1


def parity(n: int) -> str:
    return "".join(str(i.bit_count() % 2) for i in range(2**n))


def walk(code: str) -> tuple[int, int]:
    """The encoder's prime walk: ``(largest prime, decimal digits)``."""
    primes = (p for _lo, _hi, segment in prime_segments(20000) for p in segment)
    largest, log_n, i = 0, 0.0, 0
    while i < len(code):
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        largest = next(p for p in primes if p % 11 == _BF_RESIDUE[code[i]])
        log_n += (j - i) * math.log(largest)
        i = j
    return largest, int(log_n / math.log(10)) + 1


def check_tree() -> list[str]:
    for n in (2, 3):
        for bits in itertools.product("01", repeat=2**n):
            assert len(brainfuck("".join(bits))) <= tree_bound(n)
    rng = random.Random(5)
    for n in range(4, 10):
        for _ in range(60):
            density = rng.random()
            table = "".join("1" if rng.random() < density else "0" for _ in range(2**n))
            assert len(brainfuck(table)) <= tree_bound(n)
    for n in range(2, 12):
        assert len(brainfuck(parity(n))) == tree_bound(n), n
    return ["tree bound holds; parity attains it for n = 2..11"]


def check_gaps(bound: int) -> list[str]:
    last = dict.fromkeys(range(1, 9), 0)
    worst = 0.0
    for _lo, _hi, segment in prime_segments(1 << 16):
        for p in segment:
            if p > bound:
                assert worst <= GAP_C, worst
                return [f"class-gap ratio {worst:.4f} <= {GAP_C} through {bound:,}"]
            a = p % 11
            if a in last:
                # A gap (q, p] costs (p - x)/ln^2 max(x, 37) at most at x = q.
                worst = max(worst, (p - last[a]) / math.log(max(last[a], FIRST)) ** 2)
                last[a] = p
    raise AssertionError("prime_segments is unbounded")  # pragma: no cover


def check_window() -> list[str]:
    # Below 2**64 SymPy's isprime is deterministic.
    from sympy import isprime

    for a in range(1, 9):
        assert any(isprime(p) for p in range(X_GAP + 1, SIEVED + 1) if p % 11 == a), a
    return [f"every class has a prime in ({X_GAP:,}, {SIEVED:,}]"]


def check_ceiling() -> list[str]:
    lines = []
    for n in range(2, 12):
        q_star, digits = ceiling(n)
        q, d = walk(brainfuck(parity(n)))
        assert q <= q_star, (n, q, q_star)
        assert d <= digits, (n, d, digits)
        t = 2**n
        lines.append(
            f"n={n:2d}  D={d:>7,} <= {digits:>7,}"
            f"  D/(T ln T) {d / (t * math.log(t)):6.2f} <= "
            f"{digits / (t * math.log(t)):6.2f}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bound", type=int, default=10**7)
    args = parser.parse_args(argv)
    print("L1  tree bound C <= 35T/2 + 55n + 25")
    print("\n".join(check_tree()))
    print("L2  class gaps mod 11 against ln^2")
    print("\n".join(check_gaps(args.bound)))
    print("\n".join(check_window()))
    print("L3  digit ceiling on parity")
    print("\n".join(check_ceiling()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
