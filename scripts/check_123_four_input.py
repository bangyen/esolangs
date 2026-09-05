#!/usr/bin/env python3
"""Exhaustively verify the 123 constructor at four inputs.

The sweep constructs every one of the 65,536 truth tables, substitutes all
16 input rows, and accepts a row only after an exact halt or repeated-state
verdict.  Progress is checkpointed after every table, so rerunning the same
command resumes at the first unfinished table.  ``--jobs`` parallelizes small
batches while preserving checkpoint order.

On the first failure, the checkpoint records the table, row, template,
instantiated program, and an interpreter replay trace.  The replay itself has
no step cap: it ends only at a halt, a repeated complete state, or an exception.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, cast

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine
from esolangs.tools.boolean.one_two_three_construct import (
    _replay_verdict,
    construct,
)

TABLES = 1 << 16
ROWS = 16
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = ROOT / "notes" / "123-four-input-coverage.json"
CONSTRUCTOR_SOURCE = (
    ROOT / "src" / "esolangs" / "tools" / "boolean" / "one_two_three_construct.py"
)


def _constructor_sha256() -> str:
    """Identify the exact constructor implementation a checkpoint covers."""
    return hashlib.sha256(CONSTRUCTOR_SOURCE.read_bytes()).hexdigest()


def _instantiate(template: str, row: int) -> str:
    """Substitute the four bits of ``row`` into ``template`` in name order."""
    program = template
    for i in range(4):
        bit = (row >> (3 - i)) & 1
        program = program.replace(f"{{X{i}}}", "1" if bit else "2")
    return program


def _trace(program: str) -> dict[str, Any]:
    """Return an uncapped command-by-command interpreter replay."""
    machine = _Machine(program, ScriptedIO(""))
    seen: dict[object, int] = {}
    states: list[object] = []
    try:
        while not machine.halted:
            state = machine.snapshot()
            if state in seen:
                return {
                    "outcome": "cycle",
                    "cycle_start": seen[state],
                    "cycle_end": len(states),
                    "states": states,
                }
            seen[state] = len(states)
            states.append(state)
            machine.step()
    except Exception as exc:  # the exception is the evidence being recorded
        return {
            "outcome": "exception",
            "exception": f"{type(exc).__name__}: {exc}",
            "states": states,
        }
    states.append(machine.snapshot())
    return {"outcome": "halt", "states": states}


def _check_table(table_index: int) -> dict[str, Any]:
    """Construct and verify one table, returning a serializable result."""
    table = format(table_index, "016b")
    started = time.monotonic()
    try:
        # The harness supplies the independent closing gate below.
        template = construct(table, verify=False)
    except Exception as exc:
        return {
            "ok": False,
            "table_index": table_index,
            "table": table,
            "row": None,
            "template": None,
            "program": None,
            "expected": None,
            "actual": None,
            "replay_trace": {
                "outcome": "construction_exception",
                "exception": f"{type(exc).__name__}: {exc}",
            },
        }

    for row in range(ROWS):
        program = _instantiate(template, row)
        try:
            actual = _replay_verdict(program)
        except Exception as exc:
            actual = f"{type(exc).__name__}: {exc}"
        if actual != table[row]:
            return {
                "ok": False,
                "table_index": table_index,
                "table": table,
                "row": row,
                "template": template,
                "program": program,
                "expected": table[row],
                "actual": actual,
                "replay_trace": _trace(program),
            }
    return {
        "ok": True,
        "table_index": table_index,
        "seconds": time.monotonic() - started,
        "template_size": len(template),
    }


def _write_json(path: Path, value: object) -> None:
    """Atomically replace ``path`` with formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _initial_state(start: int, stop: int) -> dict[str, Any]:
    """Return a fresh checkpoint for the requested half-open range."""
    return {
        "version": 2,
        "constructor_sha256": _constructor_sha256(),
        "start": start,
        "stop": stop,
        "next_table": start,
        "tables_checked": 0,
        "rows_checked": 0,
        "slowest": None,
        "failure": None,
        "complete": False,
    }


def _load_state(path: Path, start: int, stop: int) -> dict[str, Any]:
    """Load a compatible checkpoint, or make a fresh one."""
    if not path.exists():
        return _initial_state(start, stop)
    state = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    expected = (2, _constructor_sha256(), start, stop)
    actual = (
        state.get("version"),
        state.get("constructor_sha256"),
        state.get("start"),
        state.get("stop"),
    )
    if actual != expected:
        raise ValueError(
            "checkpoint constructor or range differs: "
            f"found {actual}, expected {expected}"
        )
    return state


def _record_success(state: dict[str, Any], result: dict[str, Any]) -> None:
    """Advance ``state`` by one successful table result."""
    state["next_table"] = result["table_index"] + 1
    state["tables_checked"] += 1
    state["rows_checked"] += ROWS
    slowest = state["slowest"]
    if slowest is None or result["seconds"] > slowest["seconds"]:
        state["slowest"] = {
            "table_index": result["table_index"],
            "table": format(result["table_index"], "016b"),
            "seconds": result["seconds"],
            "template_size": result["template_size"],
        }


def run(start: int, stop: int, jobs: int, checkpoint: Path) -> bool:
    """Run or resume a range; return whether every requested table passed."""
    state = _load_state(checkpoint, start, stop)
    next_table = int(state["next_table"])
    if state["complete"]:
        print(f"already complete: {state['tables_checked']} tables", flush=True)
        return True
    if state["failure"] is not None:
        print(f"failure already recorded in {checkpoint}", flush=True)
        return False

    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        while next_table < stop:
            end = min(stop, next_table + max(1, jobs * 4))
            for result in executor.map(_check_table, range(next_table, end)):
                if not result["ok"]:
                    state["failure"] = result
                    _write_json(checkpoint, state)
                    print(
                        f"FAIL table={result['table']} row={result['row']}; "
                        f"recorded in {checkpoint}",
                        flush=True,
                    )
                    return False
                _record_success(state, result)
                next_table = int(state["next_table"])
                _write_json(checkpoint, state)
                if state["tables_checked"] % 100 == 0:
                    elapsed = time.monotonic() - started
                    print(
                        f"checked {state['tables_checked']}/{stop - start} tables "
                        f"through {next_table - 1:04x} ({elapsed:.1f}s this run)",
                        flush=True,
                    )

    state["complete"] = True
    _write_json(checkpoint, state)
    print(
        f"PASS: {state['tables_checked']} tables, {state['rows_checked']} rows; "
        f"checkpoint {checkpoint}",
        flush=True,
    )
    return True


def main() -> int:
    """Parse arguments and return the exhaustive check's exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=TABLES)
    parser.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    args = parser.parse_args()
    if not 0 <= args.start <= args.stop <= TABLES:
        parser.error("require 0 <= start <= stop <= 65536")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        passed = run(args.start, args.stop, args.jobs, args.checkpoint)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
