"""Price screen workloads and supervise their complete CLI process trees."""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _screen_evidence import checksum
from _screen_phase import run as run_phase
from _verify_process import start_logged, wait_with_heartbeat


def options(parser: argparse.ArgumentParser) -> None:
    """Add explicit whole-screen limits and a generation-free cost preview."""
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget-seconds", type=float, default=60)
    parser.add_argument("--setup-seconds", type=float, default=5)
    parser.add_argument("--finalize-seconds", type=float, default=5)
    parser.add_argument("--max-work", type=int, default=10**10)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-cases", type=int, default=100000)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)


def setup(
    args: argparse.Namespace, operation: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Share one hard setup deadline across corpus, provenance and resume work."""
    limit = getattr(args, "setup_seconds", 5)
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("setup deadline must be positive and finite")
    if not hasattr(args, "_setup_deadline"):
        vars(args)["_setup_deadline"] = time.monotonic() + limit
    return run_phase(
        operation, payload, vars(args)["_setup_deadline"] - time.monotonic()
    )


def price(
    parser: argparse.ArgumentParser, args: argparse.Namespace, plan: dict[str, Any]
) -> None:
    """Reject an oversized workload before preparing its corpus."""
    if (
        any(
            not math.isfinite(value) or value <= 0
            for value in (
                args.budget_seconds,
                getattr(args, "setup_seconds", 5),
                getattr(args, "finalize_seconds", 5),
            )
        )
        or args.max_work < 1
        or getattr(args, "max_cases", 100000) < 1
    ):
        parser.error("wall budgets and work limits must be positive and finite")
    if plan.get("work_bound", plan.get("step_bound", 0)) > args.max_work:
        parser.error("screen exceeds --max-work")
    if plan.get("tables", 0) > getattr(args, "max_cases", 100000):
        parser.error("screen exceeds --max-cases")


def supervise(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    path: Path,
    plan: dict[str, Any],
    argv: list[str] | None = None,
) -> bool:
    """Return true only inside the worker; otherwise print a plan or run it."""
    price(parser, args, plan)
    expected = plan.get("case_ids", [])
    if "case_ids" in plan and len(expected) != plan.get("tables", len(expected)):
        parser.error("planned case count does not match corpus")
    if len(set(expected)) != len(expected):
        parser.error("duplicate planned case")
    if args.worker:
        return True
    print(
        json.dumps(
            {
                **{key: value for key, value in plan.items() if key != "case_ids"},
                "wall_budget_seconds": args.budget_seconds,
                "setup_budget_seconds": getattr(args, "setup_seconds", 5),
                "finalize_budget_seconds": getattr(args, "finalize_seconds", 5),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if args.dry_run:
        return False
    root = (
        path.resolve().parents[2]
        if path.parent.name == "screens"
        else path.resolve().parents[1]
    )
    try:
        allocated = setup(
            args,
            "allocate",
            {
                "root": str(root),
                "screen": path.stem,
                "report": str(args.report) if getattr(args, "report", None) else None,
            },
        )
    except (OSError, ValueError, TimeoutError) as exc:
        parser.error(str(exc))
    name, report = allocated["name"], Path(allocated["report"])
    progress = Path(name + ".progress")
    try:
        identity = setup(args, "metadata", {})
        if "reference_template" in plan:
            plan = {
                **plan,
                "reference": setup(
                    args, "reference", {"template": plan["reference_template"]}
                ),
            }
    except (OSError, ValueError, TimeoutError) as exc:
        parser.error(str(exc))
    checkout, runtime = identity["checkout"], identity["runtime"]
    settings = {
        key: value
        for key, value in vars(args).items()
        if not key.startswith("_")
        and key
        not in {
            "report",
            "resume",
            "worker",
            "dry_run",
            "budget_seconds",
            "setup_seconds",
            "finalize_seconds",
            "max_work",
            "max_cases",
        }
    }
    settings = json.loads(json.dumps(settings, default=str, sort_keys=True))
    resume_file = Path(name + ".resume")
    try:
        records_to_reuse = (
            setup(
                args,
                "resume",
                {
                    "path": str(args.resume),
                    "identity": {
                        "checkout": checkout,
                        "settings": settings,
                        "runtime": runtime,
                    },
                    "plan": plan,
                    "screen": path.stem,
                },
            )["cases"]
            if getattr(args, "resume", None)
            else []
        )
        setup(
            args,
            "write",
            {
                "path": str(resume_file),
                "value": {
                    "cases": records_to_reuse,
                    "identity": {
                        **identity,
                        "reference": plan.get("reference"),
                        "settings": settings,
                    },
                },
            },
        )
    except (OSError, ValueError, TimeoutError) as exc:
        parser.error(str(exc))
    findings = Path(name + ".findings")
    started = time.monotonic()
    code = 1
    status = "failed"
    output = ""
    try:
        process = start_logged(
            [
                sys.executable,
                str(path),
                *(sys.argv[1:] if argv is None else argv),
                "--worker",
            ],
            path.stem,
            {
                **os.environ,
                "ESOLANGS_SCREEN_PROGRESS": str(progress),
                "ESOLANGS_SCREEN_RESUME": str(resume_file),
                "ESOLANGS_SCREEN_FINDINGS": str(findings),
            },
            root,
            stream=True,
        )
        output, code = wait_with_heartbeat(
            process, path.stem, started, args.budget_seconds, 10
        )
        status = "complete" if code == 0 else "timeout" if code == 124 else "failed"
    except BaseException:
        status = "interrupted"
        raise
    finally:
        finish_deadline = time.monotonic() + getattr(args, "finalize_seconds", 5)

        def finish(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
            return run_phase(operation, payload, finish_deadline - time.monotonic())

        records, saved_findings = [], []
        try:
            collected = finish(
                "collect",
                {
                    "progress": str(progress),
                    "expected": expected,
                    "status": status,
                    "findings": str(findings),
                },
            )
            records, saved_findings = collected["cases"], collected["findings"]
            if status == "complete" and len(records) != plan.get(
                "tables", len(records)
            ):
                status, code = "incomplete", 1
        except (OSError, ValueError):
            status, code = "invalid-evidence", 1
        try:
            if (
                "reference" in plan
                and finish("reference", {"template": plan["reference"]["template"]})
                != plan["reference"]
            ):
                status, code = "source-changed", 1
            if finish("metadata", {}) != identity:
                status, code = "source-changed", 1
        except (OSError, ValueError):
            status, code = "invalid-evidence", 1
        finish(
            "write",
            {
                "path": str(report),
                "cleanup": [str(progress), str(resume_file)]
                if status != "invalid-evidence"
                else [],
                "value": {
                    "schema": 3,
                    "settings": settings,
                    "runtime": runtime,
                    "screen": path.stem,
                    "checkout": checkout,
                    "plan": plan,
                    "completed_cases": sum(
                        record.get("case_count", 1)
                        for record in records
                        if record.get("status") != "skipped"
                    ),
                    "skipped_cases": sum(
                        record.get("case_count", 1)
                        for record in records
                        if record.get("status") == "skipped"
                    ),
                    "row_executions": sum(
                        record.get("rows", 0)
                        for record in records
                        if not record.get("reused")
                    ),
                    "cases": records,
                    "findings": saved_findings,
                    "status": status,
                    "exit_code": code,
                    "wall_budget_seconds": args.budget_seconds,
                    "setup_budget_seconds": getattr(args, "setup_seconds", 5),
                    "finalize_budget_seconds": getattr(args, "finalize_seconds", 5),
                    "elapsed_seconds": time.monotonic() - started,
                },
            },
        )
        print(f"screen manifest: {report}", flush=True)
    if code:
        print(output, file=sys.stderr)
        raise SystemExit(code)
    return False


_ORDINAL = 0


def completed(status: str, *, rows: int = 0, **fields: Any) -> None:
    """Append one completed case to the supervising process's bounded ledger."""
    global _ORDINAL
    name = os.environ.get("ESOLANGS_SCREEN_PROGRESS")
    if name is None:
        return
    record = {"ordinal": _ORDINAL, "status": status, "rows": rows, **fields}
    record["evidence_sha256"] = checksum(record)
    line = json.dumps(record, sort_keys=True) + "\n"
    path = Path(name)
    if (path.stat().st_size if path.exists() else 0) + len(
        line.encode("utf-8")
    ) > 8 * 1024 * 1024:
        raise RuntimeError("screen progress exceeds eight MiB")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    _ORDINAL += 1
