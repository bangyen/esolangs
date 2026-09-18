"""The registry-wide execution contract: commands run against table length.

Run:  just proofs   (or python tests/proofs/deep/execution.py)

``linearity.py`` prices what a generator *emits*.  This prices what the
emitted program *does*: it builds each generator at rising arity, steps the
resulting program through its interpreter, and measures how the worst row's
command count grows.  The two are independent, in both directions -- a
Theta(T) source can execute in O(n) commands, and a fourteen-command program
can do Theta(T) work -- so neither bound implies the other and the registry
needs both measured.

What is asserted
----------------
A program that walks its table once doubles its command count when the table
doubles, so its ratio per added input tends to two; one that walks the table
per row tends to four.  ``MAX_GROWTH`` is the same 2.15 ``linearity.py``
uses, and for the same reason: it sits above every construction that reads
its table once and below every construction that reads it per row.

Where the bound sits, measured on both sides:

* the held cohort runs from x1.11 (Alight, Fargo -- programs that never
  look at most of the table, brainfuck's count being an arithmetic
  progression in the input count rather than the table's; Crement's
  ``5 n + 2`` tree walk measures x1.15 for the same reason) up to x2.06
  (AddSubJump), with 123, S*bleq, Bitdeque, Collatz Multiverse and COD all
  within a percent of x2.00 -- a single pass over the table;
* it has caught one construction for real.  Minsky Swap measured x2.29,
  with commands per table entry of 4.5, 4.0, 3.9, 4.5, 5.2, 6.1, 7.1, 8.0,
  9.0, 10.0 at n=1..10 -- the input count rather than a constant, so
  Theta(T log T).  It padded every input's setter block to the table's
  length when only that bit's weight was needed; sized to the weight, the
  blocks sum to ``2**n + 2``, per-entry commands settle at 2.01, and it
  measured x1.98.  The weight has since moved out of the embed into the
  template (every run is ``++`` or ``**``, and the stage after it adds the
  weight), which reads x1.83; it is held to the bound like everything else.

The gap between x2.06 and the x2.29 that was caught is narrow, which is the
honest reading: the statistic separates a single pass over the table from a
pass per entry, and nothing finer.

Steps, not seconds
------------------
The measurement is the command count, which stepping counts exactly, rather
than wall-clock.  A clock would make the verdict depend on machine load, and
this repository has already had a contended run invert a performance verdict.
The cost of a command is real and is *not* constant -- it is what makes BIO
quadratic on a linear command count -- but it belongs to the interpreter,
where ``docs/limitations.md`` records it, not to a contract on the generator.

So passing this is not a claim that a program is *fast*: Container runs
fourteen commands at six inputs and each divides a T-digit integer.  It is
the claim that the program does not issue more commands than a single pass
over its table.

Parity only
-----------
``linearity.py`` measures both table shapes because a route change moves
emitted size. Execution is measured on parity alone, which is the expensive
shape: checked against dense and against pseudo-random tables, those cost the
same or less, so parity bounds them.  That halves a budget this band does not
have to spare.

Rows are sampled
----------------
The worst row is what matters, but stepping all ``T`` rows at twelve inputs
is minutes, not seconds.  ``ROW_SAMPLE`` rows are taken per arity, evenly
spaced and always including the last, which is where these constructions do
their most work.  The sample is deterministic, so the *growth* it measures is
honest even where the absolute worst row is missed.

Rows that never halt
--------------------
Four languages answer by *not* halting (ArrowQueue, 123, Crement,
Vandevelo), so half their rows have no command count at all.  Those rows are
identified from ``answer_encoding`` and skipped rather than stepped: letting
them run to ``STEP_CAP`` cost 461 seconds of a 489-second run, to learn what
the truth table already said.  A row that caps anyway is dropped rather than
counted, so a truncated measurement can never pass as a small one.

A Painter Ant halts on no row at all -- its answer is a proven cycle in an
unconditional loop -- so it is exempt and not stepped.
"""

from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass
from math import log2
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs import describe, encode_inputs, generate, instantiate, make_vm
from esolangs.registry import BY_BOOLEAN
from tests.proofs._ledger import load as load_ledger
from tests.proofs._roadmap import load as load_audit
from tests.tools.test_boolean_contract import _parity

#: Cost band; see ``__main__.py``.  It steps every generator's program at
#: rising arity, which is tens of seconds and so cannot sit in CI.
BAND = "by-hand"
COST = 30.0

#: Most per-added-input growth in commands a settled generator may show.
#: Shared with ``linearity.py``: a single pass over the table doubles.
MAX_GROWTH = 2.15

#: A step outside this band is a route change rather than growth, exactly as
#: in ``linearity.py`` -- generators dispatch, and a switch moves the command
#: count by a factor that says nothing about asymptotics.
REGIME_BAND = (0.5, 4.0)

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
#: machine than in CI and quietly changes the verdict.
MAX_ARITY = 9
ARITY_OVERRIDE = {
    "b_tapemark": 7,
    "circuit_diagram": 7,
    "container": 6,
    "factor": 7,
    "flowchart": 8,
    "one_two_three": 8,
    "polynomial": 7,
    "qoibl": 6,
    "streetcode": 6,
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
#: silently deselect one.
EXEMPT = {
    "A Painter Ant": (
        "halts on no row -- an unconditional loop whose answer is a proven "
        "cycle, so there is no command count to grow"
    ),
}


def exempt_generators() -> dict[str, str]:
    """Every generator this contract does not hold to the bound.

    :data:`EXEMPT` plus the resource-ceiling rows of ``proofs.md`` and the
    roadmap audit rows whose execution-time cell is open, read from the
    documents the way ``linearity.py`` reads them: a generator that cannot
    be built past a low arity cannot produce the rungs a slope needs; COD's
    restored fork generator is the one the audit holds open.  Reading them
    means closing a cap row or an execution cell arms this contract against
    that generator with no edit here.
    """
    reasons = dict(EXEMPT)
    for row in load_ledger().rows:
        for label in ("cap", "exception"):
            if label in row.labels:
                reasons.setdefault(row.generator, f"proofs.md {label} row")
    for name in sorted(load_audit().execution_unsettled):
        reasons.setdefault(name, "roadmap scaling audit: execution open")
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


def _rows(table: str, halts: str | None) -> list[int]:
    """Which rows of ``table`` to step, the last candidate always included.

    ``halts`` is the answer bit that means "this row terminates", for the
    languages that answer by halting or not; rows spelling the other bit are
    skipped rather than stepped into the cap.  Those six were 461 seconds of
    a 489-second run before this -- every diverging row paying ``STEP_CAP``
    to tell us what the table already said.
    """
    candidates = [
        row for row in range(len(table)) if halts is None or table[row] == halts
    ]
    if len(candidates) <= ROW_SAMPLE:
        return candidates
    step = len(candidates) // ROW_SAMPLE
    keep = {*candidates[::step], candidates[-1]}
    return sorted(keep)


def _commands(name: str, table: str) -> int | None:
    """Worst sampled row's command count, or ``None`` if none finished.

    A row that reaches ``STEP_CAP`` is dropped rather than counted: for the
    languages that answer by not halting it is the answer, and for anything
    else it is a measurement this contract cannot make.
    """
    facts = describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        # Which bit the language spells by terminating, read rather than
        # assumed: it is ("halts", "diverges") for all three today.
        halts = str(list(facts["answer_encoding"]).index("halts"))
    inputs = len(table).bit_length() - 1
    program = generate(name, table, None)
    worst: int | None = None
    for row in _rows(table, halts):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, bits, None), ""
        else:
            source, stdin = program, encode_inputs(name, bits, table)
        machine = make_vm(name, source, stdin)
        steps = 0
        while not machine.halted and steps < STEP_CAP:
            machine.step()
            steps += 1
        if steps < STEP_CAP and (worst is None or steps > worst):
            worst = steps
    return worst


def _series(name: str, top: int) -> list[tuple[int, int]]:
    """(arity, worst sampled command count) for every arity that runs."""
    out: list[tuple[int, int]] = []
    for n in range(1, top + 1):
        try:
            count = _commands(name, _parity(n))
        except Exception:
            break
        if count is None or count == 0:
            continue
        out.append((n, count))
    return out


def _growth(window: list[tuple[int, int]]) -> float:
    """Per-added-input growth, as the fitted slope over ``window``.

    A least-squares line through ``log2(commands)`` against arity, rather
    than a ratio between two of them.  Every construction here wobbles --
    see ``MIN_RUNGS`` -- and a fit uses all five rungs instead of letting
    two endpoints decide.  Measured on this registry, it reads Taglate at
    x1.93 and S*bleq at x2.00 where an endpoint pair read x2.30 and x2.21,
    and still reads Minsky Swap at x2.29, whose commands per table entry
    are the input count rather than a constant.
    """
    xs = [float(arity) for arity, _ in window]
    ys = [log2(count) for _, count in window]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    spread = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / spread
    return 2.0**slope


def _regime_start(series: list[tuple[int, int]]) -> int:
    """The arity after the last route change."""
    lo, hi = REGIME_BAND
    start = series[0][0]
    for (_a, before), (b, after) in itertools.pairwise(series):
        if before and not lo <= after / before <= hi:
            start = b
    return start


def measure(key: str, name: str) -> Growth:
    """Worst per-input command growth, past any route change."""
    if name in EXEMPT:
        # Not stepped at all: A Painter Ant's rows run to the cap by
        # construction, which was 91 seconds spent rediscovering its
        # docstring.
        return Growth(name, reason=EXEMPT[name])
    top = ARITY_OVERRIDE.get(key, MAX_ARITY)
    series = _series(name, top)
    if len(series) < MIN_RUNGS:
        return Growth(name, reason="too few arities produced a halting row")
    start = _regime_start(series)
    past = [row for row in series if row[0] >= start]
    if len(past) < MIN_RUNGS:
        return Growth(name, reason="too few rungs past the last route change")
    ratio = _growth(past[-WINDOW:])
    return Growth(name, ratio, past[-1][0], start, past[-1][1])


def main() -> int:
    """Measure every generator and check the settled ones against the bound."""
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}
    exempt = exempt_generators()
    unknown = sorted(set(exempt) - set(by_display))
    assert not unknown, f"exempt names no such generator: {unknown}"

    measured = [measure(key, name) for name, key in sorted(by_display.items())]
    assert len(measured) == len(BY_BOOLEAN) == 60, "not every generator was measured"

    print(f"Execution contract: {len(measured)} generators, bound x{MAX_GROWTH}\n")
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
        if row.generator not in exempt and (row.ratio is None or row.ratio > MAX_GROWTH)
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
