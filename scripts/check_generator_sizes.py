"""Hold every generator's emitted size and step count to a committed baseline.

What a generator emits, and how long the emitted program runs, is the claim
this collection is *about* -- and nothing measured it automatically.
``scripts/benchmark.py`` could, but no gate, workflow or test ran it over more
than one language, which is how its parameterized branch came to raise
``ArgumentError`` for every parameterized language without anyone noticing.

Both pinned quantities are exact, not sampled: ``source_units`` is
``len(rendered)`` and ``commands`` is the step count to halt, and neither
depends on the machine.  So the check is equality, and any change -- a
regression *or* a win -- fails until ``--update`` rewrites the baseline, which
puts the delta in the diff where review sees it.

Generation *time* is deliberately not pinned.  It is load- and machine-
dependent (CI runs ~2.3x slower than a laptop here), and a gate that flakes is
worse than no gate; ``weekly.yml`` records timings as an artifact instead, so
the trend stays readable without blocking a PR on noise.

Run::

    python scripts/check_generator_sizes.py            # verify
    python scripts/check_generator_sizes.py --update   # re-record
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import measure  # noqa: E402

import esolangs  # noqa: E402

BASELINE = REPO_ROOT / "tests" / "fixtures" / "generator_sizes.json"

#: One table per arity, 2 through 4.  Each is the parity function on its
#: inputs, which no generator special-cases: a constant or a single-variable
#: table would let a route that collapses dependencies look linear.  Four is
#: the ceiling because the whole sweep stays under ten seconds there, and the
#: registry-wide growth contract (``tests/proofs/deep/linearity.py``) is what
#: measures to n=12.
TABLES = ("0110", "01101001", "0110100110010110")

#: Far below ``benchmark.py``'s default.  Every language that halts on this
#: corpus does so in well under this many steps; the thirteen records with a
#: null ``commands`` are the raster and non-steppable languages, which return
#: None before stepping rather than on the cap.
STEP_CAP = 200_000

SCHEMA = 1


def sweep(*, repeat: int = 1) -> list[dict[str, Any]]:
    """Return one full benchmark record per (language, table), timings and all."""
    return [
        measure(
            name,
            table,
            repeat=repeat,
            row=(1 << (len(table).bit_length() - 1)) - 1,
            step_cap=STEP_CAP,
        )
        for name in esolangs.list_languages()
        for table in TABLES
    ]


def baseline(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Project a sweep onto the deterministic fields, keyed by name and table.

    The timings stay out: they are what makes a sweep unrepeatable, and the
    whole point of the baseline is that re-running it on another machine gives
    the same answer.
    """
    by_name: dict[str, dict[str, Any]] = {}
    for record in records:
        by_name.setdefault(record["language"], {})[record["truth_table"]] = {
            "source_units": record["source_units"],
            "commands": record["commands"],
        }
    return {
        "schema": SCHEMA,
        "step_cap": STEP_CAP,
        "tables": list(TABLES),
        "records": by_name,
    }


def collect() -> dict[str, Any]:
    """Return the baseline as measured now."""
    return baseline(sweep())


def differences(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Return one line per disagreement between a baseline and a measurement.

    Languages and tables are compared by name, so adding a language reports as
    an addition rather than shifting every row after it.
    """
    lines: list[str] = []
    if old.get("schema") != new["schema"]:
        return [f"baseline schema {old.get('schema')!r}, expected {SCHEMA}"]
    if old.get("tables") != new["tables"]:
        return [f"baseline tables {old.get('tables')!r}, expected {list(TABLES)}"]
    was, is_ = old.get("records", {}), new["records"]
    for name in sorted(set(was) | set(is_)):
        if name not in was:
            lines.append(f"{name}: not in the baseline (new language?)")
            continue
        if name not in is_:
            lines.append(f"{name}: in the baseline but not in the registry")
            continue
        for table in new["tables"]:
            # Both sides are read with .get: a record missing a table has to
            # report as a difference, not raise -- a gate that crashes on an
            # incomplete sweep says nothing about the sweep it did finish.
            before = was[name].get(table, {})
            after = is_[name].get(table, {})
            for field in ("source_units", "commands"):
                if before.get(field) != after.get(field):
                    lines.append(
                        f"{name} [{table}] {field}: "
                        f"{before.get(field)} -> {after.get(field)}"
                    )
    return lines


def main(argv: list[str] | None = None) -> int:
    """Compare against the baseline, or rewrite it under ``--update``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="re-record the baseline")
    parser.add_argument(
        "--timings",
        type=Path,
        help="also write the full sweep, timings included, to this path",
    )
    parser.add_argument(
        "--repeat", type=int, default=1, help="timing samples per record"
    )
    args = parser.parse_args(argv)

    records = sweep(repeat=args.repeat)
    if args.timings is not None:
        args.timings.parent.mkdir(parents=True, exist_ok=True)
        args.timings.write_text(
            json.dumps(records, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.timings}")
    measured = baseline(records)
    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(measured, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    if not BASELINE.exists():
        print(f"no baseline at {BASELINE}; run with --update", file=sys.stderr)
        return 1
    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
    lines = differences(recorded, measured)
    if not lines:
        count = len(measured["records"]) * len(TABLES)
        print(f"{count} generator measurements match the baseline")
        return 0
    print("generator size/step baseline changed:", file=sys.stderr)
    for line in lines:
        print(f"  {line}", file=sys.stderr)
    print(
        "\nIf the change is intended, re-record it so the diff carries it:\n"
        "  python scripts/check_generator_sizes.py --update",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
