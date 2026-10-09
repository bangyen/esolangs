"""Price and execute the canonical-piece path screen through eight inputs.

Sizes use characters for text and rectangular area for grids/raster. Every
artifact executes the first, middle and last row; --all-rows executes all.
Refused paths and timeouts remain explicit; neither is evidence of a wall.
"""

import argparse
import json
import random
import sys
import tomllib
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _build import ignore, random_table, source_size, tiled
from paths import paths

import esolangs
from esolangs._evaluate import _terminates
from esolangs.interpreters.io import ScriptedIO
from esolangs.registry import resolve


def corpus(n: int) -> dict[str, str]:
    """Return constants, dense, constant-half, tiled and ignored-input tables."""
    rng = random.Random(2026 + n)
    dense = random_table(n, rng)
    found = {"zero": "0" * (1 << n), "one": "1" * (1 << n), "dense": dense}
    if n > 1:
        inner = random_table(n - 1, rng)
        found["constant-half"] = inner + "0" * len(inner)
        for at in sorted({0, n // 2, n - 1}):
            found[f"ignored-{at}"] = ignore(inner, at)
    if n > 2:
        found["tiled"] = tiled(n, rng)
    return found


def size(name: str, program: esolangs.Program) -> int:
    """Return the emitted size, grids measured as rectangular area."""
    return source_size(name, program)


def execute(
    name: str,
    program: esolangs.Program,
    table: str,
    options: dict[str, Any],
    *,
    all_rows: bool,
) -> int:
    """Check bounded actual answers, including cycle-proved termination answers."""
    n = len(table).bit_length() - 1
    facts = esolangs.describe(name)
    settings = options.get("settings")
    rows = (
        range(len(table)) if all_rows else sorted({0, len(table) // 2, len(table) - 1})
    )
    source: esolangs.Program
    for row in rows:
        bits = [int(bit) for bit in format(row, f"0{n}b")]
        if facts["parameterized"]:
            source = esolangs.instantiate(name, program, bits, settings=settings)
            stdin = ""
        else:
            source = program
            stdin = esolangs.encode_inputs(name, bits, truth_table=table)
        if facts["answer_mode"] == "termination":
            assert isinstance(source, str)
            encoding = facts["answer_encoding"]
            actual = _terminates(
                name,
                source,
                stdin,
                2,
                str(encoding.index("halts")),
                str(encoding.index("diverges")),
                settings=settings,
            )
        else:
            actual = esolangs.read_answer(
                name,
                esolangs.run(name, source, stdin=stdin, timeout=2, settings=settings),
            )
        if actual != table[row]:
            raise ValueError(f"{name} row {row}: {actual!r} != {table[row]!r}")
    return len(rows)


def audit(
    name: str,
    n: int,
    *,
    all_rows: bool,
    done: set[tuple[str, int, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Measure and execute each path, retaining refusals and timed-out jobs."""
    records = []
    for label, options in paths(name).items():
        for piece, table in corpus(n).items():
            if done and (name, n, label, piece) in done:
                continue
            started = perf_counter()
            record: dict[str, Any] = {
                "language": name,
                "n": n,
                "path": label,
                "piece": piece,
            }
            try:
                built: list[esolangs.Program] = []
                measured: list[int] = []

                def build(*_args: object) -> None:
                    built.append(esolangs.generate(name, table, **options))  # noqa: B023
                    measured.append(size(name, built[0]))  # noqa: B023

                esolangs._run(build, "", ScriptedIO(""), 2)  # noqa: SLF001
                program = built[0]
                record["size"] = measured[0]
                record["rows"] = execute(
                    name, program, table, options, all_rows=all_rows
                )
                record["status"] = "executed"
            except (ValueError, esolangs.ArgumentError) as exc:
                # Execution errors are failures, never generation refusals.
                if built and measured:
                    raise
                record["status"] = "refused"
                record["reason"] = str(exc)
            except esolangs.ExecutionTimeoutError:
                record["status"] = "timeout"
            record["seconds"] = perf_counter() - started
            records.append(record)
    return records


def controls() -> dict[str, int]:
    """Execute historical canonical-gap fixtures against current generators."""
    found = {}
    root = Path(__file__).resolve().parents[2] / "tests/fixtures"
    for path in sorted(root.glob("*/canonical_*.toml")):
        name = resolve(path.parent.name)
        case = tomllib.loads(path.read_text(encoding="utf-8"))
        table, old = case["truth_table"], case["baseline"]
        new = esolangs.generate(name, table)
        execute(name, old, table, {}, all_rows=True)
        execute(name, new, table, {}, all_rows=True)
        saving = size(name, old) - size(name, new)
        if saving <= 0:
            raise ValueError(f"canonical screen positive control did not fire: {path}")
        found[case["label"]] = saving
    if not found:
        raise ValueError("canonical screen has no positive controls")
    return found


def main() -> None:
    """Print JSONL evidence; the pilot prices the same paths at four inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="*")
    parser.add_argument("--price", action="store_true")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--all-rows", action="store_true")
    args = parser.parse_args()
    names = args.languages or [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["boolean_generator"]
    ]
    print(json.dumps({"positive_controls": controls()}), flush=True)
    done = set()
    if args.resume:
        for line in args.resume.read_text().splitlines():
            record = json.loads(line)
            if "language" in record and (
                not args.all_rows
                or record["status"] != "executed"
                or record["rows"] == 1 << record["n"]
            ):
                done.add(
                    (record["language"], record["n"], record["path"], record["piece"])
                )
    for name in names:
        for n in (4,) if args.price else range(1, 9):
            for record in audit(name, n, all_rows=args.all_rows, done=done):
                print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
