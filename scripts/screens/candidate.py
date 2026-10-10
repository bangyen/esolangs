"""Check a candidate generator against the shipped one, every row on the interpreter.

``python scripts/screens/candidate.py LANG FILE.py:FUNC [--target MODULE:ATTR]``

``FUNC`` stands in for the language's registered generator, or for
``MODULE:ATTR`` (an inner piece such as ``esolangs.tools.minifuck:_solve``),
while ``esolangs.generate`` runs, so the candidate gets the shipped wrapping,
width and template provenance.  Each arity gets random tables, tiled ones
(subtrees repeat) and ignored-input ones (a random table plus an input it
never reads, first, middle and last).  Rows run through ``benchmark``'s
executor, all of them up to ``--rows`` per table and a sample above.

Per family: tables, changed, wrong rows, larger, the new/old size ratio
(min, mean) and the worst steps of a row, old -> new.  Any wrong row, or a
table the candidate raises on, exits 1.
"""

import argparse
import importlib
import importlib.util
import json
import math
import random
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _atomic import write_text
from _benchmark_client import Worker
from _build import ignore, random_table, tiled
from _candidate_evidence import dependencies_changed, read_json
from _candidate_evidence import identity as _candidate_identity
from _candidate_evidence import replay as read_replay
from benchmark import _execute, source_identity

import esolangs
from esolangs.registry import LANGUAGES, resolve

#: Steps one row may take before it counts as wrong.
CAP = 10**7


def _load(spec: str) -> Callable[..., object]:
    """Return ``FUNC`` from ``FILE.py:FUNC``, importing the file by path."""
    path, _, name = spec.rpartition(":")
    sys.path.insert(0, str(Path(path).resolve().parent))
    module_spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    assert module_spec is not None, path
    assert module_spec.loader is not None, path
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return getattr(module, name)  # type: ignore[no-any-return]


@dataclass
class _Tally:
    tables: int = 0
    changed: int = 0
    wrong: int = 0
    larger: int = 0
    ratios: list[float] = field(default_factory=list)
    old_steps: int = 0
    new_steps: int = 0


@contextmanager
def _patched(
    language: str, target: str | None, fn: Callable[..., object]
) -> Iterator[None]:
    """Run the body with ``fn`` in place of the generator or ``target``."""
    if target is None:
        owner: object = LANGUAGES[language]
        attr = "boolean"
    else:
        module_name, _, attr = target.partition(":")
        owner = importlib.import_module(module_name)
    old = getattr(owner, attr)
    object.__setattr__(owner, attr, fn)  # Language is a frozen dataclass
    try:
        yield
    finally:
        object.__setattr__(owner, attr, old)


def _tables(n: int, rng: random.Random, count: int) -> Iterator[tuple[str, str]]:
    """Yield ``(family, table)`` at arity ``n``."""
    for _ in range(count):
        yield "random", random_table(n, rng)
    for _ in range(count if n >= 3 else 0):
        yield "tiled", tiled(n, rng)
    for at in sorted({0, n // 2, n - 1}):
        for _ in range(count):
            yield "ignored", ignore(random_table(n - 1, rng), at)


def plan(lo: int, hi: int, count: int, rows: int, cap: int) -> dict[str, int]:
    """Count generation cases and bounded row work without building tables."""
    tables = executions = 0
    for n in range(lo, hi + 1):
        cases = count * (1 + int(n >= 3) + len({0, n // 2, n - 1}))
        tables += cases
        executions += 2 * cases * min(rows, 1 << n)
    return {
        "tables": tables,
        "row_executions": executions,
        "step_bound": cap * executions,
        "largest_table_bits": 1 << hi,
    }


def _run_case(
    arguments: dict[str, Any], generation_timeout: float, remaining: float
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="candidate-dependencies-") as directory:
        path = Path(directory) / "dependencies.json"
        worker = Worker(
            [sys.executable, str(Path(__file__).with_name("_candidate_worker.py"))]
        )
        try:
            result: dict[str, Any] = worker.measure(
                {**arguments, "dependency_report": str(path)},
                {},
                generation_timeout,
                total_timeout=remaining,
            )
            result["runtime_dependencies"] = read_json(path)
            return result
        except Exception as error:
            if path.exists():
                error.__dict__["candidate_dependencies"] = read_json(path)
            raise
        finally:
            worker.close()


def _worst(
    language: str,
    program: esolangs.Program,
    table: str,
    rows: list[int],
    timeout: float = 30.0,
) -> tuple[int, int]:
    """Return ``(wrong rows, worst steps)``; an unanswered row is wrong."""
    wrong = worst = 0
    for row in rows:
        result = _execute(language, program, table, row, CAP, timeout)
        wrong += result["matches"] is not True
        worst = max(worst, result["commands"] or 0)
    return wrong, worst


def main(argv: list[str] | None = None) -> int:
    """Print the per-family tallies; 1 on any wrong row or candidate crash."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("language")
    parser.add_argument("candidate", help="FILE.py:FUNC")
    parser.add_argument("--target", help="MODULE:ATTR to replace instead")
    parser.add_argument("--n", type=int, nargs=2, default=(3, 7), metavar=("LO", "HI"))
    parser.add_argument("--count", type=int, default=4, help="tables per family")
    parser.add_argument("--rows", type=int, default=64, help="rows per table")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds per row")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--generation-timeout", type=float, default=30)
    parser.add_argument("--budget-seconds", type=float, default=60)
    parser.add_argument("--max-tables", type=int, default=100)
    parser.add_argument("--max-work", type=int, default=10**11)
    parser.add_argument("--max-table-bits", type=int, default=65536)
    parser.add_argument("--step-cap", type=int, default=CAP)
    parser.add_argument("--failures", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument(
        "--allow-changed-candidate",
        action="store_true",
        help="replay a saved case against an updated candidate",
    )
    parser.add_argument("--allow-changed-checkout", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    if any(
        not math.isfinite(value) or value <= 0
        for value in (args.generation_timeout, args.budget_seconds)
    ):
        parser.error("generation and wall deadlines must be positive and finite")
    if min(args.max_tables, args.max_work, args.max_table_bits, args.step_cap) < 1:
        parser.error("work limits must be positive")
    if args.rows < 1 or args.count < 1:
        parser.error("--rows and --count must be positive")
    if not 1 <= args.n[0] <= args.n[1]:
        parser.error("--n requires 1 <= LO <= HI")

    try:
        replay = read_replay(args.replay, args.max_table_bits) if args.replay else None
    except (OSError, ValueError, OverflowError, RecursionError) as error:
        parser.error(str(error))
    if replay is not None:
        table, rows, bounds = replay["table"], replay["rows"], replay["bounds"]
        cost = {
            "tables": 1,
            "row_executions": 2 * len(rows),
            "step_bound": 2 * len(rows) * bounds["step_cap"],
            "largest_table_bits": len(table),
        }
    else:
        if args.n[1] > args.max_table_bits.bit_length() - 1:
            parser.error("arity exceeds --max-table-bits")
        cost = plan(args.n[0], args.n[1], args.count, args.rows, args.step_cap)
    print(
        json.dumps(
            {
                **cost,
                "wall_budget_seconds": args.budget_seconds,
                "generation_deadline_seconds": args.generation_timeout,
            },
            sort_keys=True,
        )
    )
    if cost["tables"] > args.max_tables or cost["step_bound"] > args.max_work:
        parser.error("screen exceeds --max-tables or --max-work")
    if args.dry_run:
        return 0
    language = resolve(args.language)
    try:
        identity = _candidate_identity(args.candidate)
    except (OSError, ValueError, SyntaxError) as error:
        parser.error(str(error))
    checkout = source_identity()
    if replay is not None and (
        replay.get("schema") != 1
        or (replay.get("candidate") != identity and not args.allow_changed_candidate)
        or replay.get("language") != language
        or replay.get("target") != args.target
    ):
        parser.error("replay candidate, language, or target changed")
    if (
        replay is not None
        and replay["checkout"] != checkout
        and not args.allow_changed_checkout
    ):
        parser.error("replay checkout changed; use --allow-changed-checkout")
    if (
        replay is not None
        and not args.allow_changed_candidate
        and dependencies_changed(replay.get("runtime_dependencies", {}))
    ):
        parser.error("replay runtime dependencies changed")
    rng = random.Random(args.seed)
    stats: dict[str, _Tally] = defaultdict(_Tally)
    failed = 0
    started = time.monotonic()
    deadline = started + args.budget_seconds
    records: list[dict[str, Any]] = []

    def finish(code: int, status: str) -> int:
        try:
            changed = (
                source_identity() != checkout
                or _candidate_identity(args.candidate) != identity
                or any(
                    dependencies_changed(record.get("runtime_dependencies", {}))
                    for record in records
                )
            )
        except (OSError, ValueError, SyntaxError):
            changed = True
        if changed:
            print("screen evidence invalid: source changed during execution")
            code, status = 1, "source-changed"
        if args.report is not None:
            write_text(
                args.report,
                json.dumps(
                    {
                        "schema": 1,
                        "status": status,
                        "exit_code": code,
                        "plan": cost,
                        "wall_budget_seconds": args.budget_seconds,
                        "elapsed_seconds": time.monotonic() - started,
                        "completed_cases": sum(
                            "result" in record for record in records
                        ),
                        "attempted_cases": len(records),
                        "cases": records,
                    },
                    sort_keys=True,
                    indent=1,
                )
                + "\n",
            )
        return code

    cases = [(replay["family"], replay["table"], replay["rows"])] if replay else None
    directory = args.failures
    index = 0
    for n in range(args.n[0], args.n[1] + 1) if cases is None else [0]:
        entries = cases or [
            (family, table, None) for family, table in _tables(n, rng, args.count)
        ]
        for family, table, saved_rows in entries:
            if saved_rows is None:
                rows = (
                    list(range(len(table)))
                    if len(table) <= args.rows
                    else sorted(rng.sample(range(len(table)), args.rows))
                )
            else:
                rows = saved_rows
            bounds = (
                replay["bounds"]
                if replay
                else {
                    "step_cap": args.step_cap,
                    "timeout": args.timeout,
                    "generation_timeout": args.generation_timeout,
                }
            )
            arguments = {
                "language": language,
                "table": table,
                "rows": rows,
                "sample_rows": rows * 2,
                "candidate": identity["spec"],
                "target": args.target,
                "timeout": bounds["timeout"],
                "step_cap": bounds["step_cap"],
            }
            record = {
                "schema": 1,
                "language": language,
                "candidate": identity,
                "target": args.target,
                "checkout": checkout,
                "seed": replay["seed"] if replay else args.seed,
                "family": family,
                "table": table,
                "rows": rows,
                "bounds": bounds,
            }
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print("screen wall budget exhausted")
                return finish(1, "budget-exhausted")
            if replay is not None:
                record["replay_of"] = str(args.replay.resolve())
            baseline_wrong = False
            try:
                result = _run_case(arguments, bounds["generation_timeout"], remaining)
                record["result"] = result
                record["runtime_dependencies"] = result.get("runtime_dependencies", {})
                new_rows = result["new_executions"]
                old_rows = result["old_executions"]
                wrong = sum(row["matches"] is not True for row in new_rows)
                baseline_wrong = any(row["matches"] is not True for row in old_rows)
                tally = stats[family]
                tally.tables += 1
                tally.changed += (
                    result["new_artifact_sha256"] != result["old_artifact_sha256"]
                )
                tally.ratios.append(result["new_size"] / result["old_size"])
                tally.larger += tally.ratios[-1] > 1
                tally.wrong += wrong
                tally.new_steps = max(
                    tally.new_steps, *(row["commands"] or 0 for row in new_rows)
                )
                tally.old_steps = max(
                    tally.old_steps, *(row["commands"] or 0 for row in old_rows)
                )
                bad = bool(wrong or baseline_wrong)
                failed += baseline_wrong
            except Exception as error:
                record["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                    "notes": getattr(error, "__notes__", []),
                }
                record["runtime_dependencies"] = getattr(
                    error, "candidate_dependencies", {}
                )
                print(f"{family}: {type(error).__name__}: {error}")
                failed += 1
                bad = True
            records.append(record)
            if bad:
                if directory is None:
                    parent = Path(__file__).resolve().parents[2] / "notes" / "screens"
                    parent.mkdir(parents=True, exist_ok=True)
                    directory = Path(tempfile.mkdtemp(prefix="candidate-", dir=parent))
                path = directory / f"failure-{index:04d}.json"
                write_text(path, json.dumps(record, sort_keys=True, indent=1) + "\n")
                print(f"replay: {path}")
            index += 1
            if baseline_wrong:
                return finish(1, "baseline-failed")

    print(f"{'family':<8} tables changed wrong larger  ratio min/mean  worst steps")
    for family, tally in stats.items():
        ratios = tally.ratios
        print(
            f"{family:<8} {tally.tables:>6} {tally.changed:>7} {tally.wrong:>5}"
            f" {tally.larger:>6}  {min(ratios):.3f}/{sum(ratios) / len(ratios):.3f}"
            f"     {tally.old_steps} -> {tally.new_steps}"
        )
    wrong = sum(tally.wrong for tally in stats.values())
    return finish(
        1 if wrong or failed else 0, "failed" if wrong or failed else "complete"
    )


if __name__ == "__main__":
    raise SystemExit(main())
