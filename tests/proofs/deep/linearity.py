"""The registry-wide scaling contract: emitted size against table length."""

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

#: Cost band; see ``__main__.py``.  It passes now that Forþ is linear, so the
#: band is a cost call rather than a triage one: it builds every generator at
#: rising arity, and 30s is too slow for CI to spend on every push.
from tests.source_support import source_units
from tests.tools.test_boolean_contract import _nested_dense, _parity

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
    "streetcode": 10,
    # Native Line at n=6 already renders millions of pixels.
    "line": 6,
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
            out.append((n, source_units(fn(make(n)))))
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
    """The top rungs of each arity parity, past any route change."""
    past = _past_regime(series)
    out = []
    for parity in (0, 1):
        rungs = [row for row in past if row[0] % 2 == parity]
        if len(rungs) >= MIN_TREND_RUNGS:
            out.append(rungs[-MIN_TREND_RUNGS:])
    return out


def _trend(series: list[tuple[int, int]]) -> float | None:
    """Successive-difference ratio over three same-parity rungs."""
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
    """Least-squares ``a * T + b`` over the same rungs, for the report."""
    classes = _classes(series)
    if not classes:
        return None
    return max(
        (_line([(2**n, size) for n, size in rungs]) for rungs in classes),
        key=lambda fitted: fitted[2],
    )


def _ratio(series: list[tuple[int, int]]) -> float | None:
    """Two-step growth of one ``(arity, size)`` series, past any route change."""
    if len(series) < MIN_RUNGS:
        return None
    past = _past_regime(series)
    if len(past) < MIN_RUNGS:
        return None
    return sqrt(past[-1][1] / past[-3][1])


def measure(key: str, name: str) -> Growth:
    """Worst-fitting shape for one generator, past any route change."""
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
    """Run the statistic on linear and on super-linear synthetic series."""
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
    """Return manifest exemptions for open size claims and totality ceilings."""
    reasons = {}
    for row in load_ledger().rows:
        for label in ("cap", "exception"):
            if label in row.labels:
                reasons[row.generator] = f"proof_status.toml {label} row"
    for name in sorted(load_audit().unsettled):
        reasons[name] = "proof_status.toml scaling audit: open"
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
    assert len(measured) == len(BY_BOOLEAN), "not every generator was measured"

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
