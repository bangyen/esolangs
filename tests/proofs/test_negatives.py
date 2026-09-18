"""The limits ``docs/polynomial.md`` claims, as executable checks.

Most of that document's content is a measurement -- a ratio, a census, a
growth exponent.  Those belong in prose, where a stale number reads as a
stale number.  Pinning one in a rarely-run test hides it instead: the
suite goes green while the quantity it named has moved.

These are a different kind of claim.  Each says the system *cannot*
do something, and each of those absences is load-bearing -- an argument in
the document rests on it.  An absence is exactly what turns false silently
when someone improves the code, and when one of these does turn false it
is not a regression but an opening: the bound it supports is back in play.

So a failure here means "go read the paragraph this supports", not "revert
the change".  Each test names the paragraph.

Each was measured first by a scratch probe.  The probes were not tracked;
these checks are what the repository keeps of them, which is the point --
a claim worth relying on belongs somewhere that runs.
"""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from typing import ClassVar

import pytest
import sympy as sp
import z3

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.polynomial import (
    _parse_program,
    run,
    sanitize,
)
from esolangs.tools._polynomial import format_coeffs, multiply
from esolangs.tools.register import polynomial

# --------------------------------------------------------------------------
# Polynomial cannot ship a factored program
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` prices Polynomial's text as the *expanded*
# polynomial's coefficient digits.  The obvious escape is to ship the product
# form instead -- m factors, each O(log) characters, so O(m log m) text and no
# expansion at all.  The document rules that out on the parser's behaviour,
# and a silent misparse is what makes it a dead end rather than a feature
# request: the program still runs, just as a different program.


class TestFactoredProgramsAreMisread:
    """``f(x) = (x-2)(x-3)`` parses, and parses *wrong*.

    If this ever starts raising, or starts agreeing with the expanded form,
    the compact-encoding escape is open and the `Omega(T^2/(log T)^2)` text
    bound needs revisiting.
    """

    def test_the_expanded_form_is_read_as_written(self) -> None:
        assert sanitize("f(x) = x^2-5x^1+6") == [1, -5, 6]

    @pytest.mark.parametrize("code", ["f(x) = (x-2)(x-3)", "f(x) = (x-2)*(x-3)"])
    def test_a_product_is_accepted_rather_than_rejected(self, code: str) -> None:
        # The silence is the point: a rejection would be a clean signal.
        # ``*`` is stripped by the character filter, so both spellings land
        # in the same place.
        assert sanitize(code) is not None

    @pytest.mark.parametrize("code", ["f(x) = (x-2)(x-3)", "f(x) = (x-2)*(x-3)"])
    def test_a_product_decodes_to_a_different_polynomial(self, code: str) -> None:
        assert sanitize(code) != sanitize("f(x) = x^2-5x^1+6")

    def test_only_the_last_term_of_each_degree_survives(self) -> None:
        # The mechanism behind the misparse: ``_sanitize`` sums ``c*x^d``
        # monomials and never multiplies out, so ``(x-2)(x-3)`` is read as
        # the last term of each degree rather than as a product.
        assert sanitize("f(x) = (x-2)(x-3)") == [1, -3]
        assert sanitize("f(x) = (x-2)(x-3)(x-5)") == [1, -5]


# --------------------------------------------------------------------------
# Polynomial multiples cannot change what a program does
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` says extra roots that do not match an instruction
# code "may multiply the mandatory root product without changing execution".
# That premise carries the whole sparse-multiple frontier, so it is executed
# rather than asserted: built here, decoded here, and run here.

#: ``reg += 70 ; reg -= 5 ; output`` -- prints "A" (primes 2, 3, 5).
_A_PRINTER_FACTORS = (
    [1, -140, 70 * 70 + 4],  # (x-70)^2 + 2^2
    [1, 10, 25 + 9],  # (x+5)^2 + 3^2, a negative operand
    [1, 0, 25],  # x^2 + 5^2
)
_A_PRINTER_DECODED = [[70, 1], [-5, 1], [0, 1]]


def _a_printer() -> list[int]:
    base = [1]
    for factor in _A_PRINTER_FACTORS:
        base = multiply(base, factor)
    return base


class TestIgnoredRootMultiplesPreserveExecution:
    """Multiplying by a root that is not an instruction code changes nothing.

    If a cofactor here ever *does* change the decode, the sparse-multiple
    frontier narrows and the paragraph resting on it needs rereading.
    """

    @pytest.mark.parametrize(
        ("name", "cofactor"),
        [
            ("x^2 + x + 1, irreducible and the wrong quadratic shape", [1, 1, 1]),
            ("x - 6, linear with a root that is not a prime power", [1, -6]),
        ],
    )
    def test_a_shape_dodging_cofactor_leaves_the_program_alone(
        self, name: str, cofactor: list[int]
    ) -> None:
        code = format_coeffs(multiply(_a_printer(), cofactor))
        assert [list(d) for d in _parse_program(code)] == _A_PRINTER_DECODED, name
        io = ScriptedIO("")
        run(code, io)
        assert io.getvalue() == "A", name

    def test_the_control_changes_the_decode(self) -> None:
        # x - 2: the root 2 = 2^1 IS an instruction code, so this one must
        # decode differently.  Without it the tests above would pass on an
        # implementation that ignored cofactors entirely.
        code = format_coeffs(multiply(_a_printer(), [1, -2]))
        assert [list(d) for d in _parse_program(code)] != _A_PRINTER_DECODED

    def test_a_real_generator_artifact_survives_being_multiplied(self) -> None:
        table = "0110"
        program = polynomial(table)
        lifted = format_coeffs(multiply(sanitize(program), [1, 1, 1]))

        def rows(code: str) -> str:
            out = []
            for row in range(1 << 2):
                io = ScriptedIO("".join(f"{b}\n" for b in f"{row:02b}"))
                run(code, io)
                out.append(io.getvalue())
            return "".join(out)

        assert rows(program) == table
        assert rows(lifted) == table


# --------------------------------------------------------------------------
# Polynomial multiples: the second-largest coefficient is a primorial fraction
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` ("The tail is a primorial fraction") reports that a
# multiple of ``(x-2)(x-3)...`` whose every non-constant coefficient is small
# does not exist at any degree searched: the floor sits near ``0.4`` of the
# primorial and stops falling once the degree passes about twice the root
# count.  The one-big-coefficient profile the open row needs is the negation
# of this.  Exact, by z3, at the two smallest sizes where the floor has
# already flattened; the witness shows the *other* profile (two large
# coefficients, the rest at most 5) does exist, so the floor is about the
# maximum of the tail, not its count.


def _tail_fits(roots: tuple[int, ...], degree: int, height: int) -> bool:
    """Is there a nonzero ``S = sum_{j=1..degree} s_j x^j``, ``|s_j| <= height``,
    with ``S(r)`` equal at every root?  Then ``S - S(r_0)`` is a multiple."""
    solver = z3.Solver()
    solver.set("timeout", 60_000)
    coeffs = [z3.Int(f"s{j}") for j in range(1, degree + 1)]
    for c in coeffs:
        solver.add(c >= -height, c <= height)
    solver.add(z3.Or(*[c != 0 for c in coeffs]))
    values = [sum(c * r ** (j + 1) for j, c in enumerate(coeffs)) for r in roots]
    for value in values[1:]:
        solver.add(value == values[0])
    verdict = solver.check()
    assert verdict != z3.unknown
    return verdict == z3.sat


class TestTailHeightIsAPrimorialFraction:
    """Every non-constant coefficient small: impossible below ~0.4 primorial.

    If the ``unsat`` side ever turns ``sat``, a multiple with a single large
    coefficient exists at that size and the open row's profile is live.
    """

    @pytest.mark.parametrize(
        ("roots", "degree", "floor"),
        [((2, 3, 5), 8, 13), ((2, 3, 5, 7), 8, 82)],
    )
    def test_the_floor_is_exact(
        self, roots: tuple[int, ...], degree: int, floor: int
    ) -> None:
        assert not _tail_fits(roots, degree, floor - 1)
        assert _tail_fits(roots, degree, floor)

    def test_two_large_coefficients_with_a_tiny_rest_do_exist(self) -> None:
        # 3540 - 1012 x^2 + (2x - x^3 + 2x^5 + x^6 + 5x^7 - x^8): every other
        # coefficient at most 5.  Cheap in count, not in text: both large ones
        # are ~2^degree, and the tiny part fills every degree.
        coeffs = [3540, 2, -1012, -1, 0, 2, 1, 5, -1]
        for r in (2, 3, 5):
            assert sum(c * r**j for j, c in enumerate(coeffs)) == 0


def _remainder_fits(roots: tuple[int, ...], degree: int, low: int, height: int) -> bool:
    """Is there a multiple ``G + tau`` of ``prod (x - r)``: ``G`` free on degrees
    ``0..low``, ``tau`` nonzero on ``low+1..degree`` with ``|tau_j| <= height``?"""
    solver = z3.Solver()
    solver.set("timeout", 60_000)
    g = [z3.Int(f"g{j}") for j in range(low + 1)]
    tau = [z3.Int(f"t{j}") for j in range(low + 1, degree + 1)]
    for c in tau:
        solver.add(c >= -height, c <= height)
    solver.add(z3.Or(*[c != 0 for c in tau]))
    for r in roots:
        solver.add(
            sum(c * r**j for j, c in enumerate(g))
            + sum(c * r ** (j + low + 1) for j, c in enumerate(tau))
            == 0
        )
    verdict = solver.check()
    assert verdict != z3.unknown
    return verdict == z3.sat


class TestSparseRemainderNeedsTheLargestPrime:
    """``docs/polynomial.md`` ("The sparse-remainder profile"): above ``K <=
    L - 2`` unbounded low coefficients, some remainder coefficient is at
    least ``p_L - 1`` (divided-difference lemma), tight at ``L = 5``; and at
    ``L = 6`` with three unbounded low coefficients no remainder bounded by
    ``p_L = 13`` exists through degree 20 at all.
    """

    def test_the_lemma_threshold_is_tight_at_five_primes(self) -> None:
        assert not _remainder_fits((2, 3, 5, 7, 11), 18, 3, 10)
        assert _remainder_fits((2, 3, 5, 7, 11), 18, 3, 11)

    def test_six_primes_admit_no_remainder_bounded_by_the_largest(self) -> None:
        assert not _remainder_fits((2, 3, 5, 7, 11, 13), 20, 3, 13)


class TestIteratedEliminationThresholds:
    """``docs/polynomial.md`` ("The iterated elimination"): with the lowest
    ``K + 1`` coefficients free, some higher coefficient reaches
    ``prod_{i > K+1} (p_i - 1)``; unsat at the product, sat within 1.4x.
    """

    @pytest.mark.parametrize(
        ("roots", "degree", "low", "below", "above"),
        [
            ((2, 3, 5, 7, 11), 14, 2, 60, 80),
            # Z3's branch-and-bound search is CPU-bound.  Under `-n auto`,
            # this case exceeded the medium band's 15s CI ceiling (35.03s);
            # the weekly slow run is its stable home.
            pytest.param((2, 3, 5, 7, 11, 13), 16, 3, 120, 160, marks=pytest.mark.slow),
            # 2.3s alone, but z3 is CPU-bound and the bands measure wall
            # clock: under `-n auto` this one contends with the other
            # solver tests and reached 23s, past even the medium band's
            # scaled CI ceiling.  The band with headroom is the honest
            # home for it; the weekly run still checks it.
            pytest.param(
                (2, 3, 5, 7, 11, 13, 17), 16, 4, 192, 300, marks=pytest.mark.slow
            ),
        ],
    )
    def test_the_product_of_the_largest_primes_less_one(
        self, roots: tuple[int, ...], degree: int, low: int, below: int, above: int
    ) -> None:
        assert not _remainder_fits(roots, degree, low, below)
        assert _remainder_fits(roots, degree, low, above)


# --------------------------------------------------------------------------
# Polynomial: the finite-degree certificate and the c = 2 termwise inequality
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` ("The iterated elimination") states two measured
# inequalities that a language lower bound would need proved for every
# degree.  Both are exact-rational computations, so they are pinned here at
# the sizes they were measured; a failure names the degree.


def _h_table(roots: tuple[int, ...], smax: int) -> list[int]:
    """Complete homogeneous symmetric polynomials ``h_0..h_smax`` of ``roots``."""
    h = [1] + [0] * smax
    for x in roots:
        for s in range(1, smax + 1):
            h[s] = h[s] + x * h[s - 1]
    return h


def _certificate_threshold(roots: tuple[int, ...], low: int, degree: int) -> Fraction:
    """``1 / tail`` of the row-space certificate with ``c - 1`` zeros under the
    top, ``c = L - low - 1``; the profile with the lowest ``low + 1``
    coefficients free is infeasible below it (Farkas)."""
    qs = list(range(low + 1, len(roots)))
    c = len(qs)
    h = _h_table(roots, degree)

    def at(s: int) -> int:
        return h[s] if s >= 0 else 0

    rows = [[at(degree - d - q) for q in qs] for d in range(c)]
    lam = sp.Matrix(rows).LUsolve(sp.Matrix([1] + [0] * (c - 1)))
    lam = [Fraction(int(x.p), int(x.q)) for x in lam]
    w = {
        m: sum(lam[i] * at(m - q) for i, q in enumerate(qs))
        for m in range(low + 1, degree + 1)
    }
    assert w[degree] == 1
    assert all(w[degree - d] == 0 for d in range(1, c))
    return 1 / sum(abs(w[m]) for m in range(low + 1, degree - c + 1))


class TestFiniteDegreeCertificateDominatesTheLimit:
    """The exact-degree certificate is never below ``prod (p_i - 1)`` over the
    largest primes -- measured, and what a proof of (b) must give."""

    @pytest.mark.parametrize(
        ("roots", "low", "degrees"),
        [
            ((2, 3, 5, 7, 11), 0, range(5, 41)),
            ((2, 3, 5, 7, 11), 2, range(5, 41)),
            ((2, 3, 5, 7, 11, 13), 3, range(6, 41)),
            ((2, 3, 5, 7, 11, 13, 17), 0, range(7, 41)),
            ((2, 3, 5, 7, 11, 13, 17), 4, range(7, 41)),
        ],
    )
    def test_never_below(
        self, roots: tuple[int, ...], low: int, degrees: range
    ) -> None:
        limit = math.prod(p - 1 for p in roots[low + 1 :])
        for degree in degrees:
            assert _certificate_threshold(roots, low, degree) >= limit, degree


class TestTwoLargestRootsTermwise:
    """``c = 2``: with ``Q = h(all roots)``, ``a < b`` the two largest,
    ``Q_{n-d} Q_{n-1} - Q_{n-d-1} Q_n <= psi_d (Q_n^2 - Q_{n-1} Q_{n+1})``,
    ``psi_d = (a^-d - b^-d) / (b - a)``; an identity when only ``a, b`` are
    present.  Summed over ``d`` it is the ``c = 2`` case of (b)."""

    @pytest.mark.parametrize(
        "roots", [(2, 3, 5), (2, 3, 5, 7, 11), (2, 3, 5, 7, 11, 13)]
    )
    def test_holds_to_n_30(self, roots: tuple[int, ...]) -> None:
        a, b = roots[-2], roots[-1]
        q = _h_table(roots, 32)
        for n in range(2, 31):
            top = q[n] * q[n] - q[n - 1] * q[n + 1]
            assert top > 0
            for d in range(1, n):
                psi = (Fraction(1, a**d) - Fraction(1, b**d)) / (b - a)
                left = q[n - d] * q[n - 1] - q[n - d - 1] * q[n]
                assert 0 <= left <= psi * top, (n, d)


class TestConvolutionStepOfTheTwoRootTheorem:
    """``docs/polynomial.md`` ("The two largest roots, every degree"): the
    induction step.  Adding a root ``x`` convolves ``Q`` with ``(1, x, x^2,
    ...)``; by Cauchy--Binet every 2x2 minor of the new Toeplitz matrix on
    columns ``{0, s}`` is ``sum_{k1 < s <= k2} x^(k1 + k2 - s)`` times the old
    minor on columns ``{k1, k2}``, the same weights for both row pairs, and
    the s-uniform inequality passes through.  Checked exactly, and the
    inequality itself with the pure base an identity in the interior.
    """

    @staticmethod
    def _minor(q: list[int], r1: int, r2: int, c1: int, c2: int) -> int:
        def at(m: int) -> int:
            return q[m] if m >= 0 else 0

        return at(r1 - c1) * at(r2 - c2) - at(r1 - c2) * at(r2 - c1)

    def test_cauchy_binet_weights_are_shared_by_both_row_pairs(self) -> None:
        q = _h_table((3, 5, 7), 40)
        x = 2
        q2 = _h_table((2, 3, 5, 7), 40)
        for n in range(2, 20):
            for d in range(1, n):
                for s in range(1, 8):
                    for rows in ((n - d, n), (n, n + 1)):
                        expanded = sum(
                            x ** (k1 + k2 - s) * self._minor(q, *rows, k1, k2)
                            for k1 in range(s)
                            for k2 in range(s, n + 2)
                        )
                        assert expanded == self._minor(q2, *rows, 0, s), (n, d, s, rows)

    @pytest.mark.parametrize(
        ("small", "a", "b"),
        [((), 2, 3), ((2,), 3, 5), ((2, 3, 5), 7, 11), ((10,), 11, 13)],
    )
    def test_s_uniform_inequality(self, small: tuple[int, ...], a: int, b: int) -> None:
        q = _h_table((*small, a, b), 26)
        hab = _h_table((a, b), 26)
        equalities = 0
        for n in range(1, 24):
            for d in range(1, n + 1):
                psi = Fraction(hab[d - 1], (a * b) ** d)
                for s in range(1, n + 2):
                    left = self._minor(q, n - d, n, 0, s)
                    right = self._minor(q, n, n + 1, 0, s)
                    assert 0 <= left <= psi * right, (n, d, s)
                    equalities += left == psi * right and right > 0
        assert (equalities > 0) == (small == ())


# --------------------------------------------------------------------------
# Polynomial: no multiple is lighter than the product itself
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` ("Total mass"): over every integer cofactor of the
# degrees searched, the least coefficient-digit mass of a multiple of the
# first L primes' product is the product's own.  That mass is
# Theta(L^2 log L), so the iterated elimination's target is the truth at
# every size measured.  Exact, by z3 bisection on a digit budget.


def _digit_mass(coeffs: list[int]) -> int:
    return sum(len(str(abs(c))) for c in coeffs if c)


def _product(roots: tuple[int, ...]) -> list[int]:
    p = [1]
    for r in roots:
        q = [0] * (len(p) + 1)
        for i, c in enumerate(p):
            q[i] -= r * c
            q[i + 1] += c
        p = q
    return p


def _lighter_multiple_exists(roots: tuple[int, ...], degree: int, budget: int) -> bool:
    """Is there a nonzero integer multiple of degree <= ``degree`` whose
    coefficient digits sum to at most ``budget``?"""
    p = _product(roots)
    low = len(p) - 1
    solver = z3.Solver()
    solver.set("timeout", 60_000)
    m = [z3.Int(f"m{j}") for j in range(degree - low + 1)]
    for v in m:
        solver.add(v >= -(10**budget), v <= 10**budget)
    solver.add(z3.Or(*[v != 0 for v in m]))
    cost = 0
    for k in range(degree + 1):
        fk = sum(p[i] * m[k - i] for i in range(low + 1) if 0 <= k - i <= degree - low)
        solver.add(fk <= 10**budget - 1, fk >= -(10**budget - 1))
        bits = [z3.Bool(f"b{k}_{j}") for j in range(budget)]
        for j, b in enumerate(bits):
            solver.add(z3.Or(b, z3.And(fk <= 10**j - 1, fk >= -(10**j - 1))))
            if j:
                solver.add(z3.Implies(b, bits[j - 1]))
        cost = cost + sum(z3.If(b, 1, 0) for b in bits)
    solver.add(cost <= budget)
    verdict = solver.check()
    assert verdict != z3.unknown
    return verdict == z3.sat


class TestNoMultipleIsLighterThanTheProduct:
    @pytest.mark.parametrize(
        ("roots", "degree"),
        [
            ((2, 3, 5), 8),
            ((2, 3, 5, 7), 6),
            ((2, 3, 5, 7, 11), 7),
            pytest.param((2, 3, 5, 7, 11, 13), 8, marks=pytest.mark.medium),
            pytest.param((2, 3, 5, 7, 11, 13, 17), 9, marks=pytest.mark.medium),
        ],
    )
    def test_the_product_is_the_minimum(
        self, roots: tuple[int, ...], degree: int
    ) -> None:
        dense = _digit_mass(_product(roots))
        assert not _lighter_multiple_exists(roots, degree, dense - 1)
        assert _lighter_multiple_exists(roots, degree, dense)

    def test_the_product_has_u_plus_one_coefficients_over_each_threshold(self) -> None:
        # The iterated elimination's assembled statement, on the only
        # minimal-mass witness: at least u+1 coefficients below the top reach
        # prod_{i>u} (p_i - 1), tight at u = L-3, L-2.
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        for count in range(3, 13):
            roots = tuple(primes[:count])
            below = [abs(c) for c in _product(roots)[:-1]]
            for u in range(count - 1):
                threshold = math.prod(p - 1 for p in roots[u:])
                assert sum(1 for c in below if c >= threshold) >= u + 1, (count, u)


def _lighter_real_multiple_exists(
    roots: tuple[int, ...], degree: int, budget: int
) -> bool:
    """Real relaxation: monic real cofactor, a coefficient below 1 costs nothing,
    ``digits(f) = #{j >= 0 : |f| >= 10^j}``; is the digit sum at most ``budget``?"""
    p = _product(roots)
    low = len(p) - 1
    solver = z3.Solver()
    solver.set("timeout", 60_000)
    m = [z3.Real(f"m{j}") for j in range(degree - low + 1)]
    solver.add(m[-1] == 1)
    cost = 0
    for k in range(degree + 1):
        fk = sum(p[i] * m[k - i] for i in range(low + 1) if 0 <= k - i <= degree - low)
        bits = [z3.Bool(f"b{k}_{j}") for j in range(budget + 1)]
        for j, b in enumerate(bits):
            solver.add(z3.Or(b, z3.And(fk < 10**j, fk > -(10**j))))
            if j:
                solver.add(z3.Implies(b, bits[j - 1]))
        solver.add(z3.Not(bits[budget]))
        cost = cost + sum(z3.If(b, 1, 0) for b in bits)
    solver.add(cost <= budget)
    verdict = solver.check()
    assert verdict != z3.unknown
    return verdict == z3.sat


class TestTheRealRelaxationIsAsHeavy:
    """``docs/polynomial.md`` ("Real against integer"): over real monic
    cofactors the least digit mass is the product's own less one -- the one
    digit that free sub-unit coefficients buy -- so the linear-programming
    route is sound and integrality is not where the bound lives."""

    @pytest.mark.parametrize(
        ("roots", "degree"), [((2, 3, 5), 5), ((2, 3, 5, 7), 6), ((2, 3, 5, 7, 11), 7)]
    )
    def test_one_digit_under_the_product(
        self, roots: tuple[int, ...], degree: int
    ) -> None:
        dense = _digit_mass(_product(roots))
        assert not _lighter_real_multiple_exists(roots, degree, dense - 2)
        assert _lighter_real_multiple_exists(roots, degree, dense - 1)


class TestCountStatementsOnAdversarialWitnesses:
    """The count form of gap (a) on the z3 minimisers of earlier rounds (each
    an exact multiple, re-verified here): at least ``u + 1`` coefficients
    below the top reach ``prod_{i>u} (p_i - 1)`` (weak) and even
    ``prod_{i>u} p_i / 2`` (strong), the strong count exactly ``u + 1`` at
    ``u = 0`` on the tail-height minimisers."""

    WITNESSES: ClassVar = [
        ((2, 3, 5), [-60, 2, 12, 13, -8, 1, 0, 0, 0]),
        ((2, 3, 5, 7), [-3360, -38, -73, -42, 2, 78, 80, 36, -56, 14, -1]),
        (
            (2, 3, 5, 7, 11),
            [-34650, 15, 593, -677, 92, 855, 802, 316, -652, 210, -25, 1],
        ),
        (
            (2, 3, 5, 7),
            [
                -12885390,
                6507873,
                -49,
                -12,
                -17,
                -30,
                -21,
                -36,
                -42,
                -15,
                -32,
                -23,
                -24,
                11,
                -1,
            ],
        ),
        (
            (2, 3, 5, 7, 11),
            [
                3161833290,
                -2646414393,
                532793472,
                55,
                67,
                -52,
                63,
                64,
                -54,
                -1,
                54,
                -27,
                -75,
                18,
                -1,
            ],
        ),
        (
            (2, 3, 5, 7, 11, 13),
            [
                -12348183267420,
                12824797280984,
                -4170337811545,
                422492795974,
                112,
                117,
                -93,
                89,
                -81,
                12,
                -50,
                -77,
                -140,
                -3,
                -142,
                24,
                -1,
            ],
        ),
    ]

    @pytest.mark.parametrize(("roots", "coeffs"), WITNESSES)
    def test_counts(self, roots: tuple[int, ...], coeffs: list[int]) -> None:
        for r in roots:
            assert sum(c * r**k for k, c in enumerate(coeffs)) == 0
        top = max(k for k, c in enumerate(coeffs) if c)
        below = [abs(c) for c in coeffs[:top]]
        for u in range(len(roots)):
            weak = math.prod(p - 1 for p in roots[u:])
            strong = math.prod(roots[u:])
            assert sum(1 for c in below if c >= weak) >= u + 1, ("weak", u)
            assert sum(1 for c in below if 2 * c >= strong) >= u + 1, ("strong", u)


class TestThreeRootHypothesisAtTheBoundary:
    """``docs/polynomial.md`` ("General c"): the s-uniform hypothesis for
    ``c = 3`` designated roots -- rows ``{n-d, n-1, n}`` against ``{n-1, n,
    n+1}``, every column set, ``psi_d = h_{d-2}(1/rho) / prod rho`` -- an
    equality in the interior, measured at the truncation boundary, and
    the one statement gap (b) still needs for ``c >= 3`` -- of the sharp
    form only; the slack certificate forms no truncated Toeplitz minor."""

    @pytest.mark.parametrize(
        ("small", "rho"), [((), (2, 3, 5)), ((2,), (3, 5, 7)), ((2, 3), (5, 7, 11))]
    )
    def test_measured_to_n_10(
        self, small: tuple[int, ...], rho: tuple[int, ...]
    ) -> None:
        q = _h_table((*small, *rho), 14)
        hinv = _h_table(tuple(Fraction(1, p) for p in rho), 14)
        prod_rho = math.prod(rho)

        def at(m: int) -> int:
            return q[m] if m >= 0 else 0

        def minor(rows: list[int], cols: list[int]) -> int:
            return sp.Matrix([[at(r - k) for k in cols] for r in rows]).det()

        interior_equalities = 0
        for n in range(2, 11):
            rows_b = [n - 1, n, n + 1]
            for d in range(2, n):
                rows_a = [n - d, n - 1, n]
                psi = hinv[d - 2] / prod_rho
                for c1 in range(1, 6):
                    for c2 in range(c1 + 1, 7):
                        cols = [0, c1, c2]
                        left, right = minor(rows_a, cols), minor(rows_b, cols)
                        assert 0 <= left <= psi * right, (n, d, cols)
                        if n - d >= c2 and left == psi * right:
                            interior_equalities += 1
        assert (interior_equalities > 0) == (small == ())


def _certificate_tail(
    rho: tuple[int, ...], zeros: tuple[int, ...], horizon: int = 100
) -> Fraction:
    """``u_d = sum a_i rho_i^-d`` with ``u_0 = 1`` and ``u_z = 0`` on ``zeros``
    (``len(zeros) == len(rho) - 1``); returns an upper bound on
    ``sum_{d >= 1, d not in zeros} |u_d|`` (exact to ``horizon``, geometric
    remainder beyond)."""
    rows = [[Fraction(1)] * len(rho)] + [
        [Fraction(1, r) ** z for r in rho] for z in zeros
    ]
    sol = sp.Matrix(rows).LUsolve(sp.Matrix([1] + [0] * len(zeros)))
    a = [Fraction(int(x.p), int(x.q)) for x in sol]
    total = sum(
        abs(sum(ai * Fraction(1, r) ** d for ai, r in zip(a, rho, strict=True)))
        for d in range(1, horizon + 1)
        if d not in zeros
    )
    # Past the last prescribed zero the sum is one-signed (a c-term
    # exponential sum has no other zeros), so the remainder is exact.
    assert horizon > max(zeros)
    remainder = abs(
        sum(
            ai * Fraction(1, r) ** (horizon + 1) / (1 - Fraction(1, r))
            for ai, r in zip(a, rho, strict=True)
        )
    )
    return total + remainder


class TestEachLeadingZeroBuysOneRoot:
    """``docs/polynomial.md`` ("The slack certificate"): for the pure
    exponential sum on ``c`` roots with ``c - 1`` prescribed zeros, of which
    the first ``f`` are at distances ``1..f``, the tail is at most
    ``1 / prod (rho - 1)`` over the ``f + 1`` largest roots, with equality
    when every zero is a leading one.  Proved there; the proof's own links
    are pinned by :class:`TestLeadingZeroTheoremProof`, and this is the
    statement they assemble to, checked exhaustively on small zero sets."""

    @pytest.mark.parametrize("rho", [(5, 7, 11), (3, 5, 7, 11), (7, 11, 13, 17)])
    def test_measured(self, rho: tuple[int, ...]) -> None:
        c = len(rho)
        largest_first = sorted(rho, reverse=True)
        equalities = 0
        for zeros in itertools.combinations(range(1, 9), c - 1):
            lead = 0
            while lead + 1 in zeros:
                lead += 1
            bound = Fraction(1, math.prod(r - 1 for r in largest_first[: lead + 1]))
            tail = _certificate_tail(rho, zeros)
            assert tail <= bound, zeros
            equalities += tail == bound
        assert equalities == 1  # only the all-leading set

    @pytest.mark.parametrize(
        ("count", "free"), [(6, 1), (6, 2), (7, 2), (7, 3), (8, 3)]
    )
    def test_free_positions_anywhere_reach_the_slack_threshold(
        self, count: int, free: int
    ) -> None:
        # Free set U of size u anywhere under the top: the certificate on the
        # L - u largest roots with zeros at U plus the first L - 2u - 1 free
        # distances is top-heavy at prod_{i > 2u} (p_i - 1) or better.
        primes = (2, 3, 5, 7, 11, 13, 17, 19)[:count]
        rho = primes[free:]
        target = math.prod(p - 1 for p in primes[2 * free :])
        for free_set in itertools.combinations(range(1, 8), free):
            zeros = set(free_set)
            d = 1
            while len(zeros) < len(rho) - 1:
                zeros.add(d) if d not in zeros else None
                d += 1
            assert 1 / _certificate_tail(rho, tuple(sorted(zeros))) >= target, free_set


class TestOneDisplacedZeroIsProved:
    """``docs/polynomial.md`` ("One displaced zero"): with zeros at ``1..c-2``
    and one more at ``z``, the certificate is ``F + lambda G`` (``F`` the
    leading-zero certificate on the ``c - 1`` largest roots, ``G`` the
    ``c``-root sum vanishing at ``0..c-2``), ``u_d = sigma P (h'_d - r_z h_d)``,
    and ``tail <= prod`` over the ``c - 1`` largest roots follows from
    ``y_c <= 1/2``.  The identity and the inequality, exactly.  This is the
    ``k = 1``, all-leading-``Z'`` case of the theorem, where the peel's
    ``Delta`` vanishes identically and (C) is an identity."""

    @pytest.mark.parametrize(
        "rho", [(5, 7, 11), (3, 5, 7, 11), (2, 3, 5, 7), (5, 7, 11, 13, 17)]
    )
    def test_identity_and_bound(self, rho: tuple[int, ...]) -> None:
        c = len(rho)
        y = [
            Fraction(1, r) for r in rho
        ]  # rho descending is not assumed: sort y ascending
        y.sort()
        top = y[:-1]  # the c - 1 largest roots
        horizon = 80
        h_all = _h_table(tuple(y), horizon)
        h_top = _h_table(tuple(top), horizon)
        product = math.prod(top)
        bound = math.prod(v / (1 - v) for v in top)
        roots_sorted = tuple(sorted(rho, reverse=True))
        for z in range(c - 1, 30):
            zeros = (*range(1, c - 1), z)
            a = sp.Matrix(
                [[Fraction(1)] * c] + [[v**w for v in y] for w in zeros]
            ).LUsolve(sp.Matrix([1] + [0] * (c - 1)))
            a = [Fraction(int(x.p), int(x.q)) for x in a]
            ratio = Fraction(h_top[z - c + 1]) / Fraction(h_all[z - c + 1])
            for d in range(c - 1, 50):
                u_d = sum(ai * v**d for ai, v in zip(a, y, strict=True))
                assert u_d == (-1) ** c * product * (
                    h_top[d - c + 1] - ratio * h_all[d - c + 1]
                )
            assert _certificate_tail(roots_sorted, zeros) <= bound


def _exp_sum(y: list[Fraction], zeros: tuple[int, ...], unit_at: int | None):
    """Coefficients of the exponential sum on ``y`` with the given zeros, normalised
    to value 1 at ``unit_at`` (``None`` means at 0)."""
    rows = [[v ** (0 if unit_at is None else unit_at) for v in y]]
    rows += [[v**z for v in y] for z in zeros]
    sol = sp.Matrix(rows).LUsolve(sp.Matrix([1] + [0] * len(zeros)))
    return [Fraction(int(x.p), int(x.q)) for x in sol]


class TestTriangleSlackIsBounded:
    """``docs/polynomial.md`` ("What the earlier rounds leave behind"): the
    lossy induction the peel superseded.  ``u = F + lambda G`` with
    ``F`` on the ``c - 1`` largest roots carrying all zeros but the last
    displaced one and ``G`` the ``c``-root sum vanishing at ``0`` and those;
    the triangle term ``|lambda| tail(G)`` is at most ``0.7 bound(f)`` (0.53,
    0.58, 0.61, 0.64 at ``c = 3..6``), worst with one displaced zero just
    past the fill, and ``|F_d / G_d|`` decreases past the last prescribed
    zero.  Kept as the record of the route: step 3's identity is exact where
    this triangle inequality was lossy, so the two sub-lemmas it needed are
    no longer a dependency of the bound."""

    @pytest.mark.parametrize(
        "count",
        [
            3,
            4,
            pytest.param(5, marks=pytest.mark.medium),
            pytest.param(6, marks=pytest.mark.medium),
        ],
    )
    def test_slack_and_monotone_ratio(self, count: int) -> None:
        primes = (3, 5, 7, 11, 13, 17)[:count]
        y = sorted(Fraction(1, p) for p in primes)
        worst = Fraction(0)
        for f in range(count - 1):
            k = count - 1 - f
            lead = tuple(range(1, f + 1))
            bound = math.prod(v / (1 - v) for v in y[: f + 1])
            for disp in itertools.combinations(range(f + 2, f + 2 + 9), k):
                a_f = _exp_sum(y[:-1], lead + disp[:-1], None)
                a_g = _exp_sum(y, (0, *lead, *disp[:-1]), disp[-1])
                horizon = disp[-1] + 50

                def f_at(d: int, a: list[Fraction] = a_f) -> Fraction:
                    return sum(ai * v**d for ai, v in zip(a, y[:-1], strict=True))

                def g_at(d: int, a: list[Fraction] = a_g) -> Fraction:
                    return sum(ai * v**d for ai, v in zip(a, y, strict=True))

                tail_g = sum(
                    abs(g_at(d)) for d in range(1, horizon) if d not in lead + disp
                )
                tail_g += abs(
                    sum(ai * v**horizon / (1 - v) for ai, v in zip(a_g, y, strict=True))
                )
                worst = max(worst, abs(f_at(disp[-1])) * tail_g / bound)
                last = disp[-2] if k > 1 else f
                ratios = [
                    abs(f_at(d)) / abs(g_at(d)) for d in range(last + 1, last + 20)
                ]
                assert all(a >= b for a, b in itertools.pairwise(ratios))
        assert worst < Fraction(7, 10)


class TestConvolutionRelationIsOneDisplacedOnly:
    """``docs/polynomial.md`` ("What the earlier rounds leave behind"): ``G``
    is a convolution of ``F`` only when the zeros are one consecutive run
    (``k = 1``); with a second displaced zero the ratio ``G_d / (F * geo)_d``
    is not constant.  That is step 5's ``p = 0`` dichotomy: the convolution
    is the identity case, and (C) is the inequality that replaces it
    everywhere else.  ``|F|`` is log-concave past its last prescribed zero
    either way."""

    def test_k1_relation_and_its_failure_at_k2(self) -> None:
        y = sorted(Fraction(1, p) for p in (3, 5, 7, 11))
        y_c = y[-1]

        def conv(f_at, d: int) -> Fraction:
            return sum(y_c**j * f_at(d - j) for j in range(d))

        def make(zeros: tuple[int, ...]):
            a_f = _exp_sum(y[:-1], zeros, None)
            a_g = _exp_sum(y, (0, *zeros), max(zeros) + 1)
            f_at = lambda d: sum(ai * v**d for ai, v in zip(a_f, y[:-1], strict=True))  # noqa: E731
            g_at = lambda d: sum(ai * v**d for ai, v in zip(a_g, y, strict=True))  # noqa: E731
            return f_at, g_at

        f_at, g_at = make((1, 2))  # k = 1: zeros 1..c-2
        ratios = {g_at(d) / conv(f_at, d) for d in range(3, 12)}
        assert len(ratios) == 1
        f_at, g_at = make((1, 4))  # k = 2
        ratios = {g_at(d) / conv(f_at, d) for d in range(5, 12)}
        assert len(ratios) > 1
        vals = [abs(f_at(d)) for d in range(5, 30)]
        assert all(
            b * b >= a * c for a, b, c in zip(vals, vals[1:], vals[2:], strict=False)
        )


class TestPointADecomposition:
    """``docs/polynomial.md`` ("What the earlier rounds leave behind"): the
    Lagrange-basis decomposition the peel superseded, whose ``B``-pieces
    would not split.  ``E_d = G_d - y_c G_{d-1}`` is a ``(c-1)``-root sum vanishing
    on the leading zeros with ``E_{z_j} = -y_c G_{z_j - 1}``, it equals
    ``mu F + sum_j E_{z_j} B_j`` on the Lagrange basis exactly, and ``G_d =
    sum_{i<d} y_c^i E_{d-i}`` recovers ``G``.  The triangle sum over these
    pieces stays under ``0.5 bound(f)`` while its ``B``-pieces are products
    of an unbounded tail and a vanishing ratio."""

    def test_identities_and_bound_sum(self) -> None:
        y = sorted(Fraction(1, p) for p in (3, 5, 7, 11, 13))
        y_c = y[-1]
        worst = Fraction(0)
        for f, disp in [
            (0, (2, 5, 7, 9)),
            (1, (3, 4, 6)),
            (1, (4, 7, 12)),
            (2, (5, 6)),
            (2, (4, 9)),
        ]:
            lead = tuple(range(1, f + 1))
            z_k = disp[-1]
            a_f = _exp_sum(y[:-1], lead + disp[:-1], None)
            a_g = _exp_sum(y, (0, *lead, *disp[:-1]), z_k)
            a_e = [ai * (1 - y_c / v) for ai, v in zip(a_g[:-1], y[:-1], strict=True)]

            def val(a: list[Fraction], roots: list[Fraction], d: int) -> Fraction:
                return sum(ai * v**d for ai, v in zip(a, roots, strict=True))

            for d in range(1, 14):
                assert val(a_e, y[:-1], d) == val(a_g, y, d) - y_c * val(a_g, y, d - 1)
                assert val(a_g, y, d) == sum(
                    y_c**i * val(a_e, y[:-1], d - i) for i in range(d)
                )
            basis = []
            for j, z_j in enumerate(disp[:-1]):
                others = tuple(z for i, z in enumerate(disp[:-1]) if i != j)
                basis.append(_exp_sum(y[:-1], (0, *lead, *others), z_j))
            mu = val(a_e, y[:-1], 0)
            for d in range(0, 16):
                recon = mu * val(a_f, y[:-1], d) + sum(
                    val(a_e, y[:-1], z_j) * val(b, y[:-1], d)
                    for z_j, b in zip(disp[:-1], basis, strict=True)
                )
                assert recon == val(a_e, y[:-1], d)
            bound = math.prod(v / (1 - v) for v in y[: f + 1])
            horizon = z_k + 40

            def tail1(
                a: list[Fraction], roots: list[Fraction], horizon: int = horizon
            ) -> Fraction:
                s = sum(abs(val(a, roots, d)) for d in range(1, horizon))
                return s + abs(
                    sum(
                        ai * v**horizon / (1 - v)
                        for ai, v in zip(a, roots, strict=True)
                    )
                )

            pref = abs(val(a_f, y[:-1], z_k)) * y_c / (1 - y_c)
            total = pref * abs(val(a_g, y, -1)) * tail1(a_f, y[:-1])
            total += sum(
                pref * abs(val(a_g, y, z_j - 1)) * tail1(b, y[:-1])
                for z_j, b in zip(disp[:-1], basis, strict=True)
            )
            worst = max(worst, total / bound)
        assert worst < Fraction(1, 2)


# --------------------------------------------------------------------------
# The leading-zero theorem, link by link
# --------------------------------------------------------------------------
#
# ``docs/polynomial.md`` ("The slack certificate") proves the lemma the whole
# language bound rests on, by peeling one root and one zero at a time.  The
# five steps are an identity, an equivalence, two inequalities and a zero
# count; each is exact, so each is pinned rather than measured.  A failure
# here is not a stale number -- it is the bound.


def _val(a: list[Fraction], y: list[Fraction], d: int) -> Fraction:
    """``v_d = sum_i a_i y_i**d``."""
    return sum(ai * v**d for ai, v in zip(a, y, strict=True))


def _from(a: list[Fraction], y: list[Fraction], m: int) -> Fraction:
    """``sum_{d >= m} v_d``, in closed form."""
    return sum(ai * v**m / (1 - v) for ai, v in zip(a, y, strict=True))


def _abs_tail(a: list[Fraction], y: list[Fraction], zeros: tuple[int, ...]) -> Fraction:
    """``sum_{d >= 1} |v_d|``: term by term to the last zero, then the
    one-signed remainder in closed form (step 0: a ``c``-term sum has no zero
    past the last prescribed one)."""
    top = max(zeros, default=0)
    return sum(abs(_val(a, y, d)) for d in range(1, top + 1)) + abs(
        _from(a, y, top + 1)
    )


def _leading_run(zeros: tuple[int, ...]) -> int:
    """``f``: the largest ``f`` with ``1..f`` all in ``zeros``."""
    f = 0
    while f + 1 in zeros:
        f += 1
    return f


class TestLeadingZeroTheoremProof:
    """``docs/polynomial.md`` ("The slack certificate"): the peel, exactly.

    With ``z = max Z`` displaced, ``Z' = Z \\ {z}``, ``m = max Z'``, ``F`` the
    certificate on the ``c - 1`` largest roots with zeros ``Z'`` and ``F_0 =
    1``, and ``G`` the ``c``-root sum vanishing on ``{0} u Z'`` with ``G_z =
    1``, the theorem reduces to ``tail(u) <= tail(F)`` and that to a zero
    count.  Checked here in exact rationals: step 3's identity, step 4's
    equivalence and the two inequalities (C) and (D), and step 5's structure
    for ``Delta``.
    """

    HORIZON: ClassVar[int] = 24

    @pytest.mark.parametrize(
        ("rho", "reach"),
        [
            ((11, 7, 5), 11),
            ((11, 7, 5, 3), 8),
            ((7, 5, 3, 2), 8),
            ((17, 13, 11, 7, 5), 8),
        ],
    )
    def test_every_link(self, rho: tuple[int, ...], reach: int) -> None:
        y = sorted(Fraction(1, r) for r in rho)  # ascending: y_c = 1/min(rho)
        c = len(y)
        y_c, top_roots = y[-1], y[:-1]
        strict_steps = 0
        for zeros in itertools.combinations(range(1, reach), c - 1):
            a_u = _exp_sum(y, zeros, None)
            bound = math.prod(v / (1 - v) for v in y[: _leading_run(zeros) + 1])
            tail_u = _abs_tail(a_u, y, zeros)
            assert tail_u <= bound, zeros
            if _leading_run(zeros) == c - 1:
                assert tail_u == bound  # the k = 0 equality case
                continue

            z, rest = zeros[-1], zeros[:-1]
            m = max(rest, default=0)
            a_f = _exp_sum(top_roots, rest, None)
            a_g = _exp_sum(y, (0, *rest), z)
            eta = 1 if _val(a_f, top_roots, m + 1) > 0 else -1

            def f_hat(d: int, a: list[Fraction] = a_f, s: int = eta) -> Fraction:
                return s * _val(a, top_roots, d)

            def g_at(d: int, a: list[Fraction] = a_g) -> Fraction:
                return _val(a, y, d)

            # Step 1: the peel is the whole induction, and it is strict.
            tail_f = _abs_tail(a_f, top_roots, rest)
            assert tail_u < tail_f, zeros
            strict_steps += 1

            # Step 2: F and lambda G are anti-aligned, crossing exactly at z.
            mu = abs(f_hat(z))
            for d in range(1, z):
                if d not in rest:
                    assert abs(f_hat(d)) > mu * abs(g_at(d)), (zeros, d)
            for d in range(z + 1, z + 12):
                assert abs(f_hat(d)) < mu * abs(g_at(d)), (zeros, d)

            # Step 3: the identity, exactly.
            tail_g = _abs_tail(a_g, y, (0, *rest))
            above = abs(_from(a_u, y, z + 1))
            assert tail_f - tail_u == mu * tail_g - 2 * above, zeros

            # Step 4: the equivalence, then (T) and the factor 2.
            gamma_g = _from(a_g, y, z) / g_at(z)
            gamma_f = eta * _from(a_f, top_roots, z) / f_hat(z)
            assert gamma_g <= gamma_f / (1 - y_c), zeros
            assert gamma_g <= 2 * gamma_f, zeros

            # (C): G's normalised profile is under F's convolved with y_c.
            psi = ratio = Fraction(1)
            for t in range(1, self.HORIZON):
                psi = y_c * psi + f_hat(z + t) / f_hat(z)
                ratio = y_c * ratio + (g_at(z + t) - y_c * g_at(z + t - 1)) / g_at(z)
                assert g_at(z + t) / g_at(z) == ratio  # the recurrence for G
                assert ratio <= psi, (zeros, t)

            # (D), and the W > 0 that chains it to every z.
            sigma = g_at(m + 1) / f_hat(m + 1)
            for d in range(z, z + self.HORIZON):
                e_d = g_at(d) - y_c * g_at(d - 1)
                assert e_d / f_hat(d) <= sigma <= g_at(z) / f_hat(z), (zeros, d)
                assert g_at(d) * f_hat(m + 1) - g_at(m + 1) * f_hat(d) >= 0

            # Step 5: Delta vanishes identically iff {0} u Z' is an interval,
            # and otherwise has no zero above m + 1 and is positive there.
            def delta(d: int, s: Fraction = sigma) -> Fraction:
                return s * f_hat(d) - (g_at(d) - y_c * g_at(d - 1))

            interval = [0, *rest] == list(range(c - 1))
            assert delta(m + 1) == 0
            if interval:
                assert all(delta(d) == 0 for d in range(m + 2, m + 12))
            else:
                assert all(delta(d) > 0 for d in range(m + 2, m + 12)), zeros
        assert strict_steps  # the parametrisation reaches the peel at all
