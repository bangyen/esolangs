"""The limits ``docs/polynomial.md`` claims, as executable checks.

Most of that document's content is a measurement -- a ratio, a census, a
growth exponent.  Those belong in prose, where a stale number reads as a
stale number.  Pinning one in a rarely-run test hides it instead: the
suite goes green while the quantity it named has moved.

These three are a different kind of claim.  Each says the system *cannot*
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

import math
from fractions import Fraction

import pytest
import sympy as sp
import z3

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _Machine
from esolangs.interpreters.register_based.polynomial import (
    _parse_program,
    run,
    sanitize,
)
from esolangs.tools._polynomial import format_coeffs, multiply
from esolangs.tools.register import polynomial
from esolangs.tools.wii2d import _wii2d_apply

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
# An Interprogck8 rung cannot corrupt the answer phase
# --------------------------------------------------------------------------
#
# The blocker on putting a relay lattice inside the table region is that a
# ``DownAccLines`` fires during the fall-through that reads the answer, and
# the jump would corrupt the running sum.  It does not, because the rung
# advances by ``acc + 1``: followed by ``k`` nops it is transparent for every
# ``acc`` in ``[0, k]``.  The Theta(T log T) pricing rests on this.

_NOP = "X"


def _run_from(program: list[str], ip: int, acc: int) -> tuple[int | None, str]:
    """Run starting mid-program at ``(ip, acc)``; return (final acc, printed)."""
    io = ScriptedIO("")
    machine = _Machine(program, io)
    machine.state = machine.state.__class__(tuple(program), ip=ip, acc=acc)
    steps = 0
    try:
        while not machine.halted and steps < 10_000:
            machine.step()
            steps += 1
    except HaltError as exc:
        return None, f"HALT({exc})"
    return machine.state.acc, io.getvalue()


class TestRungsAreTransparent:
    """A navigation rung can sit inside the answer region without corrupting it.

    Transparency is "the accumulator survives and every path converges", not
    "every entry ends equal" -- ``DownAccLines`` preserves ``acc``, so
    different entries must end with different values.  Comparing them to each
    other was the wrong test when this was first written.
    """

    @pytest.mark.parametrize("k", [1, 2, 3, 4])
    @pytest.mark.parametrize("acc", [0, 1, 2, 3, 4])
    def test_a_rung_plus_k_nops_preserves_the_accumulator(
        self, k: int, acc: int
    ) -> None:
        if acc > k:  # only [0, k] is claimed
            pytest.skip("outside the transparent band")
        program = ["DownAccLines"] + [_NOP] * k + [_NOP] * 4
        final, _ = _run_from(program, 0, acc)
        assert final == acc

    def test_the_control_fires(self) -> None:
        # A rung followed by an EFFECT is not transparent, which is what the
        # nop run fixes.  Without this the test above would pass on a machine
        # where DownAccLines did nothing at all.
        program = ["DownAccLines", "@id", _NOP, _NOP]
        moved, _ = _run_from(program, 0, 0)
        kept, _ = _run_from(program, 0, 1)
        assert moved != 0, "acc 0 should fall through onto @id and move"
        assert kept == 1, "acc 1 should jump over @id and be kept"

    @pytest.mark.parametrize("table", ["01101001", "1111", "0000", "0110100110010110"])
    def test_a_suffix_sum_survives_rungs_threaded_through_it(self, table: str) -> None:
        """The answer phase itself: enter at r, fall through, read table[r].

        Line j is the difference ``table[j] - table[j+1]`` in {-1,0,1},
        biased so the running value stays in [0,2], with a transparent rung
        every 4 lines.
        """
        bits = [int(c) for c in table] + [0]
        lines: list[str] = []
        index: dict[int, int] = {}
        for j in range(len(table)):
            if j and j % 4 == 0:  # a navigation rung, made transparent
                lines += ["DownAccLines", _NOP, _NOP]
            index[j] = len(lines)
            delta = bits[j] - bits[j + 1]
            lines.append({1: "@nd", -1: "@nt", 0: _NOP}[delta])

        for row in range(len(table)):
            final, _ = _run_from(lines, index[row], 1)  # bias +1
            assert final == 1 + bits[row], f"row {row} of {table!r}"


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
# WII2D: a fold cannot halve past the radius of its merge zone
# --------------------------------------------------------------------------
#
# ``docs/limitations.md`` (searched negatives, WII2D) rests its ratchet
# accounting on one deterministic fact about the readout: after an ``s``
# whose epoch (the ``s`` and its ``+ - /`` tail) merges ``m`` live values
# and halves ``h`` times, for every ``n`` the ``n`` smallest distinct
# ``|w|`` before the ``s`` (largest ``r``) satisfy ``m >= n - 2 r**2 / 2**h
# - 2``: their squares span ``r**2``, a span meets at most ``r**2 / 2**h +
# 1`` block boundaries and at most that many consecutive gaps of ``2**h``
# or more, and every other consecutive pair merges.  At ``n = m + 3`` this
# is ``2**h <= r**2``, so the epoch leaves magnitude at least ``max(w)**2 /
# 2**h - unary - 1``: a fold about a dense centre squares the magnitude and
# divides it by ``r**2``.  The programs below are exact optima from the
# exhaustive readout search (domain 8, every pattern, cap 2**12) and the
# longest found at domains 10 and 12; each is replayed on the op semantics
# first.  A failure here means the lemma is wrong and the ratchet paragraph
# with it, not that a decoder regressed.

_WII2D_OPTIMA: tuple[tuple[str, str], ...] = (
    ("11010100", "++s/-//-----s-//--s-///s"),
    ("01101001", "---**+s/-/////s-///s"),
    ("01010101", "---s-/----s/-//s-/s"),
    ("00110101", "s/-//-s-/s-/////s"),
    ("1010110100", "-----**+s////-//---s/-/s-///s"),
    ("001101011010", "s/-//--------*-s/-/////--s-/--s/-/s"),
)


def _wii2d_epochs(
    pattern: str, program: str
) -> list[tuple[int, int, list[int], int, int]]:
    """Return ``(h, m, radii, max_w, out)`` per ``s`` epoch, replaying ``program``.

    ``radii`` is the sorted list of distinct ``|w|`` before the ``s``.
    """
    values = list(range(len(pattern)))
    out: list[tuple[int, int, list[int], int, int]] = []
    i = 0
    while i < len(program):
        if program[i] != "s":
            values = [_wii2d_apply(program[i], v) for v in values]
            i += 1
            continue
        before = sorted({abs(v) for v in values})
        merges = h = unary = 0
        live = len(set(values))
        values = [_wii2d_apply("s", v) for v in values]
        i += 1
        while i < len(program) and program[i] in "+-/":
            values = [_wii2d_apply(program[i], v) for v in values]
            h += program[i] == "/"
            unary += program[i] in "+-"
            i += 1
        merges = live - len(set(values))
        magnitude = max(abs(v) for v in values) + unary + 1
        out.append((h, merges, before, before[-1], magnitude))
    return out


class TestWii2dFoldCannotHalvePastItsMergeZone:
    @pytest.mark.parametrize(("pattern", "program"), _WII2D_OPTIMA)
    def test_the_program_reads_out_the_pattern(
        self, pattern: str, program: str
    ) -> None:
        got = "".join(str(_wii2d_apply(program, q)) for q in range(len(pattern)))
        assert got == pattern

    @pytest.mark.parametrize(("pattern", "program"), _WII2D_OPTIMA)
    def test_every_epoch_obeys_the_zone_lemma(self, pattern: str, program: str) -> None:
        epochs = _wii2d_epochs(pattern, program)
        assert epochs, program
        for h, merges, radii, max_w, magnitude in epochs:
            for n, radius in enumerate(radii, 1):
                assert merges >= n - 2 * radius * radius / 2**h - 2, (program, h, n)
            if len(radii) >= merges + 3:
                radius = radii[merges + 2]
                assert 2**h <= radius * radius, (program, h, merges, radius)
            assert magnitude >= max_w * max_w / 2**h, (program, magnitude, max_w, h)


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
            pytest.param(
                (2, 3, 5, 7, 11, 13), 16, 3, 120, 160, marks=pytest.mark.medium
            ),
            pytest.param(
                (2, 3, 5, 7, 11, 13, 17), 16, 4, 192, 300, marks=pytest.mark.medium
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
