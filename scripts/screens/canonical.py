"""Price and execute the canonical-piece path screen through eight inputs.

Sizes use characters for text and rectangular area for grids/raster. Every
artifact executes the first, middle and last row; --all-rows executes all.
Refused paths and timeouts remain explicit; neither is evidence of a wall.
"""

import argparse
import hashlib
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import asdict, is_dataclass

from benchmark import source_identity

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
    checkout: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Measure and execute each path, retaining refusals and timed-out jobs."""
    records = []
    checkout = source_identity() if checkout is None else checkout
    for label, options in paths(name).items():
        for piece, table in corpus(n).items():
            identity = evidence_identity(checkout, table, options)
            if done and (name, n, label, piece) in done:
                continue
            started = perf_counter()
            record: dict[str, Any] = {
                "language": name,
                "n": n,
                "path": label,
                "piece": piece,
                "schema": 1,
                "identity": identity,
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


def evidence_identity(
    checkout: dict[str, Any], table: str, options: dict[str, Any]
) -> dict[str, Any]:
    """Bind source, the exact seeded table and serializable generation settings."""
    settings = {
        key: asdict(value)
        if is_dataclass(value) and not isinstance(value, type)
        else value
        for key, value in options.items()
    }
    return {
        "checkout": checkout,
        "table_sha256": hashlib.sha256(table.encode("ascii")).hexdigest(),
        "settings_sha256": hashlib.sha256(
            json.dumps(settings, sort_keys=True).encode()
        ).hexdigest(),
    }


def resume(
    path: Path, checkout: dict[str, Any], *, all_rows: bool
) -> set[tuple[str, int, str, str]]:
    """Resume only executed, matching records; retry refusals and timeouts."""
    with path.open("rb") as stream:
        data = stream.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("canonical resume exceeds eight MiB")
    done = set()
    for line in data.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("invalid canonical resume record")
        if "language" not in record:
            continue
        if (
            type(record.get("schema")) is not int
            or record.get("schema") != 1
            or not isinstance(record.get("identity"), dict)
        ):
            raise ValueError("canonical resume lacks source identity")
        if not isinstance(record["language"], str):
            raise ValueError("invalid canonical resume language")
        name = resolve(record["language"])
        n = record.get("n")
        if type(n) is not int or not 1 <= n <= 8:
            raise ValueError("invalid canonical resume arity")
        label, piece = record.get("path"), record.get("piece")
        choices, tables = paths(name), corpus(n)
        if (
            not isinstance(label, str)
            or not isinstance(piece, str)
            or label not in choices
            or piece not in tables
        ):
            raise ValueError("canonical resume path or corpus changed")
        expected = evidence_identity(checkout, tables[piece], choices[label])
        if record["identity"] != expected:
            raise ValueError("canonical resume source, settings or corpus changed")
        if record.get("status") != "executed":
            continue
        expected_rows = len(tables[piece]) if all_rows else min(3, len(tables[piece]))
        if type(record.get("rows")) is not int or record["rows"] not in {
            min(3, len(tables[piece])),
            len(tables[piece]),
        }:
            raise ValueError("invalid canonical resume row coverage")
        if record["rows"] >= expected_rows:
            done.add((name, n, label, piece))
    return done


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
    checkout = source_identity()
    done = set()
    if args.resume:
        try:
            done = resume(args.resume, checkout, all_rows=args.all_rows)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    for name in names:
        for n in (4,) if args.price else range(1, 9):
            for record in audit(
                name, n, all_rows=args.all_rows, done=done, checkout=checkout
            ):
                print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
