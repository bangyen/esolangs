"""The registry-wide execution contract: commands run against table length."""

from __future__ import annotations

import itertools
import random
import sys
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from math import log2
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs import describe, encode_inputs, generate, instantiate
from esolangs.debugger import make_vm
from esolangs.registry import BY_BOOLEAN
from esolangs.vm import VM
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.linearity import _regime_start
from tests.tools.test_boolean_contract import _parity

#: Cost band; see ``__main__.py``.  It steps every generator's program at
#: rising arity, which is tens of seconds and so cannot sit in CI.
BAND = "by-hand"
COST = 32.0

#: Most per-added-input growth in commands a settled generator may show.
#: Shared with ``linearity.py``: a single pass over the table doubles.
MAX_GROWTH = 2.15

#: Most per-added-input growth a ``poly n`` Execution or Workspace cell may
#: show.  ``n**2`` fitted over n=5..9 reads x1.33 and ``T`` reads x2, so
#: this splits them; a large constant can still hide a ``T`` term this far
#: down, which is why a ``poly n`` cell also names its reason.
POLY_GROWTH = 1.5

#: Most growth the increments of a ``poly n`` row's dense series may show
#: (``_step_growth``).  ``n**3`` reads x1.25 at n=6..12 and a constant plus
#: ``T`` x2; NoComment read x1.99 and SLOW ACV MAMMALIAN x1.43.
STEP_GROWTH = 1.4

#: Rungs needed after the last route change before a ratio means anything,
#: and the window the slope is fitted over.  Five, because the wobble these
#: counts carry has no single period: Taglate alternates every other input
#: (1.14x then 3.35x, both Theta(T)), while AddSubJump and S*bleq bump on a
#: longer cycle.  Any fixed two- or three-step comparison lands mid-wobble
#: for one of them and reads a linear construction as super-linear.
MIN_RUNGS = 5
WINDOW = 5

#: Rows stepped per arity.  See "Rows are sampled" above.
ROW_SAMPLE = 6

#: A program still running after this many commands is reported, not guessed
#: at.  Also what stops a non-halting row from running forever.
STEP_CAP = 2_000_000

#: Arity ceilings.  Fixed rather than a time budget, for the reason
#: ``linearity.py`` gives: a wall-clock cutoff climbs further on a fast
#: machine than in CI and quietly changes the verdict.  Raised where the
#: route changes late: AddSubJump jumps 39 -> 965 at n=6, FRACTRAN drops
#: 41 -> 10 at n=7, so 9 left four and three rungs, short of ``MIN_RUNGS``.
MAX_ARITY = 9

#: The dense pass of a ``poly n`` row climbs further: Sophie passed it at
#: n <= 9 and only diverged past 10 (dense 81 -> 455 commands at n=10..16,
#: parity 68 -> 115).  A poly n row is cheap by its own claim; n=10..12 cost
#: ~6s over 23 rows.  ``ARITY_OVERRIDE`` still caps Factor, Line and Circuit
#: Diagram, whose time is load, not commands (152s, 99s, 27s to n=12).
DENSE_ARITY = 12
ARITY_OVERRIDE = {
    "addsubjump": 10,
    "b_tapemark": 7,
    "fractran": 11,
    "circuit_diagram": 7,
    "container": 6,
    "factor": 7,
    "line": 6,
    "flowchart": 8,
    "one_two_three": 8,
    "polynomial": 7,
}

#: Generators this contract cannot measure at all, with the reason.
#:
#: Deliberately short, and it does *not* list the quadratic-execution
#: languages.  BIO, Jaune, Flowchart, RAM0 and BrainIf run a *linear* number
#: of commands -- their quadratic is the cost of each command, which this
#: contract says outright it does not price -- so they are held to the bound
#: here like anything else, and their per-command cost is recorded in
#: ``docs/limitations.md`` where it belongs.  Exempting them here would have
#: been a category error that quietly stopped guarding five generators.
#:
#: ``main`` asserts every name is a real generator, so a rename cannot
#: silently deselect one.  Empty since A Painter Ant, which never halts, is
#: measured to the pass start its ``run`` stops at (:func:`run_to_answer`).
EXEMPT: dict[str, str] = {}


def exempt_generators() -> dict[str, str]:
    """Return manifest exemptions plus the nonhalting generator's obstruction."""
    reasons = dict(EXEMPT)
    for row in load_ledger().rows:
        for label in ("cap", "exception"):
            if label in row.labels:
                reasons.setdefault(row.generator, f"proof_status.json {label} row")
    return reasons


@dataclass
class Growth:
    """One generator's worst measured command growth."""

    generator: str
    ratio: float | None = None
    arity: int = 0
    regime: int = 0
    commands: int = 0
    reason: str = ""
    step: float | None = None


def _rows(table: str, halts: str | None) -> list[int]:
    """Which rows of ``table`` to step, the last candidate always included."""
    candidates = [
        row for row in range(len(table)) if halts is None or table[row] == halts
    ]
    if len(candidates) <= ROW_SAMPLE:
        return candidates
    step = len(candidates) // ROW_SAMPLE
    keep = {*candidates[::step], candidates[-1]}
    return sorted(keep)


def run_to_answer(
    machine: VM,
    cap: int | None = None,
    sample: Callable[[Hashable], None] | None = None,
) -> int | None:
    """Steps to the answer, or ``None`` at ``cap``.

    The answer is a halt, except where stepping never reaches it (A Painter
    Ant): there the run ends as its ``run`` does, at the pass start whose
    state repeats, found by Brent's over pass starts.  Suffolk's EOF on the
    wrap to a read is the same kind of end, already spelled ``halted``.
    """
    tortoise, power, passes, steps = machine.snapshot(), 1, 0, 0
    while not machine.halted:
        if cap is not None and steps >= cap:
            return None
        machine.step()
        steps += 1
        if sample is not None:
            sample(machine.snapshot())
        if not machine.steppable_to_answer and machine.ip == 0:
            passes += 1
            state = machine.snapshot()
            if state == tortoise:
                return steps
            if passes == power:
                tortoise, power, passes = state, power * 2, 0
    return steps


def _commands(name: str, table: str) -> int | None:
    """Worst sampled row's command count, or ``None`` if none finished."""
    facts = describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        # Which bit the language spells by terminating, read rather than
        # assumed: it is ("halts", "diverges") for all four today.
        halts = str(list(facts["answer_encoding"]).index("halts"))
    inputs = len(table).bit_length() - 1
    program = generate(name, table, width=None)
    worst: int | None = None
    for row in _rows(table, halts):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, bits, width=None), ""
        else:
            source, stdin = program, encode_inputs(name, bits, truth_table=table)
        steps = run_to_answer(make_vm(name, source, stdin=stdin), STEP_CAP)
        if steps is not None and (worst is None or steps > worst):
            worst = steps
    return worst


def _dense(n: int) -> str:
    """A seeded random table: parity has n ANF terms, so it hides Fargo's T."""
    width = 1 << n
    return f"{random.Random(n).getrandbits(width):0{width}b}"


def _series(
    name: str, top: int, table: Callable[[int], str] = _parity
) -> list[tuple[int, int]]:
    """(arity, worst sampled command count) for every arity that runs."""
    out: list[tuple[int, int]] = []
    for n in range(1, top + 1):
        try:
            count = _commands(name, table(n))
        except Exception:
            break
        if count is None or count == 0:
            continue
        out.append((n, count))
    return out


def _growth(window: list[tuple[int, int]]) -> float:
    """Per-added-input growth, as the fitted slope over ``window``."""
    xs = [float(arity) for arity, _ in window]
    ys = [log2(count) for _, count in window]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    spread = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / spread
    return 2.0**slope


def _step_growth(series: list[tuple[int, int]]) -> float | None:
    """Per-input growth of the increments: summed last window over the one before.

    Differencing cancels a fixed overhead that ``_growth`` cannot see past:
    NoComment's T/32-byte stack behind a 32,768-bit tape read x1.00 on the
    ratio and x1.99 here.  Windows of three increments, two when the series is
    short.  ``None`` (no judgement; the ratio still applies) when too short or
    when any increment is not positive: a hidden term grows every rung, while
    CV(N)(C)'s 86 -> 60 -> 81 noise read x1.55 on raw windows.
    """
    width = min(3, (len(series) - 1) // 2)
    if width < 2:
        return None
    steps = [b - a for (_, a), (_, b) in itertools.pairwise(series[-2 * width - 1 :])]
    if min(steps) <= 0:
        return None
    return float((sum(steps[width:]) / sum(steps[:width])) ** (1 / width))


def _self_check() -> tuple[float, float, float]:
    """Run the fit on known-linear, ``T log T`` and quadratic command series."""
    window = list(range(5, 5 + WINDOW))
    linear = _growth([(n, 2**n) for n in window])
    linearithmic = _growth([(n, 2**n * n) for n in window])
    quadratic = _growth([(n, 4**n) for n in window])
    assert linear <= MAX_GROWTH, f"linear control read x{linear}"
    assert linearithmic > MAX_GROWTH, f"T log T control read x{linearithmic}"
    assert quadratic > MAX_GROWTH, f"quadratic control read x{quadratic}"
    cubic = _step_growth([(n, n**3) for n in range(6, 13)])
    hidden = _step_growth([(n, 32768 + 2**n // 4) for n in range(6, 13)])
    assert cubic is not None
    assert cubic <= STEP_GROWTH, f"n**3 step read x{cubic}"
    assert hidden is not None
    assert hidden > STEP_GROWTH, f"hidden T step x{hidden}"
    return linear, linearithmic, quadratic


def measure(
    key: str,
    name: str,
    table: Callable[[int], str] = _parity,
    ceiling: int = MAX_ARITY,
) -> Growth:
    """Worst per-input command growth, past any route change."""
    if name in EXEMPT:
        return Growth(name, reason=EXEMPT[name])
    top = ARITY_OVERRIDE.get(key, ceiling)
    series = _series(name, top, table)
    if len(series) < MIN_RUNGS:
        return Growth(name, reason="too few arities produced a halting row")
    start = _regime_start(series)
    past = [row for row in series if row[0] >= start]
    if len(past) < MIN_RUNGS:
        return Growth(name, reason="too few rungs past the last route change")
    ratio = _growth(past[-WINDOW:])
    return Growth(name, ratio, past[-1][0], start, past[-1][1], step=_step_growth(past))


def main() -> int:
    """Measure every generator and check the settled ones against the bound."""
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}
    exempt = exempt_generators()
    unknown = sorted(set(exempt) - set(by_display))
    assert not unknown, f"exempt names no such generator: {unknown}"

    lin, nlog, quad = _self_check()
    print(
        f"control: linear x{lin:.3f} inside, T log T x{nlog:.3f} and "
        f"quadratic x{quad:.3f} rejected\n"
    )

    measured = [measure(key, name) for name, key in sorted(by_display.items())]
    assert len(measured) == len(BY_BOOLEAN), "not every generator was measured"

    poly = {
        row.generator for row in load_ledger().rows if row.execution_class == "poly n"
    }
    assert not poly & set(exempt), (
        f"exempt rows claim poly n: {sorted(poly & set(exempt))}"
    )
    # A poly n claim must also survive a dense table; keep the worse reading.
    for at, row in enumerate(measured):
        if row.generator in poly:
            key = by_display[row.generator]
            dense = measure(key, row.generator, _dense, DENSE_ARITY)
            if dense.ratio is None or (row.ratio or 0) < dense.ratio:
                measured[at] = dense
            if dense.step is not None and dense.step > STEP_GROWTH:
                measured[at] = Growth(
                    row.generator,
                    reason=f"dense increments grow x{dense.step:.3f}, a hidden T",
                )

    print(
        f"Execution contract: {len(measured)} generators, bound x{MAX_GROWTH}, "
        f"x{POLY_GROWTH} for poly n\n"
    )
    print(f"  {'generator':30s} {'growth':>7s} {'commands':>9s}  where")
    for row in sorted(measured, key=lambda r: -(r.ratio or 0)):
        tag = "  [exempt]" if row.generator in exempt else ""
        if row.ratio is None:
            print(f"  {row.generator:30s} {'UNPROVEN':>7s}  {row.reason}{tag}")
            continue
        print(
            f"  {row.generator:30s} x{row.ratio:6.3f} {row.commands:9d}  "
            f"n={row.arity}, from n={row.regime}{tag}"
        )

    failures = [
        row
        for row in measured
        if row.generator not in exempt
        and (
            row.ratio is None
            or row.ratio > (POLY_GROWTH if row.generator in poly else MAX_GROWTH)
        )
    ]
    xpass = sorted(
        row.generator
        for row in measured
        if row.generator in exempt and row.ratio is not None and row.ratio <= MAX_GROWTH
    )

    print(f"\n{len(exempt)} generators exempt:")
    for name, why in sorted(exempt.items()):
        print(f"  {name:30s} {why}")
    if xpass:
        print(
            f"\n{len(xpass)} of those measure inside the bound at the arities this\n"
            "reaches -- expected, and not evidence that they are linear:"
        )
        print(f"  {', '.join(xpass)}")

    if failures:
        print(f"\n{len(failures)} generator(s) not exempt exceed it:")
        for row in failures:
            detail = (
                row.reason
                if row.ratio is None
                else f"x{row.ratio:.3f} at n={row.arity} ({row.commands} commands)"
            )
            print(f"  {row.generator}: {detail}")
        print(
            "\nEither the construction or its interpreter regressed, or the cost is\n"
            "real and belongs in docs/limitations.md's execution-time section."
        )
        return 1

    print(f"\nall {len(measured) - len(exempt)} non-exempt generators inside the bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
