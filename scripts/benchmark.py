"""Measure one generator with repeatable size, time, and command counts."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any

import esolangs


def _bits(row: int, inputs: int) -> list[int]:
    return [(row >> shift) & 1 for shift in range(inputs - 1, -1, -1)]


def _source_size(program: str | esolangs.Raster) -> int:
    if isinstance(program, str):
        return len(program)
    return sum(len(row) for row in program.rows)


def _commands(
    language: str,
    program: str | esolangs.Raster,
    table: str,
    row: int,
    cap: int,
) -> int | None:
    facts = esolangs.describe(language)
    if not isinstance(program, str) or not facts["steppable_to_answer"]:
        return None
    inputs = len(table).bit_length() - 1
    bits = _bits(row, inputs)
    source = program
    stdin = esolangs.encode_inputs(language, bits)
    if facts["parameterized"]:
        source = esolangs.instantiate(language, program, bits)
        stdin = ""
    vm = esolangs.make_vm(language, source, stdin)
    steps = 0
    while not vm.halted and steps < cap:
        vm.step()
        steps += 1
    return steps if vm.halted else None


def measure(
    language: str, table: str, *, repeat: int, row: int, step_cap: int
) -> dict[str, Any]:
    """Return one benchmark record; timings are best-of-repeat."""
    timings: list[int] = []
    program: str | esolangs.Raster | None = None
    for _ in range(repeat):
        started = time.perf_counter_ns()
        program = esolangs.generate(language, table)
        timings.append(time.perf_counter_ns() - started)
    assert program is not None
    return {
        "schema": 1,
        "language": esolangs.describe(language)["name"],
        "truth_table": table,
        "inputs": len(table).bit_length() - 1,
        "row": row,
        "source_kind": esolangs.describe(language)["source_kind"],
        "source_units": _source_size(program),
        "generation_ns_best": min(timings),
        "generation_ns_median": int(statistics.median(timings)),
        "commands": _commands(language, program, table, row, step_cap),
        "step_cap": step_cap,
    }


def main(argv: list[str] | None = None) -> int:
    """Print a stable JSON benchmark record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language")
    parser.add_argument("truth_table")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--row", type=int)
    parser.add_argument("--step-cap", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    inputs = len(args.truth_table).bit_length() - 1
    row = (1 << inputs) - 1 if args.row is None else args.row
    if not 0 <= row < 1 << inputs:
        parser.error(f"--row must be in [0, {(1 << inputs) - 1}]")
    result = measure(
        args.language,
        args.truth_table,
        repeat=args.repeat,
        row=row,
        step_cap=args.step_cap,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
