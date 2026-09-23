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
L4  the GRH short-interval threshold falls inside the sieved range, and the
    resulting walk's ceiling is 24.6 T ln T over n >= 8.
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


#: Dudek-Grenie-Molteni, IJNT 15 (2019) 825-862, Thm 1.1, Table 1 row
#: ``(alpha, delta, rho, m) = (1/2, 1, 12, 23)`` at ``q = 11``.
PHI, LNQ = 10, math.log(11)
ALPHA, DELTA, RHO, MPAR = 0.5, 1.0, 12.0, 23.0
#: Runs the sieve rule alone spends climbing from 37 to ``X_GAP``.
K_SIEVE = math.floor((X_GAP - FIRST) / (GAP_C * math.log(X_GAP) ** 2))
#: ``u_(j+1) <= u_j + A ln u_j + BETA`` for ``u = sqrt(B)``.
A_GRH = PHI * math.sqrt(2) * 2 * ALPHA
BETA = PHI * math.sqrt(2) * (ALPHA * math.log(2) + DELTA * LNQ + RHO)


def dgm_h(t: float) -> float:
    """The DGM half-width at ``q = 11``: ``10(ln t/2 + ln 11 + 12) sqrt t``."""
    return PHI * (ALPHA * math.log(t) + DELTA * LNQ + RHO) * math.sqrt(t)


def grh_ceiling(runs: int) -> tuple[float, int] | None:
    """``(U, D)`` from the GRH walk, or None when the sieve already covers."""
    left = runs - K_SIEVE
    if left <= 0:
        return None
    root = math.sqrt(SIEVED)
    u = root
    for _ in range(6000):  # rises to the largest fixed point
        u = root + left * (A_GRH * math.log(u) + BETA)
    assert root + left * (A_GRH * math.log(u) + BETA) <= u + 1e-6, runs
    return u, math.floor(2 * runs * math.log10(u)) + 1


def check_grh() -> list[str]:
    """L4  the GRH threshold overlaps the sieve, and its ceiling."""
    lines = []
    threshold = (MPAR * PHI * LNQ) ** 2
    assert threshold < SIEVED, threshold
    lines.append(f"DGM threshold {threshold:,.0f} < sieved {SIEVED:,}, so they overlap")

    # Recentring at c = x + h(2x) needs h(2x) <= x, decreasing from 10**11.
    assert dgm_h(2 * SIEVED) <= SIEVED
    lines.append(f"h(2x)/x = {dgm_h(2 * SIEVED) / SIEVED:.2e} <= 1 at x = 10**11")
    assert K_SIEVE == 18_083_227, K_SIEVE
    assert abs(BETA - 208.5183) < 1e-3, BETA

    # The closed form dominates direct iteration of B -> B + 2h(2B).
    b = float(SIEVED)
    steps = 20_000
    for _ in range(steps):
        b += 2 * dgm_h(2 * b)
    closed = grh_ceiling(K_SIEVE + steps)
    assert closed is not None
    assert math.sqrt(b) <= closed[0], (b, closed)
    lines.append(
        f"{steps:,} direct steps: sqrt B = {math.sqrt(b):,.0f} <= {closed[0]:,.0f}"
    )

    # The ceiling at every arity: sieve below, GRH above, 24.6 over n >= 8.
    worst = 0.0
    for n in (13, 16, 19, 20, 22, 25, 30, 60):
        runs = int(tree_bound(n))
        grh = grh_ceiling(runs)
        if grh is None:
            digits, rule = ceiling(n)[1], "sieve"
        else:
            digits, rule = grh[1], "GRH"
        ratio = digits / (2**n * n * math.log(2))
        worst = max(worst, ratio)
        lines.append(f"n={n:<3} {rule:>5}  D/(T ln T) <= {ratio:6.2f}")
    assert worst <= 24.6, worst
    assert 35 / math.log(10) < 15.21
    lines.append(f"worst over the row {worst:.2f} <= 24.6; limsup 35/ln 10 = 15.20")

    # A density exponent A gives theta > 1 - 1/A, hence 35A/(2 ln 10).  Both
    # shipped constants are on this curve, which is why it can be quoted for
    # Thorner-Zaman's explicit A = 99.
    def from_exponent(a: float) -> float:
        return 35 * a / (2 * math.log(10))

    assert abs(from_exponent(12 / 5) - 42 / math.log(10)) < 1e-9  # Huxley
    assert abs(from_exponent(2.0) - 35 / math.log(10)) < 1e-9  # GRH
    lines.append(f"density exponent A = 99 gives {from_exponent(99):.1f}")
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
    print("L4  the GRH threshold and its ceiling")
    print("\n".join(check_grh()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
