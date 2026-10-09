#!/usr/bin/env python3
"""Executed lemma checks behind ``the relevant generator tests``."""

from __future__ import annotations

import argparse
import random
import sys

from esolangs.interpreters.grid_based.arrowqueue import _advance, _Machine
from esolangs.tools.arrowqueue import _DRAINED_RING, _STAGE, arrowqueue
from esolangs.tools.helpers import TEMPLATE_CHAR
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.fills import fill

_instantiate_arrowqueue = fill("ArrowQueue")


#: Cost band; see ``__main__.py``. Total over every arity, so nothing here enumerates
#: tables to establish the claim -- the best gating ratio in the directory.
BAND = "verify"
COST = 2.0

#: The four loop components the ring's corners must pop, in queue order.
RDLU = (0, 1, 2, 3)

failures: list[str] = []


def report(lemma: str, *, ok: bool, detail: str) -> None:
    """Print one lemma line and record a failure."""
    status = "ok  " if ok else "FAIL"
    print(f"[{status}] {lemma:28s} {detail}", flush=True)
    if not ok:
        failures.append(lemma)


def _run_block(
    rows: list[str], state: tuple[int, int, int, tuple[int, ...]], cap: int = 100_000
) -> tuple[int, int, int, tuple[int, ...], bool]:
    """Step a bare block from ``state`` until it leaves the block's rectangle."""
    width = max(map(len, rows), default=0)
    grid = tuple(row.ljust(width) for row in rows)
    current = (*state, False)
    for _ in range(cap):
        row, col, _d, _q, done = current
        if done or not (0 <= row < len(grid) and 0 <= col < width):
            break
        current = _advance(current, grid, width)
    return current


def _verdict_from(rows: list[str], state: tuple[int, int, int, tuple[int, ...]]) -> str:
    """Halt-or-cycle verdict from an arbitrary entry state."""
    machine = _Machine(list(rows))
    machine.state = (*state, not machine.grid)
    return "0" if run_until_halt_or_cycle(machine) else "1"


def check_s_stage() -> None:
    """S: a cascade stage maps ``m`` markers and a bit to ``2m + bit``."""
    bad = 0
    cases = 0
    for m in range(40):
        for bit in (0, 1):
            cases += 1
            rows = [row.replace(TEMPLATE_CHAR, "~" if bit else ".") for row in _STAGE]
            row, col, d, queue, _done = _run_block(rows, (0, 3, 1, (*([1] * m), 0)))
            if (row, col, d) != (len(rows), 3, 1) or queue != (
                *([1] * (2 * m + bit)),
                0,
            ):
                bad += 1
    report(
        "S stage is Horner",
        ok=bad == 0,
        detail=f"m=0..39 x 2 bits = {cases} stages, {bad} wrong counts or exits",
    )


def check_d_drain() -> None:
    """D: the cascade's drained ring sustains for every marker count."""
    bad = 0
    for m in range(40):
        state = (0, 1, 1, (*([1] * m), 0, *RDLU))
        if _verdict_from(_DRAINED_RING, state) != "1":
            bad += 1
    report(
        "D drain is reusable",
        ok=bad == 0,
        detail=f"m=0..39 markers into one drained ring, {bad} halts",
    )


def check_deep_composition() -> None:
    """Composition past every swept arity: whole programs at n = 6..12."""
    bad = 0
    detail = []
    for n in (1, 2, 3, 4, 6, 8, 10, 12):
        table = "".join(random.choice("01") for _ in range(2**n))
        template = arrowqueue(table)
        size = 0
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            program = _instantiate_arrowqueue(template, bits)
            size = max(size, len(program))
            if _verdict_from(program.split("\n"), (0, 0, 0, ())) != table[combo]:
                bad += 1
        detail.append(f"n={n}({size}B)")
    report(
        "deep composition", ok=bad == 0, detail=f"{' '.join(detail)}, {bad} failures"
    )

    bad = 0
    for n in (8, 10):
        for table in (
            "1" * (2**n),
            "0" * (2**n),
            "0" * (2**n - 1) + "1",
            "1" + "0" * (2**n - 1),
            "01" * (2 ** (n - 1)),
        ):
            template = arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                program = _instantiate_arrowqueue(template, bits)
                if _verdict_from(program.split("\n"), (0, 0, 0, ())) != table[combo]:
                    bad += 1
    report(
        "deep extremes",
        ok=bad == 0,
        detail=f"all-ones/zeros/single-1/alternating at n=8,10, {bad} failures",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the lemma checks and return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deep",
        action="store_true",
        help="add high-arity composition runs (~2 minutes)",
    )
    args = parser.parse_args(argv)

    # Seeded so the sampled arities and random tables are reproducible.
    random.seed(20240904)

    check_s_stage()
    check_d_drain()
    if args.deep:
        check_deep_composition()

    print()
    if failures:
        print(f"{len(failures)} lemma(s) FAILED: {', '.join(failures)}")
        return 1
    print("all lemmas hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
