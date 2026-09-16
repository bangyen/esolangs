"""The registry-wide scaling contract: emitted size against table length.

Run:  just proofs   (or python tests/proofs/deep/linearity.py)

``docs/roadmap.md`` asks for "a registry-wide scaling contract" to finish the
linear-generator item.  ``tests/tools/test_boolean_contract.py`` already has
one, but it covers only the twenty-five languages of that item's original
queue; the other forty generators have never had their growth checked at all.
This measures all sixty-five.

What is asserted
----------------
A construction whose output is O(T) doubles when the table doubles, so its
size ratio per added input tends to two.  The contract is stated on the
*per-entry* cost instead, because that is the quantity with meaning: dividing
by T, a linear construction's characters-per-table-entry settles on a
constant, while a Theta(T log T) one grows without bound.  ``MAX_GROWTH``
allows the per-entry cost to rise by at most 7.5% per added input.

Where the bound sits, measured on both sides:

* the settled cohort's worst is Circuit Diagram at x2.079 (+3.9% per entry)
  and Streetcode at x2.065, with everything else at or under x2.02;
* the super-linear constructions this repository has already retired measured,
  single-step at n=8 -> 9 on parity, A Painter Ant x3.96, COD x3.89, Minifuck
  x3.53 and 123 x2.43 -- the numbers still quoted in the roadmap's parity-sweep
  paragraph, all of which this bound rejects.

So it has teeth on both sides and roughly a factor of two of headroom above
today's worst honest construction.  It is a calibrated regression guard, not a
proof.

What is NOT asserted
--------------------
**Passing this is not evidence of linearity.**  Factor is the standing
counterexample: ``docs/limitations.md`` proves its digit growth is
language-forced super-linear, and it measures x2.113 here -- inside the
bound.  SLOW ACV MAMMALIAN's retired tree made the same point at x2.039
against a proven ``S(d) >= (2 + 1/255) S(d-1)`` before its linear chain
shipped.  No threshold separates such a construction from a linear one at
any arity this suite can reach, and one tuned until it did would fail most
of the registry.  A super-linear factor of ``log T`` is simply not visible
in twelve doublings.  That is why the expected-failure set is read from the
documents rather than discovered here, and why a generator's absence from
the failure list below means only "not caught", never "proved linear".

Regime changes are excluded, not smoothed
-----------------------------------------
Generators dispatch, and a route switch moves size by a factor that has
nothing to do with asymptotics: Circuit Diagram jumps x154 at n=8 when its
H-layout takes over, Streetcode x23 at n=6, %^2^-1 x321 at n=4, and Container
*drops* from 5674 to 1200 at n=7.  Measuring across one of those reads the
constant, not the growth -- an earlier draft of this file scored Circuit
Diagram at x20.2 for exactly that reason, and %^2^-1 and WII2D looked
super-linear until their upward jumps were excluded.

So a step whose ratio leaves ``REGIME_BAND`` is treated as a route boundary
and the measurement restarts after it.  The band is a rule rather than a fit:
a table doubles, so no construction that is even remotely linear can quadruple
or halve across one added input.  The failure mode is safe -- a generator
whose every step breaks the band never accumulates the three rungs a
measurement needs and is reported UNPROVEN, never passed.  ZTOALC L is the one
that lands there, and its ceiling is why it is a ``cap`` row.

Two arities of the same parity are compared (a two-step geometric mean)
because the alternating-axis layouts only grow on every other input: Taglate
emits 5499 characters at both n=7 and n=8, then 21025 at both n=9 and n=10.
Single steps read x1.00 then x3.82 for a construction that is perfectly
linear.
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
from tests.tools.test_boolean_contract import _dense, _parity

#: Cost band; see ``__main__.py``.  It passes now that Forþ is linear, so the
#: band is a cost call rather than a triage one: it builds all 65 generators at
#: rising arity, and 30s is too slow for CI to spend on every push.
BAND = "by-hand"
COST = 30.0

_SHAPES = (("dense", _dense), ("parity", _parity))

#: Most per-added-input growth a settled generator may show.  See the module
#: docstring for what sits on either side of it.
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
    "b_tapemark": 11,
    "circuit_diagram": 10,
    "factor": 11,
    "pct_squared_minus_one": 10,
    "polynomial": 9,
    "slow_acv_mammalian": 10,
    "streetcode": 10,
    "wii2d": 9,
    "ztoalc_l": 10,
}


@dataclass
class Growth:
    """One generator's worst measured growth."""

    generator: str
    ratio: float | None = None
    shape: str = ""
    arity: int = 0
    regime: int = 0
    reason: str = ""

    @property
    def per_entry(self) -> float:
        """Growth in characters per table entry, per added input."""
        assert self.ratio is not None
        return self.ratio / 2


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


def measure(key: str, name: str) -> Growth:
    """Worst per-input growth across both table shapes, past any route change."""
    fn = getattr(boolean, key)
    top = ARITY_OVERRIDE.get(key, MAX_ARITY)
    worst = Growth(generator=name, reason="no shape produced enough rungs")
    for shape, make in _SHAPES:
        series = _series(fn, make, top)
        if len(series) < MIN_RUNGS:
            continue
        start = _regime_start(series)
        past = [row for row in series if row[0] >= start]
        if len(past) < MIN_RUNGS:
            continue
        ratio = sqrt(past[-1][1] / past[-3][1])
        if worst.ratio is None or ratio > worst.ratio:
            worst = Growth(name, ratio, shape, past[-1][0], start)
    return worst


def exempt_generators() -> dict[str, str]:
    """Generators the documents already say are not settled as linear.

    Read from both ledgers rather than listed here.  The roadmap's audit table
    holds the open scaling rows; ``proofs.md`` marks the generators whose
    construction runs into a resource ceiling (``cap``) or has no totality
    argument at all (``exception``).  Closing a row in either document is a
    one-line edit that immediately arms this contract against that generator.
    """
    reasons = {}
    for row in load_ledger().rows:
        for label in ("cap", "exception"):
            if label in row.labels:
                reasons[row.generator] = f"proofs.md {label} row"
    for name in sorted(load_audit().unsettled):
        reasons[name] = "roadmap scaling audit: open"
    return reasons


def main() -> int:
    """Measure every generator and check the settled ones against the bound."""
    exempt = exempt_generators()
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}

    measured = [measure(key, name) for name, key in sorted(by_display.items())]
    assert len(measured) == len(BY_BOOLEAN) == 65, "not every generator was measured"

    print(f"Scaling contract: {len(measured)} generators, bound x{MAX_GROWTH}\n")
    print(f"  {'generator':30s} {'growth':>7s} {'per entry':>10s}  where")
    for row in sorted(measured, key=lambda r: -(r.ratio or 0)):
        tag = "  [exempt]" if row.generator in exempt else ""
        if row.ratio is None:
            print(f"  {row.generator:30s} {'UNPROVEN':>7s}  {row.reason}{tag}")
            continue
        where = f"{row.shape} n={row.arity}, from n={row.regime}"
        print(
            f"  {row.generator:30s} x{row.ratio:6.3f} {row.per_entry:9.3f}x  "
            f"{where}{tag}"
        )

    failures = [
        row
        for row in measured
        if row.generator not in exempt and (row.ratio is None or row.ratio > MAX_GROWTH)
    ]
    xpass = sorted(
        row.generator
        for row in measured
        if row.generator in exempt and row.ratio is not None and row.ratio <= MAX_GROWTH
    )

    print(f"\n{len(exempt)} generators exempt by the documents:")
    for name, why in sorted(exempt.items()):
        print(f"  {name:30s} {why}")
    print(
        f"\n{len(xpass)} of those measure inside the bound anyway -- expected, and "
        "not evidence of\nlinearity (see the module docstring on Factor):"
    )
    print(f"  {', '.join(xpass)}")

    if failures:
        print(f"\n{len(failures)} generator(s) the documents call settled exceed it:")
        for row in failures:
            detail = (
                row.reason
                if row.ratio is None
                else (
                    f"x{row.ratio:.3f} ({row.per_entry:.3f}x per entry) on "
                    f"{row.shape} at n={row.arity}"
                )
            )
            print(f"  {row.generator}: {detail}")
        print(
            "\nEither the construction regressed, or the document is wrong and the\n"
            "generator belongs in the roadmap's scaling audit."
        )
        return 1

    print(f"\nall {len(measured) - len(exempt)} settled generators inside the bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
