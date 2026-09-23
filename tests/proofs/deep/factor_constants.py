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
L5  the behavior count's exponent is ln 8, so the floor is 1/(3 ln 10) and
    the constant is bracketed within a factor of 105 against the tree.
L6  the chained tape lookup runs, and emits 2.532 characters an entry,
    which closes that bracket to 15.2.
L7  one walk cell per group of entries, the last bits resolved by a tree
    emitted once, brings that to 1.516 an entry and the bracket to 9.1.
L8  a signed encoding puts two entries in a byte, which halves the span
    for half a character a cell: 1.006 an entry, and the bracket 6.04.
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
COST = 2.9

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


#: The eight instruction residues; the other three classes are ignored.
USEFUL = tuple(range(1, 9))
#: Proposition "Explicit floor" and Corollary "GRH ceiling", as constants.
FLOOR = 1 / (3 * math.log(10))
CEILING = 35 / math.log(10)


def useful_logs(count: int) -> list[float]:
    """``ln q_i`` for the first ``count`` primes with residue in 1..8 mod 11."""
    out: list[float] = []
    for _lo, _hi, segment in prime_segments(1 << 14):
        for p in segment:
            if p % 11 in USEFUL:
                out.append(math.log(p))
                if len(out) == count:
                    return out
    raise AssertionError("prime_segments is unbounded")  # pragma: no cover


def count_rate(logq: list[float], budget: float) -> tuple[float, int]:
    """The behavior count's exponent at the saddle, per ``L/ln L``.

    The proof takes ``s = ln 8/ln q_K`` with ``K`` the largest run count the
    budget affords, so every ``q_i**s <= 8`` and the sum over run counts is at
    most ``K`` times its last term.
    """
    total, k = 0.0, 0
    while k < len(logq) and total + logq[k] <= budget:
        total += logq[k]
        k += 1
    assert k < len(logq), "prime table too short for this budget"
    s = math.log(8) / logq[k - 1]
    tail = math.fsum(math.log(7) - math.log(math.expm1(s * c)) for c in logq[:k])
    bound = s * budget + tail + math.log(8 * k / 7)
    return bound / (budget / math.log(budget)), k


def check_floor() -> list[str]:
    """L5  the lower bound's leading constant, and the gap it leaves."""
    lines = []
    logq = useful_logs(12_000)
    head = [round(math.exp(c)) for c in logq[:5]]
    assert head == [2, 3, 5, 7, 13], head
    lines.append(f"q_1..q_5 = {head}, ln 8 = {math.log(8):.5f}")

    # The exponent descends towards ln 8 from above; the correction is of
    # order lnln L/ln L, so L = 10**5 is still 10% high.
    rates = []
    for exponent in (3, 4, 5):
        rate, k = count_rate(logq, 10.0**exponent)
        rates.append(rate)
        lines.append(f"L=10**{exponent}  K={k:>6,}  exponent/(L/ln L) = {rate:.4f}")
    assert rates == sorted(rates, reverse=True), rates
    assert rates[-1] < 2.30, rates
    assert min(rates) > math.log(8), rates

    # Same constant from the crude p_i >= i+1, approached more slowly.
    crude = [math.log(i + 1) for i in range(1, 16_000)]
    crude_rate, _ = count_rate(crude, 10.0**5)
    assert crude_rate > rates[-1], (crude_rate, rates[-1])
    lines.append(
        f"crude p_i >= i+1 at L=10**5: {crude_rate:.4f}, above {rates[-1]:.4f}"
    )

    # The bracket and its factorization.
    assert abs(FLOOR - 0.1447648) < 1e-6, FLOOR
    assert abs(CEILING / FLOOR - 105) < 1e-9, CEILING / FLOOR
    assert abs((35 / 2) / (1 / 3) * 2 - 105) < 1e-9
    lines.append(
        f"floor {FLOOR:.5f}, tree ceiling {CEILING:.4f} on GRH"
        f"  ratio {CEILING / FLOOR:.0f} = 52.5 runs x 2 walk; L6 cuts the runs"
    )
    # Counting spellings is capped at 1/(3(1-theta) ln 10).
    cap = 1 / (3 * 0.5 * math.log(10))
    assert abs(cap - 0.2895296) < 1e-6, cap
    lines.append(
        f"spelling-count cap on GRH {cap:.4f}, still {CEILING / cap:.0f}x below"
    )
    return lines


#: A brainfuck cell holds one byte, so an index digit gets at most eight bits
#: and the chained lookup takes one level per digit.
RADIX_BITS = 8


def chain_layout(n: int, leaf: int = 2) -> tuple[list[int], list[int], int]:
    """``(chunk sizes top-down, hop stride per level, cells spanned)``.

    ``leaf`` is the stride the bottom level hops by: a walk/data pair for
    Lemma "Chained lookup", a whole group for Lemma "Grouped lookup".  The
    short chunk goes second from the top, since a hop loop is ``3*stride``
    characters and the top stride is the span over the top radix, so a small
    radix on top costs three times what it costs at the leaf.
    """
    levels = max(1, -(-n // RADIX_BITS))
    rest = n - RADIX_BITS * (levels - 1)
    if levels == 1:
        sizes = [n]
    elif levels == 2:
        sizes = [RADIX_BITS, rest]
    else:
        sizes = [RADIX_BITS, rest] + [RADIX_BITS] * (levels - 2)
    blocks = [leaf]
    for size in reversed(sizes):
        blocks.append((1 << size) * blocks[-1] + 2)
    strides = [blocks[len(sizes) - 1 - k] for k in range(len(sizes))]
    return sizes, strides, blocks[-1]


def chain_cell(x: int, n: int) -> int:
    """The cell holding entry ``x`` under :func:`chain_layout`."""
    sizes, strides, _ = chain_layout(n)
    digits, rest = [], x
    for size in reversed(sizes):
        digits.append(rest & ((1 << size) - 1))
        rest >>= size
    digits.reverse()
    start = 0
    for k, size in enumerate(sizes):
        index = (1 << size) - 1 - digits[k]
        start += index * strides[k] if k < len(sizes) - 1 else 2 * index
    return start + 1


def bf_chain(truth_table: str) -> str:
    """The chained tape lookup of Lemma "Chained lookup"."""
    n = int(math.log2(len(truth_table)))
    sizes, strides, span = chain_layout(n)
    flip = truth_table.count("1") * 2 > len(truth_table)
    cells = [0] * span
    for x, bit in enumerate(truth_table):
        cells[chain_cell(x, n)] = int(bit) ^ flip

    out, anchor = [], span - 2
    for cell in range(anchor + 1):
        if cells[cell]:
            out.append("+")
        if cell < anchor:
            out.append(">")
    for k, size in enumerate(sizes):
        for _ in range(size):
            out.append("[->++<]>[-<+>]<>,")
            out.append("-" * 48)
            out.append("[-<+>]<")
        seat = strides[k] if k == len(sizes) - 1 else 2
        out.append("[-" + "<" * seat + "+" + ">" * seat + "]" + "<" * seat)
        hop = "<" * strides[k]
        out.append(f"[[-{hop}+{'>' * strides[k]}]{hop}-]")
    out.append("+" * 49 + ">[-<->]<." if flip else ">" + "+" * 48 + ".")
    return "".join(out)


def chain_length(n: int, ones: int, size: int) -> int:
    """Closed form for what :func:`bf_chain` emits."""
    sizes, strides, span = chain_layout(n)
    total = span - 2 + min(ones, size - ones)
    for k, size_k in enumerate(sizes):
        total += 72 * size_k + 10 + 3 * strides[k] + 7
    return total + (58 if ones * 2 > size else 50)


#: A group is ``[W][S0][S1][d_0]..[d_(k-1)]``; the three are its walk cell
#: and the two scratch cells the selector runs in.
GROUP_SCRATCH = 3


def group_cell(x: int, n: int, bits: int) -> int:
    """The cell holding entry ``x`` under the grouped layout."""
    sizes, strides, _ = chain_layout(n - bits, (1 << bits) + GROUP_SCRATCH)
    group, within = x >> bits, x & ((1 << bits) - 1)
    digits, rest = [], group
    for size in reversed(sizes):
        digits.append(rest & ((1 << size) - 1))
        rest >>= size
    digits.reverse()
    start = 0
    for k, size in enumerate(sizes):
        start += ((1 << size) - 1 - digits[k]) * strides[k]
    return start + GROUP_SCRATCH + within


def group_selector(bits: int, *, flip: bool) -> str:
    """The decision tree over one group, entered and left on its walk cell."""

    def leaf(index: int) -> str:
        out, back = ">" * (GROUP_SCRATCH + index), "<" * (GROUP_SCRATCH + index)
        if not flip:
            return out + "+" * 48 + ".[-]" + back
        return "+" * 49 + out + "[-" + back + "-" + out + "]" + back + ".[-]"

    def node(depth: int, base: int) -> str:
        if depth == bits:
            return leaf(base)
        half = 1 << (bits - depth - 1)
        high, low = node(depth + 1, base + half), node(depth + 1, base)
        return ">," + "-" * 48 + f">+<[->-<<{high}>]>[-<<{low}>>]<<"

    return node(0, 0)


def bf_group(truth_table: str, bits: int) -> str:
    """The grouped tape lookup of Lemma "Grouped lookup"."""
    n = int(math.log2(len(truth_table)))
    bits = min(bits, n)
    sizes, strides, span = chain_layout(n - bits, (1 << bits) + GROUP_SCRATCH)
    flip = truth_table.count("1") * 2 > len(truth_table)
    cells = [0] * span
    for x, bit in enumerate(truth_table):
        cells[group_cell(x, n, bits)] = int(bit) ^ flip

    out, anchor = [], span - 2
    for cell in range(anchor + 1):
        if cells[cell]:
            out.append("+")
        if cell < anchor:
            out.append(">")
    for k, size in enumerate(sizes):
        for _ in range(size):
            out.append("[->++<]>[-<+>]<>,")
            out.append("-" * 48)
            out.append("[-<+>]<")
        seat = strides[k] if k == len(sizes) - 1 else 2
        out.append("[-" + "<" * seat + "+" + ">" * seat + "]" + "<" * seat)
        hop = "<" * strides[k]
        out.append(f"[[-{hop}+{'>' * strides[k]}]{hop}-]")
    out.append(group_selector(bits, flip=flip))
    return "".join(out)


def group_length(n: int, ones: int, size: int, bits: int) -> int:
    """Closed form for what :func:`bf_group` emits."""
    bits = min(bits, n)
    sizes, strides, span = chain_layout(n - bits, (1 << bits) + GROUP_SCRATCH)
    total = span - 2 + min(ones, size - ones)
    for k, size_k in enumerate(sizes):
        seat = strides[k] if k == len(sizes) - 1 else 2
        total += 72 * size_k + 3 * seat + 4 + 3 * strides[k] + 7
    return total + len(group_selector(bits, flip=ones * 2 > size))


def check_chain() -> list[str]:
    """L6  the chained lookup: it runs, and its constant is 2.532."""
    from tests.tools.boolean_runners import run_bf

    lines, rng = [], random.Random(17)
    for n in range(1, 15):
        table = parity(n)
        assert len(bf_chain(table)) == chain_length(n, table.count("1"), 1 << n), n
    lines.append("emitted length matches the closed form, n = 1..14")

    runs = 0
    for n in range(1, 7):
        size = 1 << n
        for table in ("0" * size, "1" * size, parity(n)):
            program = bf_chain(table)
            for k in range(size):
                bits = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                assert run_bf(program, bits) == table[k], (n, table, k)
                runs += 1
    lines.append(f"exhaustive: {runs} executions over n = 1..6, all correct")

    # Past n = 8 a one-cell index would wrap; these are the indices that
    # caught it, so the sample always includes them.
    runs = 0
    for n in (9, 10, 12):
        size = 1 << n
        for table in (parity(n), "1" * size):
            program = bf_chain(table)
            for k in [255, 256, 257, size - 1, *rng.sample(range(size), 6)]:
                bits = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                assert run_bf(program, bits) == table[k], (n, k)
                runs += 1
    lines.append(f"sampled past the byte: {runs} executions at n = 9, 10, 12")

    worst = max(chain_length(n, 1 << (n - 1), 1 << n) / (1 << n) for n in (24, 64))
    assert worst < 2.532, worst
    limsup = 2 * worst / math.log(10)
    assert limsup < 2.20, limsup
    lines.append(f"worst chars/entry {worst:.5f} < 2.532, limsup {limsup:.4f} < 2.20")
    lines.append(
        f"bracket {FLOOR:.5f} .. {limsup:.4f} is {limsup / FLOOR:.1f}x,"
        f" was {CEILING / FLOOR:.0f}x on the tree"
    )
    return lines


def check_group() -> list[str]:
    """L7  the grouped lookup: it runs, and its constant is 1.516."""
    from tests.tools.boolean_runners import run_bf

    lines, rng = [], random.Random(23)
    for bits in (2, 4, 8):
        for n in range(1, 13):
            table = parity(n)
            emitted = len(bf_group(table, bits))
            assert emitted == group_length(n, table.count("1"), 1 << n, bits), (n, bits)
    lines.append("emitted length matches the closed form, n = 1..12, k = 4, 16, 256")

    runs = 0
    for bits in (1, 2, 4):
        for n in range(1, 7):
            size = 1 << n
            for table in ("0" * size, "1" * size, parity(n)):
                program = bf_group(table, bits)
                for k in range(size):
                    inputs = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                    assert run_bf(program, inputs) == table[k], (bits, n, k)
                    runs += 1
    lines.append(f"exhaustive: {runs} executions over n = 1..6, k = 2, 4, 16")

    runs = 0
    for n in (9, 10, 12):
        size = 1 << n
        for table in (parity(n), "1" * size):
            program = bf_group(table, 8)
            for k in [255, 256, 257, size - 1, *rng.sample(range(size), 5)]:
                inputs = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                assert run_bf(program, inputs) == table[k], (n, k)
                runs += 1
    lines.append(f"sampled at k = 256: {runs} executions at n = 9, 10, 12")

    # The selector is O(k**2) and emitted once, so k may grow with T; at
    # k = log T it vanishes and the span tends to (1 + 1/255) T.
    worst = max(
        group_length(n, 1 << (n - 1), 1 << n, bits) / (1 << n)
        for n, bits in ((32, 10), (64, 14))
    )
    assert worst < 1.516, worst
    limit = (1 + 1 / 255) * (1 + 3 / 255) + 0.5
    assert abs(limit - 1.51573) < 1e-5, limit
    limsup = 2 * limit / math.log(10)
    assert limsup < 1.317, limsup
    lines.append(f"chars/entry {worst:.5f}, limit {limit:.5f}, limsup {limsup:.4f}")
    lines.append(
        f"bracket {FLOOR:.5f} .. {limsup:.4f} is {limsup / FLOOR:.1f}x"
        f"  = {limit * 3:.2f} construction x 2 walk"
    )
    return lines


#: Cell values for a pair of entries, cheapest first.  A cell is a byte, so
#: ``-`` reaches 255 -- that is -1 -- in one character, and the four patterns
#: can be spelled for 0, 1, 1, 2 rather than 0, 1, 2, 3.
PACK_VALUES = (0, 1, 255, 2)


def pack_layout(n: int, bits: int) -> tuple[list[int], list[int], int]:
    """As :func:`chain_layout`, with a packed group as the leaf stride."""
    return chain_layout(n - bits, (1 << (bits - 1)) + GROUP_SCRATCH)


def pack_cell(x: int, n: int, bits: int) -> tuple[int, int]:
    """``(cell holding entry x, which of the cell's two entries it is)``."""
    sizes, strides, _ = pack_layout(n, bits)
    group, within = x >> bits, x & ((1 << bits) - 1)
    digits, rest = [], group
    for size in reversed(sizes):
        digits.append(rest & ((1 << size) - 1))
        rest >>= size
    digits.reverse()
    start = sum(
        ((1 << size) - 1 - digits[k]) * strides[k] for k, size in enumerate(sizes)
    )
    return start + GROUP_SCRATCH + (within >> 1), within & 1


def pack_encoding(truth_table: str) -> dict[int, int]:
    """Spell the commonest pair with 0, the rarest with 2.

    Frequencies sort, so the cost is ``f2 + f3 + 2 f4`` with ``f1 >= .. >= f4``,
    which is largest when the four patterns are equally common and the table
    pays one character a cell.  This subsumes the complement trick: flipping
    the table permutes the patterns and leaves the frequencies alone.
    """
    counts = [0, 0, 0, 0]
    for x in range(0, len(truth_table), 2):
        counts[int(truth_table[x]) * 2 + int(truth_table[x + 1])] += 1
    order = sorted(range(4), key=lambda pattern: -counts[pattern])
    return {pattern: PACK_VALUES[i] for i, pattern in enumerate(order)}


def pack_switch(table: dict[int, int], bit: int) -> str:
    """Decode the parked value; entered and left on the walk cell, zeroed."""
    inverse = {value: pattern for pattern, value in table.items()}

    def emit(pattern: int) -> str:
        # Leave the cell at zero: every enclosing ']' retests it.
        return "+" * (48 + ((pattern >> (1 - bit)) & 1)) + ".[-]"

    def case(j: int) -> str:
        # The walk cell was raised by one, so value v arrives as v + 1.
        out = emit(inverse[(j - 1) % 256])
        if j == len(PACK_VALUES) - 1:
            return out
        return ">+<[->-<" + case(j + 1) + "]>[-<" + out + ">]<"

    return case(0)


def pack_selector(table: dict[int, int], bits: int) -> str:
    """The group's tree parks a byte on the walk cell; one decode follows."""

    def leaf(index: int) -> str:
        home, back = ">" * (GROUP_SCRATCH + index), "<" * (GROUP_SCRATCH + index)
        return home + "[-" + back + "+" + home + "]" + back

    def node(depth: int, base: int) -> str:
        if depth == bits - 1:
            return leaf(base)
        half = 1 << (bits - 2 - depth)
        high, low = node(depth + 1, base + half), node(depth + 1, base)
        return ">," + "-" * 48 + f">+<[->-<<{high}>]>[-<<{low}>>]<<"

    high, low = pack_switch(table, 1), pack_switch(table, 0)
    return node(0, 0) + "+>," + "-" * 48 + f">+<[->-<<{high}>]>[-<<{low}>>]<<"


def pack_selector_length(table: dict[int, int], bits: int) -> int:
    """Closed form for :func:`pack_selector`, which is quadratic in ``k``."""
    k = 1 << (bits - 1)
    leaves = 2 * k * k + 14 * k
    both = len(pack_switch(table, 1)) + len(pack_switch(table, 0))
    return leaves + 71 * (k - 1) + 72 + both


def bf_pack(truth_table: str, bits: int) -> str:
    """The packed tape lookup of Lemma "Packed lookup"."""
    n = int(math.log2(len(truth_table)))
    sizes, strides, span = pack_layout(n, bits)
    table = pack_encoding(truth_table)
    cells = [0] * span
    for x in range(0, len(truth_table), 2):
        cell, _ = pack_cell(x, n, bits)
        cells[cell] = table[int(truth_table[x]) * 2 + int(truth_table[x + 1])]

    out, anchor = [], span - 2
    for cell in range(anchor + 1):
        value = cells[cell]
        out.append("+" * value if value < 128 else "-" * (256 - value))
        if cell < anchor:
            out.append(">")
    for k, size in enumerate(sizes):
        for _ in range(size):
            out.append("[->++<]>[-<+>]<>,")
            out.append("-" * 48)
            out.append("[-<+>]<")
        seat = strides[k] if k == len(sizes) - 1 else 2
        out.append("[-" + "<" * seat + "+" + ">" * seat + "]" + "<" * seat)
        hop = "<" * strides[k]
        out.append(f"[[-{hop}+{'>' * strides[k]}]{hop}-]")
    out.append(pack_selector(table, bits))
    return "".join(out)


def pack_length(n: int, bits: int, writes: int, table: dict[int, int]) -> int:
    """Closed form for what :func:`bf_pack` emits."""
    sizes, strides, span = pack_layout(n, bits)
    total = span - 2 + writes
    for k, size in enumerate(sizes):
        seat = strides[k] if k == len(sizes) - 1 else 2
        total += 72 * size + 3 * seat + 4 + 3 * strides[k] + 7
    return total + pack_selector_length(table, bits)


def even_patterns(n: int) -> str:
    """The table that costs the most: all four pairs equally often."""
    out = []
    for x in range(1 << n):
        pattern = (x >> 1) % 4
        out.append(str((pattern >> 1) if x % 2 == 0 else (pattern & 1)))
    return "".join(out)


def check_pack() -> list[str]:
    """L8  two entries to a cell: it runs, and its constant is 1.006."""
    from tests.tools.boolean_runners import run_bf

    lines, rng = [], random.Random(29)
    for bits in (2, 3, 4, 6):
        for n in range(bits, 13):
            for table in ("0" * (1 << n), parity(n), even_patterns(n)):
                code = pack_encoding(table)
                writes = sum(
                    min(code[p], 256 - code[p]) if code[p] else 0
                    for x in range(0, len(table), 2)
                    for p in (int(table[x]) * 2 + int(table[x + 1]),)
                )
                assert pack_length(n, bits, writes, code) == len(bf_pack(table, bits))
    lines.append("emitted length matches the closed form, n = 2..12, k = 2..32")

    runs = 0
    for bits in (1, 2, 3):
        for n in range(bits, 7):
            size = 1 << n
            for table in ("0" * size, "1" * size, parity(n), even_patterns(n)):
                program = bf_pack(table, bits)
                for k in range(size):
                    inputs = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                    assert run_bf(program, inputs) == table[k], (bits, n, k)
                    runs += 1
    lines.append(f"exhaustive: {runs} executions over n = 1..6, k = 1, 2, 4")

    runs = 0
    for n in (9, 10, 12):
        size = 1 << n
        for table in (parity(n), even_patterns(n)):
            program = bf_pack(table, 8)
            for k in [0, 255, 256, size - 1, *rng.sample(range(size), 5)]:
                inputs = [str((k >> (n - 1 - j)) & 1) for j in range(n)]
                assert run_bf(program, inputs) == table[k], (n, k)
                runs += 1
    lines.append(f"sampled at k = 128: {runs} executions at n = 9, 10, 12")

    # Worst case is one character a cell, and k may grow with T because the
    # selector is emitted once; at k = log T only the walk's overhead is left.
    code = dict(enumerate(PACK_VALUES))
    worst = min(
        pack_length(n, bits, 1 << (n - 1), code) / (1 << n)
        for n, bits in ((32, 7), (64, 8), (80, 9))
    )
    assert worst < 1.012, worst
    limit = 0.5 * (1 + 3 / 255) + 0.5
    assert abs(limit - 1.00588) < 1e-5, limit
    limsup = 2 * limit / math.log(10)
    assert limsup < 0.874, limsup
    lines.append(f"chars/entry {worst:.5f}, limit {limit:.5f}, limsup {limsup:.4f}")
    lines.append(
        f"bracket {FLOOR:.5f} .. {limsup:.4f} is {limsup / FLOOR:.2f}x"
        f"  = {limit * 3:.2f} construction x 2 walk"
    )

    # The family bottoms out here: m entries a cell need 2**m values, the
    # cheapest of which cost 2**(2m-2) characters in total.
    costs = {m: (1 + 2 ** (m - 2)) / m for m in range(1, 6)}
    assert min(costs, key=lambda m: costs[m]) == 2, costs
    assert abs(costs[2] - costs[3]) < 1e-12, costs
    lines.append(
        "per entry (1 + 2**(m-2))/m over m = 1..5: "
        + ", ".join(f"{costs[m]:.3f}" for m in sorted(costs))
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
    print("L4  the GRH threshold and its ceiling")
    print("\n".join(check_grh()))
    print("L5  the lower bound's leading constant")
    print("\n".join(check_floor()))
    print("L6  the chained lookup and its constant")
    print("\n".join(check_chain()))
    print("L7  the grouped lookup and its constant")
    print("\n".join(check_group()))
    print("L8  two entries to a cell")
    print("\n".join(check_pack()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
