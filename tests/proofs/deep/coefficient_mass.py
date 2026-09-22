"""The certificate sweeps behind the two coefficient-mass papers.

Run:  just proofs   (or python tests/proofs/deep/coefficient_mass.py)

``docs/proofs/coefficient-mass.tex`` proves the displaced-zero tail bound
(Theorem 2.2) under the node cutoff ``y_i <= 1/2``;
``docs/proofs/coefficient-mass-attainment.tex`` shows the cutoff cannot be
raised, that the ``(2,3,5)`` families are ordered at every degree, and that
the partial-sum criterion is necessary as well as sufficient.  This
module is a *seeded* sweep whose counts are stable, so the qualitative claims
are executed rather than remembered, plus exact checks of every number the
first paper works out by hand.

The sweep's three claims:

* the **repaired** product -- ``prod_{i<=f+1} y/(1-y)`` times
  ``max(1, y/(1-y))`` over the nodes the discard drops -- is never violated,
  at any node range;
* the **stated** product of ``thm:tail`` is violated only *above* the cutoff
  ``y_i <= 1/2``, never below it;
* the **deletion step** driving the theorem -- dropping the largest prescribed
  zero together with the largest node raises the tail -- reverses only above
  the cutoff.

Tails are exact, not truncated.  A ``c``-node sum with ``u_0 = 1`` and zeros
``Z``, ``|Z| = c - 1``, has used its whole zero budget, so it keeps one sign
past ``max Z``; the tail past that point is therefore the absolute value of a
geometric sum, ``sum_i a_i/(1 - y_i)`` minus the head.  Truncating instead
would make every consecutive case read as *strictly* below its bound and
silently destroy the equality half of the theorem -- which is how the first
draft of this sweep failed.

Every count here is a negative result, so each group carries a positive
control: a deliberately falsified variant that the same probe must catch.  A
sweep whose probe never fires reports a wall that is not there.
"""

from __future__ import annotations

import random
from fractions import Fraction

#: Cost band; see ``__main__.py``.  Exact rational solves of 450 small
#: Vandermonde systems, an exact simplex on the two small searches, and the
#: sign identities to D=40.  Measured 0.6s -- nodes are unit fractions over
#: small denominators, so the arithmetic stays narrow.  Sits beside
#: ``multiplicity``, the other coefficient-mass proof, in ``ci``.
BAND = "ci"
COST = 1.0

#: Draws are seeded so the printed tallies are quotable.  Changing this
#: reseeds every count below.
SEED = 20260922


def _solve(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    n = len(matrix)
    a = [[*row, b] for row, b in zip(matrix, rhs, strict=True)]
    for col in range(n):
        piv = next(r for r in range(col, n) if a[r][col] != 0)
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col], strict=True)]
    return [a[j][n] for j in range(n)]


def _certificate(nodes: list[Fraction], zeros: list[int]) -> list[Fraction]:
    """``a`` with ``u_d = sum a_i y_i^d``, ``u_0 = 1`` and ``u_z = 0`` on Z."""
    points = [0, *zeros]
    matrix = [[y**d for y in nodes] for d in points]
    rhs = [Fraction(1), *([Fraction(0)] * len(zeros))]
    return _solve(matrix, rhs)


def _u(nodes: list[Fraction], a: list[Fraction], d: int) -> Fraction:
    return sum(ai * y**d for ai, y in zip(a, nodes, strict=True))


def _tail(nodes: list[Fraction], zeros: list[int], a: list[Fraction]) -> Fraction:
    """Exact ``sum_{d>=1} |u_d|``; one-signed past ``max Z`` by the zero bound."""
    n = max(zeros) if zeros else 0
    head = sum(abs(_u(nodes, a, d)) for d in range(1, n + 1))
    total = sum(ai / (1 - y) for ai, y in zip(a, nodes, strict=True))
    upto = sum(_u(nodes, a, d) for d in range(n + 1))
    return head + abs(total - upto)


def _leading_run(zeros: list[int]) -> int:
    seen, f = set(zeros), 0
    while f + 1 in seen:
        f += 1
    return f


def _stated(nodes: list[Fraction], f: int) -> Fraction:
    bound = Fraction(1)
    for y in nodes[: f + 1]:
        bound *= y / (1 - y)
    return bound


def _repaired(nodes: list[Fraction], f: int) -> Fraction:
    bound = _stated(nodes, f)
    for y in nodes[f + 1 :]:
        bound *= max(Fraction(1), y / (1 - y))
    return bound


#: Node pools, in the paper's three groups.  ``below`` is the cutoff regime
#: ``y_i <= 1/2``; ``mixed`` can place a node above it; ``anywhere`` reaches
#: ``18/19``.
_POOLS = {
    "y <= 1/2": [Fraction(1, k) for k in range(2, 12)],
    "some y > 1/2": [Fraction(1, k) for k in range(2, 8)]
    + [Fraction(k, 19) for k in (11, 13, 15)],
    "anywhere in (0,1)": [Fraction(k, 19) for k in range(1, 19)],
}


def _draws(pool: list[Fraction], count: int, rng: random.Random):
    """``(nodes, zeros)`` pairs: nodes increasing, ``|Z| = c - 1``."""
    out = []
    for _ in range(count):
        c = rng.randint(2, 4)
        nodes = sorted(rng.sample(pool, c))
        zeros = sorted(rng.sample(range(1, 9), c - 1))
        out.append((nodes, zeros))
    return out


def _sweep(pool, count, rng, failures, label):
    """Tally stated/repaired violations and deletion reversals over one pool."""
    stated_bad = repaired_bad = reversals = deletions = 0
    for nodes, zeros in _draws(pool, count, rng):
        c = len(nodes)
        f = _leading_run(zeros)
        a = _certificate(nodes, zeros)
        tail = _tail(nodes, zeros, a)
        if tail > _stated(nodes, f):
            stated_bad += 1
        if tail > _repaired(nodes, f):
            repaired_bad += 1
            failures.append(f"{label}: repaired bound broken at {nodes}, Z={zeros}")
        # The deletion step: drop max Z together with the largest node.
        if f < c - 1 and c >= 3:
            rest = sorted(set(zeros) - {max(zeros)})
            if len(rest) == c - 2:
                sub = nodes[: c - 1]
                sub_tail = _tail(sub, rest or [0], _certificate(sub, rest))
                deletions += 1
                if tail >= sub_tail:
                    reversals += 1
    return stated_bad, repaired_bad, reversals, deletions


def _check_controls(failures: list[str]) -> int:
    """Each negative result above needs a probe that demonstrably fires."""
    checks = 0
    nodes = [Fraction(1, 5), Fraction(1, 3), Fraction(1, 2)]

    # (1) Equality at a consecutive Z: the exact tail must MEET the bound, so
    # a bound shaved by 1% must be exceeded.  This is the probe truncation
    # would have killed.
    zeros = [1, 2]
    a = _certificate(nodes, zeros)
    tail = _tail(nodes, zeros, a)
    bound = _stated(nodes, _leading_run(zeros))
    if tail != bound:
        failures.append(f"consecutive Z not exact: {tail} != {bound}")
    if not tail > bound * Fraction(99, 100):
        failures.append("control dead: shaved bound not exceeded at consecutive Z")
    checks += 2

    # (2) Over-counting the product by one factor must break somewhere, or the
    # ``f+1`` in the theorem carries no weight.  It does not break on every
    # displaced set -- roughly a third survive -- so this searches rather than
    # asserting on one hand-picked configuration, which is how an earlier
    # draft of this control managed to fail while the theorem was fine.
    over_broken = 0
    for zeros in ([1, 3], [2, 3], [1, 4], [2, 5], [3, 4]):
        a = _certificate(nodes, zeros)
        f = _leading_run(zeros)
        if _tail(nodes, zeros, a) > _stated(nodes, f + 1):
            over_broken += 1
    if not over_broken:
        failures.append("control dead: f+2 factors never violated on displaced sets")
    checks += 1

    # (3) The cutoff must actually bite: a node above 1/2 has to produce a
    # stated-bound violation somewhere, else group two proves nothing.
    high = [Fraction(1, 10), Fraction(4, 5)]
    a = _certificate(high, [2])
    if not _tail(high, [2], a) > _stated(high, _leading_run([2])):
        failures.append("control dead: the paper's own y=4/5 witness does not violate")
    checks += 1
    return checks


def _simplex_min_t(rows: list[list[Fraction]], const: list[Fraction]) -> Fraction:
    """``min t`` over free ``q`` with ``|const_j + rows_j . q| <= t``, exactly.

    Dense tableau, Bland's rule, ``q`` split into a difference of nonnegatives.
    No phase 1: ``q = 0`` is feasible at ``t = max|const_j|``, so pivoting ``t``
    into the most negative row clears the right-hand side.  The optimum is
    re-certified below from the final tableau, so the value does not rest on
    the pivoting being right.
    """
    m = len(rows)
    n = len(rows[0]) if m else 0
    ncol = 2 * n + 1 + 2 * m
    table: list[list[Fraction]] = []
    for j in range(m):
        for sgn, rhs in ((1, -const[j]), (-1, const[j])):
            row = [Fraction(0)] * (ncol + 1)
            for i in range(n):
                row[i] = sgn * rows[j][i]
                row[n + i] = -sgn * rows[j][i]
            row[2 * n] = Fraction(-1)
            row[2 * n + 1 + len(table)] = Fraction(1)
            row[-1] = Fraction(rhs)
            table.append(row)
    total = len(table)
    basis = [2 * n + 1 + r for r in range(total)]
    z = [Fraction(0)] * (ncol + 1)
    z[2 * n] = Fraction(1)

    def pivot(r: int, col: int) -> None:
        pr = table[r]
        pv = pr[col]
        if pv != 1:
            inv = 1 / pv
            pr[:] = [v * inv for v in pr]
        for rr in range(total):
            if rr != r and table[rr][col] != 0:
                f = table[rr][col]
                table[rr] = [a - f * b for a, b in zip(table[rr], pr, strict=True)]
        if z[col] != 0:
            f = z[col]
            z[:] = [a - f * b for a, b in zip(z, pr, strict=True)]
        basis[r] = col

    worst = min(range(total), key=lambda r: table[r][-1])
    if table[worst][-1] < 0:
        pivot(worst, 2 * n)
    while True:
        col = next((k for k in range(ncol) if z[k] < 0), None)
        if col is None:
            break
        best = None
        for r in range(total):
            a = table[r][col]
            if a > 0:
                ratio = table[r][-1] / a
                if best is None or (ratio, basis[r]) < (best[0], basis[best[1]]):
                    best = (ratio, r)
        if best is None:  # pragma: no cover -- t >= 0 bounds the program
            raise RuntimeError("unbounded")
        pivot(best[1], col)
    x = [Fraction(0)] * ncol
    for r in range(total):
        x[basis[r]] = table[r][-1]
    q = [x[i] - x[n + i] for i in range(n)]
    star = -z[-1]
    y = [z[2 * n + 1 + r] for r in range(total)]
    # Weak-duality certificate, independent of the pivoting above.
    values = [const[j] + sum(rows[j][i] * q[i] for i in range(n)) for j in range(m)]
    assert max(abs(v) for v in values) == star
    assert all(v >= 0 for v in y)
    assert sum(y) <= 1
    y1, y2 = y[0::2], y[1::2]
    for i in range(n):
        assert sum((y1[j] - y2[j]) * rows[j][i] for j in range(m)) == 0
    assert sum((y1[j] - y2[j]) * const[j] for j in range(m)) == star
    return star


def _min_bk(roots: list[Fraction], k: int, cap: int) -> Fraction:
    """``min b_k`` over monic multiples of degree at most ``cap``, exactly."""
    import itertools

    poly = [Fraction(1)]
    for r in roots:  # ascending coefficients
        nxt = [Fraction(0)] * (len(poly) + 1)
        for i, c in enumerate(poly):
            nxt[i] -= r * c
            nxt[i + 1] += c
        poly = nxt
    deg_p = len(roots)
    best = None
    for degree in range(max(deg_p, k), cap + 1):
        n = degree - deg_p
        for exempt in itertools.combinations(range(degree), k - 1):
            keep = [j for j in range(degree) if j not in exempt]
            rows = [
                [poly[j - i] if 0 <= j - i <= deg_p else Fraction(0) for i in range(n)]
                for j in keep
            ]
            const = [poly[j - n] if 0 <= j - n <= deg_p else Fraction(0) for j in keep]
            value = _simplex_min_t(rows, const)
            if best is None or value < best:
                best = value
    assert best is not None
    return best


def _check_searches(failures: list[str]) -> int:
    """The search optima are exactly the family members they should be.

    The optima 2.0308 at ``(2,3)`` and 8.5178, 4.1218 at ``(2,3,5)`` are the
    corresponding members of the exact families of ``prop:sharp23`` (in the
    certificate paper) and ``prop:sharp235`` (in the attainment paper).
    Solved in rationals, "is" is literal.  Double precision does not settle
    this: on the same program at ``(3,4,5,6)`` it reports success and returns
    184.86 past degree 25.
    """
    t7 = Fraction(2) / (1 - Fraction(2) ** -6 + Fraction(3) ** -7)
    cases = [
        ([Fraction(2), Fraction(3)], 2, 8, t7, "t_7"),
        (
            [Fraction(2), Fraction(3), Fraction(5)],
            2,
            9,
            Fraction(804576811, 94458820),
            "t_9",
        ),
        ([Fraction(2), Fraction(3), Fraction(5)], 3, 9, Fraction(31585, 7663), "s_9"),
    ]
    for roots, k, cap, expected, name in cases:
        got = _min_bk(roots, k, cap)
        if got != expected:
            failures.append(f"min b_{k} at cap {cap} is {got}, not {name} = {expected}")
    return len(cases)


def _check_ordering(failures: list[str]) -> int:
    """``prop:sharp235``'s ordering, by the sign count rather than a check.

    Descartes forces ``a_D > 0``, ``t_D > 0``, ``c_D < 0``; then
    ``(r-1)(r-a_D) + t_D = eps_r > 0`` and the rows ``r = 3, 5`` give
    ``t_D > a_D + 1 > 8``, so the run already beats ``a_D`` and at most
    ``|c_D|`` can beat the run.  No threshold, no finite check -- this pins
    the identities the argument runs on.
    """
    checked = 0
    for degree in range(5, 41):
        rows, rhs = [], []
        for r in (Fraction(2), Fraction(3), Fraction(5)):
            rows.append(
                [
                    -(r ** (degree - 1)),
                    sum(r**j for j in range(1, degree - 1)),
                    Fraction(1),
                ]
            )
            rhs.append(-(r**degree))
        a, t, c = _solve(rows, rhs)
        if not (a > 0 and t > 0 and c < 0):
            failures.append(f"D={degree}: Descartes sign pattern broken")
        eps = {}
        for r in (Fraction(3), Fraction(5)):
            lhs = (r - 1) * (r - a) + t
            if lhs != r ** (1 - degree) * (r * t + (r - 1) * abs(c)):
                failures.append(f"D={degree}, r={r}: eps identity fails")
            eps[r] = lhs
        e3, e5 = eps[Fraction(3)], eps[Fraction(5)]
        if not e5 / e3 < 2 * Fraction(3, 5) ** (degree - 1):
            failures.append(f"D={degree}: eps ratio bound fails")
        if not t > a + 1 > 8:
            failures.append(f"D={degree}: t_D > a_D + 1 > 8 fails")
        mags = sorted([abs(a)] + [t] * (degree - 2) + [abs(c)], reverse=True)
        if mags[1] != t:
            failures.append(f"D={degree}: b_2 is not the run")
        checked += 1
    return checked


def _check_worked_numbers(failures: list[str]) -> int:
    """Every number ``coefficient-mass.tex`` works out by hand, exactly."""
    checks = 0

    def tail_of(rhos: list[int], zeros: list[int]) -> Fraction:
        nodes = sorted(Fraction(1, r) for r in rhos)
        return _tail(nodes, zeros, _certificate(nodes, zeros))

    # Section 2's two-node examples, and the fixed-node non-monotonicity.
    for rhos, zeros, want in (
        ([3, 2], [1], Fraction(1, 2)),
        ([3, 2], [2], Fraction(3, 10)),
        ([5, 3], [1], Fraction(1, 8)),
        ([5, 3], [2], Fraction(9, 64)),
    ):
        got = tail_of(rhos, zeros)
        if got != want:
            failures.append(f"Tail at {rhos}, Z={zeros} is {got}, not {want}")
        checks += 1

    # The cutoff witness after thm:tail.
    high = [Fraction(1, 10), Fraction(4, 5)]
    a = _certificate(high, [2])
    if a != [Fraction(64, 63), Fraction(-1, 63)]:
        failures.append(f"cutoff witness coefficients are {a}")
    if _tail(high, [2], a) != Fraction(364, 2835):
        failures.append("cutoff witness tail is not 364/2835")
    checks += 2

    # lem:consecutive: the h_j formula, term by term, at rational nodes.
    nodes = [Fraction(1, 7), Fraction(2, 9), Fraction(1, 3), Fraction(3, 5)]
    c = len(nodes)
    a = _certificate(nodes, list(range(1, c)))
    prod = Fraction(1)
    for y in nodes:
        prod *= y
    h = [Fraction(1)]  # h_j by the recurrence over the variables
    for _ in range(12):
        h.append(Fraction(0))
    for y in nodes:
        for j in range(1, len(h)):
            h[j] += y * h[j - 1]
    for d in range(c, c + len(h)):
        if _u(nodes, a, d) != (-1) ** (c + 1) * prod * h[d - c]:
            failures.append(f"lem:consecutive formula fails at d={d}")
    checks += len(h)

    # prop:sharp23: F_n is a monic multiple of (x-2)(x-3) with b_2 = t_n > 2.
    for n in range(2, 30):
        t = Fraction(2) / (1 - Fraction(2) ** (1 - n) + Fraction(3) ** -n)
        a_n = 2 + t * (1 - Fraction(2) ** -n)
        coeffs = [t] * n + [-a_n, Fraction(1)]  # ascending
        for r in (2, 3):
            if sum(cf * r**j for j, cf in enumerate(coeffs)) != 0:
                failures.append(f"F_{n}({r}) != 0")
        mags = sorted((abs(cf) for cf in coeffs[:-1]), reverse=True)
        if not (mags[1] == t > 2):
            failures.append(f"b_2(F_{n}) is not t_{n} > 2")
        checks += 1

    # The (x+1)P_2 example: coefficients 1, -4, 1, 6.
    p2 = [6, -5, 1]
    prod_poly = [p2[0], p2[0] + p2[1], p2[1] + p2[2], p2[2]]
    if prod_poly != [6, 1, -4, 1]:
        failures.append(f"(x+1)P_2 is {prod_poly}")
    checks += 1
    return checks


def _partial_sums(roots: list[Fraction]) -> list[Fraction]:
    """``S_0..S_m`` of ``prod (x - r)``, read down from the leading 1."""
    poly = [Fraction(1)]
    for r in roots:
        poly = [*poly, Fraction(0)]
        for i in range(len(poly) - 1, 0, -1):
            poly[i] -= r * poly[i - 1]
    sums, total = [], Fraction(0)
    for c in poly:
        total += c
        sums.append(total)
    return sums


def _elementary(values: list[Fraction]) -> list[Fraction]:
    e = [Fraction(1)]
    for v in values:
        e = [*e, Fraction(0)]
        for k in range(len(e) - 1, 0, -1):
            e[k] += v * e[k - 1]
    return e


def _check_converse(failures: list[str]) -> int:
    """The necessity half of the partial-sum criterion, ``thm:converse``.

    Exact checks of its three lemmas and its worked numbers: the signed
    partial-sum formula (``lem:signs``), the directional identity
    ``sum_{d>=n} delta_d = -S_j/Q(1)`` (``lem:improve``), the two failing
    indices of ``(x-2)P_1`` the ``u = 1, r_1 = 2`` case needs, and the
    ``(2,3,5,7)`` certificate whose tail ``31/1704`` beats ``1/48``.
    """
    from math import comb

    checks = 0
    rng = random.Random(SEED + 1)
    fails = 0
    for _ in range(300):
        m = rng.randint(1, 6)
        roots = sorted({Fraction(rng.randint(21, 120), 10) for _ in range(m)})
        m = len(roots)
        sums = _partial_sums(roots)
        e = _elementary([r - 1 for r in roots])
        for j in range(m):
            formula = sum(e[k] * comb(m - 1 - k, j - k) for k in range(j + 1))
            if (-1) ** j * sums[j] != formula or formula <= 0:
                failures.append(f"lem:signs formula at {roots}, j={j}")
        if (-1) ** m * sums[m] != e[m]:
            failures.append(f"lem:signs top sum at {roots}")
        checks += 1
        a = sums
        if any(abs(a[j]) > abs(a[m]) for j in range(1, m)):
            fails += 1
            full = _partial_sums([Fraction(2), *roots])
            bad = [j for j in range(1, m + 1) if abs(full[j]) > abs(full[m + 1])]
            if len(bad) < 2:
                failures.append(f"(x-2)P_1 has one failing index at {roots}")
    if not fails:
        failures.append("no failing root set drawn; the two-index check is blind")

    for rhos in ([3, 5, 7], [2, 3, 5, 7], [4, 5, 6, 7], [2, 3, 7]):
        n = len(rhos)
        nodes = [Fraction(1, r) for r in rhos]
        sums = _partial_sums([Fraction(r) for r in rhos])
        for j in range(1, n):
            delta = _solve(
                [[y**d for y in nodes] for d in range(n)],
                [Fraction(int(d == j)) for d in range(n)],
            )
            total = sum(ai / (1 - y) for ai, y in zip(delta, nodes, strict=True))
            head = sum(_u(nodes, delta, d) for d in range(n))
            if total - head != -sums[j] / sums[n]:
                failures.append(f"lem:improve identity at {rhos}, j={j}")
            checks += 1

    nodes = [Fraction(1, 3), Fraction(1, 5), Fraction(1, 7)]
    a = _certificate(nodes, [1, 3])
    if _tail(nodes, [1, 3], a) != Fraction(31, 1704) or not Fraction(
        31, 1704
    ) < Fraction(1, 48):
        failures.append("(3,5,7) certificate with zeros {1,3} is not 31/1704")
    if _partial_sums([Fraction(r) for r in (3, 5, 7)]) != [1, -14, 57, -48]:
        failures.append("(3,5,7) partial sums are not 1,-14,57,-48")
    return checks + 2


def main() -> int:
    failures: list[str] = []
    controls = _check_controls(failures)
    searches = _check_searches(failures)
    ordering = _check_ordering(failures)
    worked = _check_worked_numbers(failures)
    converse = _check_converse(failures)
    print(f"  positive controls fired                     : {controls}")
    print(f"  search optima equal their family members    : {searches}")
    print(f"  sharp235 ordering degrees checked exactly   : {ordering}")
    print(f"  worked numbers of the paper checked exactly : {worked}")
    print(f"  converse lemmas checked exactly             : {converse}")
    rng = random.Random(SEED)
    totals = {}
    for label, pool in _POOLS.items():
        stated, repaired, rev, dele = _sweep(pool, 150, rng, failures, label)
        totals[label] = (stated, repaired, rev, dele)
        print(
            f"  {label:<18} 150 draws: stated {stated:>3}, "
            f"repaired {repaired}, deletion reversed {rev}/{dele}"
        )

    below = totals["y <= 1/2"]
    if below[0]:
        failures.append(f"stated bound broken {below[0]}x below the cutoff")
    if below[2]:
        failures.append(f"deletion reversed {below[2]}x below the cutoff")
    if not any(totals[k][0] for k in totals if k != "y <= 1/2"):
        failures.append("no stated-bound violation above the cutoff; sweep is blind")
    if not any(totals[k][2] for k in totals if k != "y <= 1/2"):
        failures.append("no deletion reversal above the cutoff; sweep is blind")

    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        return 1
    print("  repaired bound unviolated; stated bound and deletion fail only above 1/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
