"""The registry-wide scaling contract: emitted size against table length.

Run:  just proofs   (or python tests/proofs/deep/linearity.py)

``docs/roadmap.md`` asks for "a registry-wide scaling contract" to finish the
linear-generator item.  ``tests/tools/test_boolean_contract.py`` already has
one, but it covers only part of the registry; the rest have never had their
growth checked at all.  This measures every generator.

What is asserted
----------------
A linear construction's emitted size is ``a * T + b``: a constant cost per
table entry plus a fixed prologue.  Measured at three same-parity arities --
sizes ``s1, s2, s3`` at ``T, 4T, 16T`` -- such a construction satisfies

    (s3 - s2) / (s2 - s1) = 4

*exactly*, because the differences are ``3aT`` and ``12aT`` and the prologue
cancels out of both.  The contract asserts that difference ratio stays under
:data:`MAX_DIFF_RATIO`.  A convex construction leaves a residue: ``T log T``
reads 4.83 and ``T^1.1`` reads 4.59.

Being blind to ``b`` is the point, because ``b`` is what a size *ratio*
mostly measures.  A table doubles per added input, so a ratio of emitted
sizes reads

    size(n) / size(n-2) = 4 * (a + b/T) / (a + 4b/T),

which exceeds four exactly when ``b`` is negative -- a statement about the
prologue, not about growth.  And ``b < 0`` is the *normal* case here: a
balanced decision tree with per-node cost ``C`` sums to ``2C*T - 2C``.  So
the retired size ratio ranked generators by how much fixed output they emit.
AddSubJump is ``0.55*T + 1440`` and read x1.31; Clockwise is
``84.8*T - 858`` and read x2.01.  Both are exactly linear.  Worse, it
rewarded the wrong edit: with ``b`` negative and fixed, *reducing* the
per-entry cost raises the ratio, so a genuine size win read as a regression.

Where the bound sits, measured on both sides:

* the settled cohort's worst is Container at 4.289 and Streetcode at 4.231,
  both of them still settling after a route change, with everything else at
  or under 4.21;
* ``T log T`` reads 4.83 and ``T^1.1`` 4.59, and both are rejected.  Factor
  reads 4.467 and is rejected too -- correctly, since its digit growth is
  proven super-linear, and it is exempt for that reason.

So it has teeth on both sides.  It is a calibrated regression guard, not a
proof.  The retired size ratio is kept as :data:`MAX_GROWTH`, a loose
backstop for the generators whose arity ceiling leaves fewer than three
same-parity rungs past their last route change.

What is NOT asserted
--------------------
**Passing this is not evidence of linearity.**  ``T^1.05`` reads 4.289 --
inside the bound, and level with the worst honest reading -- so a
construction with a small enough super-linear factor is not distinguishable
from a line at any arity this suite can reach, and one tuned until it were
would fail most of the registry.  SLOW ACV MAMMALIAN's retired tree made the
point concretely, measuring as linear against a proven
``S(d) >= (2 + 1/255) S(d-1)`` before its linear chain shipped.  That is why
the expected-failure set is read from the documents rather than discovered
here, and why a generator's absence from the failure list below means only
"not caught", never "proved linear".

Regime changes are excluded, not smoothed
-----------------------------------------
Generators dispatch, and a route switch moves size by a factor that has
nothing to do with asymptotics: Circuit Diagram jumps x35 at n=8 when its
H-layout takes over, Streetcode x23 at n=6, and Container
*drops* from 5674 to 1200 at n=7.  A line fitted across one of those measures
the switch, not the growth.

So a step whose ratio leaves ``REGIME_BAND`` is treated as a route boundary
and the measurement restarts after it.  The band is a rule rather than a fit:
a table doubles, so no construction that is even remotely linear can quadruple
or halve across one added input.  The failure mode is safe -- a generator
whose every step breaks the band never accumulates the rungs a measurement
needs and is reported UNPROVEN, never passed.

Why the dense shape is nested
-----------------------------
``_dense`` seeds on the arity, so its tables at consecutive arities are
independent draws and how much of each folds is an accident of the draw.
Re-drawing them moves the reading by +-2% -- enough, under the old ratio, to
decide a pass: 3x, the Algebraic Programming Language and Forbin each read
above and below x2.00 depending only on the seed.  ``_nested_dense`` draws one
stream and takes prefixes of it, so each arity extends the one below and the
series is a family rather than a sample.
"""

from __future__ import annotations

import itertools
import sys
from collections.abc import Callable
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import esolangs.tools as boolean
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import load as load_ledger
from tests.proofs._roadmap import load as load_audit
from tests.tools.test_boolean_contract import _nested_dense, _parity

#: Cost band; see ``__main__.py``.  It passes now that Forþ is linear, so the
#: band is a cost call rather than a triage one: it builds every generator at
#: rising arity, and 30s is too slow for CI to spend on every push.
BAND = "by-hand"
COST = 30.0

_SHAPES = (("dense", _nested_dense), ("parity", _parity))

#: Most the difference ratio may exceed its linear value of four.  The
#: settled cohort's worst is 4.29 and the ``T log T`` control reads 4.75 to
#: 4.92, so the bound sits between them with headroom on both sides.
MAX_DIFF_RATIO = 4.4

#: What the difference ratio is for a linear construction, and what the
#: report is stated against.
LINEAR_DIFF_RATIO = 4.0

#: Rungs the difference ratio needs, *within one arity parity*.  Three is
#: exactly what the statistic consumes; there is no averaging to be had at
#: the arities this suite reaches.
MIN_TREND_RUNGS = 3

#: Backstop for the generators whose arity ceiling leaves fewer than
#: :data:`MIN_TREND_RUNGS` same-parity rungs past their last route change,
#: where the difference ratio cannot be formed at all.  A size *ratio*, with
#: all the weaknesses the module docstring gives -- which is why it applies
#: only where the difference ratio cannot.
MAX_GROWTH = 2.15

#: A step outside this band is a route change rather than growth.  A table
#: doubles per added input, so a construction anywhere near linear cannot
#: quadruple or halve across one.
REGIME_BAND = (0.5, 4.0)

#: Rungs needed after the last route change before a ratio means anything:
#: three, because the statistic compares two arities of the same parity.
MIN_RUNGS = 3

#: Arity ceilings.  Deliberately fixed rather than a time budget -- a
#: wall-clock cutoff would climb further on a fast machine than in CI (~2.3x
#: slower here) and quietly change the verdict.  The default reaches n=12; the
#: overrides are the generators whose builds are measured in seconds, each set
#: to the lowest arity that still clears MIN_RUNGS past its last route change.
MAX_ARITY = 12
ARITY_OVERRIDE = {
    "circuit_diagram": 10,
    "factor": 11,
    "polynomial": 9,
    "slow_acv_mammalian": 10,
    "streetcode": 10,
}


@dataclass
class Growth:
    """One generator's worst-reading table shape."""

    generator: str
    trend: float | None = None
    slope: float = 0.0
    intercept: float = 0.0
    ratio: float | None = None
    shape: str = ""
    arity: int = 0
    regime: int = 0
    reason: str = ""

    @property
    def measured(self) -> bool:
        """Whether either statistic came out."""
        return self.trend is not None or self.ratio is not None


def _series(
    fn: Callable[[str], object], make: Callable[[int], str], top: int
) -> list[tuple[int, int]]:
    """(arity, emitted size) for every arity the generator accepts."""
    out = []
    for n in range(1, top + 1):
        try:
            out.append((n, len(str(fn(make(n))))))
        except ValueError:
            break  # a refusal is the generator's ceiling, not a failure
    return out


def _regime_start(series: list[tuple[int, int]]) -> int:
    """The arity after the last route change."""
    lo, hi = REGIME_BAND
    start = series[0][0]
    for (_a, before), (b, after) in itertools.pairwise(series):
        if before and not lo <= after / before <= hi:
            start = b
    return start


def _past_regime(series: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The tail of ``series`` after its last route change."""
    start = _regime_start(series)
    return [row for row in series if row[0] >= start]


def _line(pts: list[tuple[int, int]]) -> tuple[float, float, float]:
    """Least-squares ``a * T + b`` over ``(T, size)`` and its worst residual."""
    count = len(pts)
    sx = sum(t for t, _ in pts)
    sy = sum(s for _, s in pts)
    sxx = sum(t * t for t, _ in pts)
    sxy = sum(t * s for t, s in pts)
    slope = (count * sxy - sx * sy) / (count * sxx - sx * sx)
    intercept = (sy - slope * sx) / count
    worst = max(abs(slope * t + intercept - s) / s for t, s in pts)
    return slope, intercept, worst


def _classes(series: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """The top rungs of each arity parity, past any route change.

    Split by parity because the alternating-axis layouts only grow on every
    other input -- Taglate emits 5499 characters at both n=7 and n=8, then
    21025 at both n=9 and n=10 -- so consecutive arities measure the step
    rather than the growth.  Within one parity those layouts are as regular
    as any other construction, and a rung is a *quadrupling* of ``T``.
    """
    past = _past_regime(series)
    out = []
    for parity in (0, 1):
        rungs = [row for row in past if row[0] % 2 == parity]
        if len(rungs) >= MIN_TREND_RUNGS:
            out.append(rungs[-MIN_TREND_RUNGS:])
    return out


def _trend(series: list[tuple[int, int]]) -> float | None:
    """Successive-difference ratio over three same-parity rungs.

    The statistic, and the reason this file no longer asserts on a size
    ratio.  For ``size = a * T + b`` at rungs ``T, 4T, 16T`` the differences
    are ``3aT`` and ``12aT``, so

        (s3 - s2) / (s2 - s1) = 4

    *exactly*, whatever ``b`` is: the prologue cancels in the first
    difference.  A convex construction leaves a residue -- ``T log T`` reads
    4.75 to 4.92 and ``T^1.1`` 4.59.

    That blindness to ``b`` is the whole point.  The retired size ratio was
    a function of the prologue more than of the growth, so it ranked
    generators by how much fixed output they emit and moved the wrong way
    when one got leaner; see the module docstring.

    Worst (largest) class reported.  ``None`` when no class has three rungs,
    or when the series does not grow across them -- a non-increasing series
    has nothing for this statistic to say, and dividing by its first
    difference would be meaningless.
    """
    worst = None
    for rungs in _classes(series):
        (_a, s1), (_b, s2), (_c, s3) = rungs
        if s2 - s1 <= 0:
            continue
        ratio = (s3 - s2) / (s2 - s1)
        if worst is None or ratio > worst:
            worst = ratio
    return worst


def _fit(series: list[tuple[int, int]]) -> tuple[float, float, float] | None:
    """Least-squares ``a * T + b`` over the same rungs, for the report.

    Reported rather than asserted on: ``a`` is the per-entry cost and ``b``
    the prologue, which is what a reader wants to know about a construction,
    but a residual over three rungs does not discriminate (the honest cohort
    reaches 0.108 and a ``T^1.05`` control only 0.089).
    """
    classes = _classes(series)
    if not classes:
        return None
    return max(
        (_line([(2**n, size) for n, size in rungs]) for rungs in classes),
        key=lambda fitted: fitted[2],
    )


def _ratio(series: list[tuple[int, int]]) -> float | None:
    """Two-step growth of one ``(arity, size)`` series, past any route change.

    The backstop statistic.  ``None`` when the series has too few rungs.
    """
    if len(series) < MIN_RUNGS:
        return None
    past = _past_regime(series)
    if len(past) < MIN_RUNGS:
        return None
    return sqrt(past[-1][1] / past[-3][1])


def measure(key: str, name: str) -> Growth:
    """Worst-fitting shape for one generator, past any route change.

    Worst means largest residual where a fit is available, and largest ratio
    where none is, so a generator is judged by its least linear-looking table
    shape either way.
    """
    fn = getattr(boolean, key)
    top = ARITY_OVERRIDE.get(key, MAX_ARITY)
    worst = Growth(generator=name, reason="no shape produced enough rungs")
    for shape, make in _SHAPES:
        series = _series(fn, make, top)
        trend = _trend(series)
        fitted = _fit(series)
        ratio = _ratio(series)
        if trend is None and ratio is None:
            continue
        past = _past_regime(series)
        here = Growth(
            generator=name,
            trend=trend,
            slope=0.0 if fitted is None else fitted[0],
            intercept=0.0 if fitted is None else fitted[1],
            ratio=ratio,
            shape=shape,
            arity=past[-1][0],
            regime=past[0][0],
        )
        if not worst.measured:
            worst = here
        elif here.trend is not None and worst.trend is not None:
            worst = max(worst, here, key=lambda row: row.trend or 0.0)
        elif here.trend is not None:
            worst = here  # the trend outranks a bare backstop ratio
        elif worst.trend is None:
            worst = max(worst, here, key=lambda row: row.ratio or 0.0)
    return worst


def _fails(row: Growth) -> str:
    """Why this generator fails the contract, or "" if it does not."""
    if not row.measured:
        return row.reason
    if row.trend is not None:
        if row.trend > MAX_DIFF_RATIO:
            return (
                f"difference ratio {row.trend:.3f} (linear is "
                f"{LINEAR_DIFF_RATIO:.1f}) on {row.shape} at n={row.arity}"
            )
        return ""
    assert row.ratio is not None
    if row.ratio > MAX_GROWTH:
        return (
            f"x{row.ratio:.3f} on {row.shape} at n={row.arity} "
            "(backstop: too few rungs for the trend)"
        )
    return ""


#: Controls: label, whether the bound must reject it, and the series.  The
#: three linear ones differ only in prologue and must read *exactly* four --
#: that is the property the retired size ratio lacked, and it is asserted
#: rather than described.  ``T^1.05`` is carried as a known blind spot: it
#: reads 4.284, inside the bound, which is the same limit the module
#: docstring states for Factor.  Twelve doublings do not separate it from a
#: line, and a bound tuned until they did would fail most of the registry.
_CONTROLS: tuple[tuple[str, bool, Callable[[int], int]], ...] = (
    ("linear", False, lambda n: 17 * 2**n),
    ("linear, +500 prologue", False, lambda n: 17 * 2**n + 500),
    ("linear, -500 prologue", False, lambda n: 17 * 2**n - 500),
    ("T log T", True, lambda n: 2**n * n),
    ("T^1.1", True, lambda n: int((2**n) ** 1.1)),
    ("T^1.05 (blind spot)", False, lambda n: int((2**n) ** 1.05)),
)


def _self_check() -> list[tuple[str, float, float]]:
    """Run the statistic on linear and on super-linear synthetic series.

    A probe that never fires reports a wall that is not there, so the guard
    has to be shown to reject something: the super-linear controls must
    exceed :data:`MAX_DIFF_RATIO` and the linear ones must not.

    The linear controls are asserted *exactly* equal to
    :data:`LINEAR_DIFF_RATIO`, prologue and all.  That is the defect this
    statistic exists to fix -- under the retired size ratio the same three
    series read x1.979, x2.000 and x2.022, so the guard's verdict turned on
    a construction's fixed overhead rather than on its growth.
    """
    span = range(MAX_ARITY - 2 * MIN_TREND_RUNGS + 1, MAX_ARITY + 1)
    out = []
    for label, superlinear, fn in _CONTROLS:
        series = [(n, fn(n)) for n in span]
        trend = _trend(series)
        ratio = _ratio(series)
        assert trend is not None, label
        assert ratio is not None, label
        if superlinear:
            assert trend > MAX_DIFF_RATIO, f"{label} control read {trend}"
        else:
            assert trend <= MAX_DIFF_RATIO, f"{label} control read {trend}"
        if label.startswith("linear"):
            assert trend == LINEAR_DIFF_RATIO, f"{label} control read {trend}"
        out.append((label, trend, ratio))
    return out


def exempt_generators() -> dict[str, str]:
    """Generators the documents already say are not settled as linear.

    Read from both ledgers rather than listed here.  The roadmap's audit table
    holds the open scaling rows; ``proofs/index.md`` marks the generators whose
    construction runs into a resource ceiling (``cap``) or has no totality
    argument at all (``exception``).  Closing a row in either document is a
    one-line edit that immediately arms this contract against that generator.

    Not read from the ledger's Scaling column: that column opens a row on
    *time* as well as size (SLOW ACV MAMMALIAN's ballast loop), and this
    contract measures size only, so the audit's size cell is the narrower
    and correct source.  ``test_the_scaling_column_is_the_audit`` keeps the
    column and the audit in step.
    """
    reasons = {}
    for row in load_ledger().rows:
        for label in ("cap", "exception"):
            if label in row.labels:
                reasons[row.generator] = f"proofs/index.md {label} row"
    for name in sorted(load_audit().unsettled):
        reasons[name] = "roadmap scaling audit: open"
    return reasons


def main() -> int:
    """Measure every generator and check the settled ones against the bound."""
    exempt = exempt_generators()
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}

    print(
        f"controls (difference ratio over {MIN_TREND_RUNGS} same-parity rungs "
        f"to n={MAX_ARITY}; linear is {LINEAR_DIFF_RATIO:.1f}):"
    )
    for label, trend, ratio in _self_check():
        verdict = "rejected" if trend > MAX_DIFF_RATIO else "inside"
        print(f"  {label:24s} {trend:7.4f} {verdict:9s} (retired ratio x{ratio:.3f})")
    print()

    measured = [measure(key, name) for name, key in sorted(by_display.items())]
    assert len(measured) == len(BY_BOOLEAN) == 62, "not every generator was measured"

    print(
        f"Scaling contract: {len(measured)} generators, "
        f"difference ratio bound {MAX_DIFF_RATIO}\n"
    )
    print(
        f"  {'generator':30s} {'trend':>7s} {'per entry':>10s} {'prologue':>9s}  where"
    )
    for row in sorted(measured, key=lambda r: -(r.trend or 0)):
        tag = "  [exempt]" if row.generator in exempt else ""
        if not row.measured:
            print(f"  {row.generator:30s} {'UNPROVEN':>7s}  {row.reason}{tag}")
            continue
        where = f"{row.shape} n={row.arity}, from n={row.regime}"
        if row.trend is None:
            assert row.ratio is not None
            print(
                f"  {row.generator:30s} {f'x{row.ratio:.3f}':>7s} "
                f"{'(backstop)':>21s}  {where}{tag}"
            )
            continue
        print(
            f"  {row.generator:30s} {row.trend:7.3f} {row.slope:10.3f} "
            f"{row.intercept:+9.0f}  {where}{tag}"
        )

    failures = [
        (row, why)
        for row in measured
        if row.generator not in exempt and (why := _fails(row))
    ]
    xpass = sorted(
        row.generator for row in measured if row.generator in exempt and not _fails(row)
    )

    print(f"\n{len(exempt)} generators exempt by the documents:")
    for name, why in sorted(exempt.items()):
        print(f"  {name:30s} {why}")
    print(
        f"\n{len(xpass)} of those fit inside the bound anyway -- expected, and "
        "not evidence of\nlinearity (see the module docstring on Factor):"
    )
    print(f"  {', '.join(xpass)}")

    if failures:
        print(f"\n{len(failures)} generator(s) the documents call settled exceed it:")
        for row, why in failures:
            print(f"  {row.generator}: {why}")
        print(
            "\nEither the construction regressed, or the document is wrong and the\n"
            "generator belongs in the roadmap's scaling audit."
        )
        return 1

    print(f"\nall {len(measured) - len(exempt)} settled generators inside the bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
