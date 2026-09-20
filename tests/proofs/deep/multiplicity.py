"""Machine checks backing the confluent slack certificate (Polynomial mass).

Run:  just proofs   (or python tests/proofs/deep/multiplicity.py)

``docs/polynomial.md`` proves "each leading zero buys one root" for an
exponential sum on *distinct* nodes, and the language bound
``Omega(T**2 / log T)`` follows only while the real instruction roots are
distinct.  A repeated root is legal (``(x-2)**3`` decodes to three ``[1]``
instructions), and the missing step is a mass bound that counts multiplicity.

The confluent analogue is::

    u_d = sum_i P_i(d) y_i^d,   deg P_i < e_i,   u_0 = 1,
    u_z = 0 for z in Z,   |Z| = c - 1,   c = sum e_i,

and the claim is the *same* tail bound with the product read over the expanded
multiset (each ``y_i`` repeated ``e_i`` times).  This module does not prove the
limit step -- that is the Hermite interpolation argument in
``notes/multiplicity/CONFLUENT_PROOF.md`` -- it pins the algebraic content:
the base case is exact, the general bound holds on every certificate here, the
slack assembly's threshold really is the product over the top units, and the
integer-root divisibility really does give the root-2 term.  Together those
give ``mass(F) >= (log10 2)/32 * m**2`` for every multiple.
"""

from __future__ import annotations

from fractions import Fraction

#: Cost band; see ``__main__.py``.  Exact rational solve of small confluent
#: systems plus a few integer products -- fast, but its place is CI where the
#: 20s budget already pays for ``all_generators``.
BAND = "ci"
COST = 1.0


def _solve(nodes: list[tuple[Fraction, int]], zeros: list[int]):
    """Coefficients q[i][k] of u_d = sum q[i][k] d^k y_i^d, u_0=1, u_z=0."""
    idx = [(i, k) for i, (_, e) in enumerate(nodes) for k in range(e)]
    n = len(idx)
    assert n == sum(e for _, e in nodes)
    assert len(zeros) == n - 1
    rows, rhs = [], []
    for d in [0, *zeros]:
        rows.append([Fraction(d**k) * nodes[i][0] ** d for i, k in idx])
        rhs.append(Fraction(1) if d == 0 else Fraction(0))
    a = [[*r, b] for r, b in zip(rows, rhs, strict=True)]
    for col in range(n):
        piv = next(r for r in range(col, n) if a[r][col] != 0)
        a[col], a[piv] = a[piv], a[col]
        pv = a[col][col]
        a[col] = [v / pv for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col], strict=True)]
    sol = [a[j][n] for j in range(n)]
    coeffs, p = [], 0
    for _, e in nodes:
        coeffs.append(sol[p : p + e])
        p += e
    return coeffs


def _u(nodes, coeffs, d: int) -> Fraction:
    return sum(
        sum(q * Fraction(d) ** k for k, q in enumerate(qs)) * y**d
        for (y, _), qs in zip(nodes, coeffs, strict=True)
    )


def _A(k: int, y: Fraction) -> Fraction:
    """``sum_{d>=0} d^k y^d`` for ``k <= 3``, exactly."""
    o = 1 - y
    if k == 0:
        return 1 / o
    if k == 1:
        return y / o**2
    if k == 2:
        return y * (1 + y) / o**3
    return y * (1 + 4 * y + y * y) / o**4


def _tail(nodes, coeffs, zeros) -> Fraction:
    """Exact ``sum_{d>=1}|u_d|``: constant sign past the last zero."""
    n = max(zeros) + 2
    head = sum(abs(_u(nodes, coeffs, d)) for d in range(1, n + 1))
    total = sum(
        q * _A(k, y)
        for (y, _), qs in zip(nodes, coeffs, strict=True)
        for k, q in enumerate(qs)
    )
    upto = sum(_u(nodes, coeffs, d) for d in range(0, n + 1))
    sign = 1 if _u(nodes, coeffs, n) > 0 else -1
    return head + sign * (total - upto)


def _expanded(nodes) -> list[Fraction]:
    z: list[Fraction] = []
    for y, e in nodes:
        z.extend([y] * e)
    return sorted(z)


def _leading_run(zeros) -> int:
    s, f = set(zeros), 0
    while f + 1 in s:
        f += 1
    return f


def _mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def _digits(n: int) -> int:
    return 0 if n == 0 else len(str(abs(n)))


def _mass(coeffs) -> int:
    return sum(_digits(c) for c in coeffs)


#: The certificates checked.  Small enough to stay inside the band budget, wide
#: enough to see one repeated node, two repeated nodes, a node at 1/2, and a
#: displaced zero set.
_CERTIFICATES = [
    ([(Fraction(1, 2), 2)], [1]),
    ([(Fraction(1, 3), 3)], [1, 3]),
    ([(Fraction(1, 3), 3)], [2, 4]),
    ([(Fraction(1, 4), 2), (Fraction(1, 2), 2)], [1, 2, 3]),
    ([(Fraction(1, 4), 2), (Fraction(1, 2), 2)], [1, 3, 4]),
    ([(Fraction(1, 5), 2), (Fraction(1, 3), 2)], [2, 3, 5]),
    ([(Fraction(1, 5), 2), (Fraction(1, 3), 2)], [1, 2, 6]),
    (
        [(Fraction(1, 6), 2), (Fraction(1, 4), 2), (Fraction(1, 2), 2)],
        [1, 2, 4, 5, 7],
    ),
]


def _check_certificates(failures: list[str]) -> int:
    for nodes, zeros in _CERTIFICATES:
        coeffs = _solve(nodes, zeros)
        assert _u(nodes, coeffs, 0) == 1
        for z in zeros:
            assert _u(nodes, coeffs, z) == 0
        t = _tail(nodes, coeffs, zeros)
        f = _leading_run(zeros)
        bound = Fraction(1)
        for y in _expanded(nodes)[: f + 1]:
            bound *= y / (1 - y)
        if t > bound:
            failures.append(f"tail {t} > bound {bound} for {nodes}, Z={zeros}")
    # base case is exact
    for nodes in (
        [(Fraction(1, 3), 3)],
        [(Fraction(1, 4), 2), (Fraction(1, 2), 2)],
    ):
        c = sum(e for _, e in nodes)
        zeros = list(range(1, c))
        coeffs = _solve(nodes, zeros)
        t = _tail(nodes, coeffs, zeros)
        exact = Fraction(1)
        for y, e in nodes:
            exact *= (y / (1 - y)) ** e
        if t != exact:
            failures.append(f"base tail {t} != {exact} for {nodes}")
    return len(_CERTIFICATES) + 2


def _check_assembly(failures: list[str]) -> int:
    """Threshold on the m-u largest units is the product over the top m-2u."""
    count = 0
    cases = [
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 0),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 1),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2)], 2),
        ([(Fraction(1, 2), 3), (Fraction(1, 3), 2), (Fraction(1, 5), 1)], 2),
    ]
    for nodes, u in cases:
        m = sum(e for _, e in nodes)
        rem, trimmed = u, []
        for y, e in sorted(nodes, key=lambda t: -t[0]):
            take = min(rem, e)
            rem -= take
            if e - take:
                trimmed.append((y, e - take))
        sub = sorted(trimmed)
        c = sum(e for _, e in sub)
        zeros = list(range(1, c))  # U = {1..u} subsets the early fill
        coeffs = _solve(sub, zeros)
        t = _tail(sub, coeffs, zeros)
        top = _expanded(nodes)[: m - 2 * u]
        prod = Fraction(1)
        for y in top:
            prod *= 1 / y - 1
        if 1 / t < prod:
            failures.append(f"assembly {1 / t} < {prod} for {nodes}, u={u}")
        count += 1
    return count


def _check_mass(failures: list[str]) -> int:
    """Integer-root divisibility and the final ``c m**2`` bound, exactly."""
    from math import log10

    count = 0
    for roots in ([(2, 3)], [(3, 4)], [(2, 2), (3, 2)]):
        f = [1]
        for r, e in roots:
            for _ in range(e):
                f = _mul(f, [1, -r])
        asc = list(reversed(f))
        for low in range(sum(e for _, e in roots)):
            div = 1
            for r, e in roots:
                if e > low:
                    div *= r ** (e - low)
            if asc[low] % div:
                failures.append(f"divisibility fails {roots} low={low}")
        mass, m = _mass(f), sum(e for _, e in roots)
        if mass < (log10(2) / 32) * m * m:
            failures.append(f"mass {mass} < c m^2 for {roots}")
        count += 1
    return count


def main() -> int:
    failures: list[str] = []
    certs = _check_certificates(failures)
    asm = _check_assembly(failures)
    mass = _check_mass(failures)
    print(f"  confluent certificates checked exactly : {certs}")
    print(f"  slack-assembly thresholds checked      : {asm}")
    print(f"  divisibility + mass(f) >= c m^2 cases  : {mass}")
    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        return 1
    print("  all confluent-slack-certificate checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
