"""The registry-wide workspace contract: written state against table length."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs import describe, encode_inputs, generate, instantiate
from esolangs.debugger import make_vm
from esolangs.registry import BY_BOOLEAN
from scripts.benchmark import WrittenState
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import (
    MAX_GROWTH,
    MIN_RUNGS,
    POLY_GROWTH,
    STEP_CAP,
    WINDOW,
    _dense,
    _growth,
    _rows,
)
from tests.proofs.deep.linearity import _regime_start
from tests.tools.test_boolean_contract import _parity

#: Cost band; see ``__main__.py``.
BAND = "by-hand"
COST = 55.0

#: Most growth a ``T log T`` row may show: T cells of ``log T``-bit values
#: (BIO's loop counters, 123's painted indices) read x2.32, a quadratic x4.
LOG_GROWTH = 2.5

BOUND = {"poly n": POLY_GROWTH, "linear": MAX_GROWTH, "T log T": LOG_GROWTH}

#: Arity ceilings, fixed for the reason ``linearity.py`` gives.  Written
#: state is recounted every step, so a rung costs ~4x the last: 9 throughout
#: was 207s.  Lowered where a generator's top rung passed ~3s; FALSE and
#: BFStack keep 9, since their poly n fit (x1.49, x1.48) is steeper lower down.
MAX_ARITY = 8
ARITY_OVERRIDE = {
    "addsubjump": 6,
    "b_tapemark": 7,
    "bfstack": 9,
    "circlefuck": 6,
    "dimensional": 7,
    "false": 9,
    "laserfuck": 9,
    "flowchart": 7,
    "line": 7,
    "rotfuck": 6,
    "slow_acv_mammalian": 6,
    "streetcode": 7,
    "taglate": 7,
    "unlambda": 6,
}


@dataclass
class Growth:
    """One generator's measured written-state growth."""

    generator: str
    workspace: str
    ratio: float | None = None
    arity: int = 0
    bits: int = 0
    reason: str = ""


def _written(name: str, table: str) -> int | None:
    """Worst sampled halting row's peak written bits, or ``None``."""
    facts = describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        halts = str(list(facts["answer_encoding"]).index("halts"))
    inputs = len(table).bit_length() - 1
    program = generate(name, table, width=None)
    worst: int | None = None
    sampled = _rows(table, halts)
    if not sampled:
        return None
    # First, middle and last of the execution sample: a rung recounts the
    # written state every step, and seven rows put the band at 126s.
    for row in sorted({sampled[0], sampled[len(sampled) // 2], sampled[-1]}):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        if facts["parameterized"]:
            source, stdin = instantiate(name, program, bits, width=None), ""
        else:
            source, stdin = program, encode_inputs(name, bits, truth_table=table)
        machine = make_vm(name, source, stdin=stdin)
        state = WrittenState(machine.snapshot())
        steps = 0
        while not machine.halted and steps < STEP_CAP:
            machine.step()
            steps += 1
            state.sample(machine.snapshot())
        if steps < STEP_CAP and (worst is None or state.bits > worst):
            worst = state.bits
    return worst


def _self_check() -> tuple[float, float, float]:
    """Run the fit on ``n**2``, ``T`` and ``T log T`` bit series."""
    window = list(range(5, 5 + WINDOW))
    poly = _growth([(n, n * n) for n in window])
    linear = _growth([(n, 2**n) for n in window])
    log = _growth([(n, 2**n * n) for n in window])
    quadratic = _growth([(n, 4**n) for n in window])
    assert poly <= POLY_GROWTH, f"n**2 control read x{poly}"
    assert POLY_GROWTH < linear <= MAX_GROWTH, f"T control read x{linear}"
    assert MAX_GROWTH < log <= LOG_GROWTH < quadratic, f"T log T control read x{log}"
    return poly, linear, log


def measure(
    key: str, name: str, workspace: str, table: Callable[[int], str] = _parity
) -> Growth:
    """Worst per-input written-state growth, past any route change."""
    series: list[tuple[int, int]] = []
    for n in range(1, ARITY_OVERRIDE.get(key, MAX_ARITY) + 1):
        try:
            bits = _written(name, table(n))
        except Exception:
            break
        if bits:
            series.append((n, bits))
    if len(series) < MIN_RUNGS:
        return Growth(name, workspace, reason="too few arities produced a halting row")
    past = [row for row in series if row[0] >= _regime_start(series)]
    if len(past) < MIN_RUNGS:
        return Growth(
            name, workspace, reason="too few rungs past the last route change"
        )
    return Growth(name, workspace, _growth(past[-WINDOW:]), past[-1][0], past[-1][1])


def main() -> int:
    """Measure every measured-class row and check it against its bound."""
    by_display = {lang.name: key for key, lang in BY_BOOLEAN.items()}
    rows = load_ledger().rows
    assert {row.generator for row in rows} == set(by_display), "ledger != registry"

    poly, linear, log = _self_check()
    print(f"control: n**2 x{poly:.3f}, T x{linear:.3f}, T log T x{log:.3f}\n")

    measured = []
    for row in rows:
        if row.workspace_class not in BOUND:
            continue
        key = by_display[row.generator]
        growth = measure(key, row.generator, row.workspace_class)
        if row.workspace_class == "poly n":
            # Parity has n ANF terms; a poly n claim must survive a dense table.
            dense = measure(key, row.generator, row.workspace_class, _dense)
            if dense.ratio is None or (growth.ratio or 0) < dense.ratio:
                growth = dense
        measured.append(growth)
    print(f"Workspace contract: {len(measured)} generators\n")
    print(f"  {'generator':30s} {'class':7s} {'growth':>7s} {'bits':>8s}")
    for row in sorted(measured, key=lambda r: -(r.ratio or 0)):
        if row.ratio is None:
            print(f"  {row.generator:30s} {row.workspace:7s} UNPROVEN  {row.reason}")
            continue
        print(
            f"  {row.generator:30s} {row.workspace:7s} x{row.ratio:6.3f} "
            f"{row.bits:8d}  n={row.arity}"
        )
    skipped = [row for row in rows if row.workspace_class not in BOUND]
    print(f"\n{len(skipped)} unmeasured:")
    for row in skipped:
        print(f"  {row.generator:30s} {row.workspace_clause}")

    failures = [
        row for row in measured if row.ratio is None or row.ratio > BOUND[row.workspace]
    ]
    if failures:
        print(f"\n{len(failures)} generator(s) exceed their workspace class:")
        for row in failures:
            print(f"  {row.generator}: {row.reason or f'x{row.ratio:.3f}'}")
        return 1
    print(f"\nall {len(measured)} measured generators inside their class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
