"""Price screen workloads and supervise their complete CLI process trees."""

import argparse
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _atomic import write_text
from _reference_identity import fingerprint
from _screen_evidence import checksum, resume, validate
from _verify_process import start_logged, wait_with_heartbeat
from benchmark import source_identity


def options(parser: argparse.ArgumentParser) -> None:
    """Add explicit whole-screen limits and a generation-free cost preview."""
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget-seconds", type=float, default=60)
    parser.add_argument("--max-work", type=int, default=10**10)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-cases", type=int, default=100000)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)


def supervise(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    path: Path,
    plan: dict[str, Any],
    argv: list[str] | None = None,
) -> bool:
    """Return true only inside the worker; otherwise print a plan or run it."""
    if (
        not math.isfinite(args.budget_seconds)
        or args.budget_seconds <= 0
        or args.max_work < 1
    ):
        parser.error("wall budget and work limit must be positive and finite")
    if plan.get("work_bound", plan.get("step_bound", 0)) > args.max_work:
        parser.error("screen exceeds --max-work")
    if plan.get("tables", 0) > getattr(args, "max_cases", 100000):
        parser.error("screen exceeds --max-cases")
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
    directory = root / "notes/screens"
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.stem + "-", suffix=".json", dir=directory)
    os.close(fd)
    report = getattr(args, "report", None) or Path(name)
    if report != Path(name):
        Path(name).unlink()
    progress = Path(name + ".progress")
    checkout = source_identity()
    settings = {
        key: value
        for key, value in vars(args).items()
        if key
        not in {
            "report",
            "resume",
            "worker",
            "dry_run",
            "budget_seconds",
            "max_work",
            "max_cases",
        }
    }
    settings = json.loads(json.dumps(settings, default=str, sort_keys=True))
    resume_file = Path(name + ".resume")
    try:
        records_to_reuse = (
            resume(
                args.resume,
                {"checkout": checkout, "settings": settings},
                plan,
                path.stem,
            )
            if getattr(args, "resume", None)
            else []
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    write_text(resume_file, json.dumps({"cases": records_to_reuse}))
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
        records = []
        try:
            if progress.exists():
                with progress.open("rb") as stream:
                    raw = stream.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("screen progress exceeds eight MiB")
                lines = raw.splitlines()
                if raw and not raw.endswith(b"\n") and status != "complete":
                    lines = lines[:-1]
                records = [json.loads(line) for line in lines]
                validate(records, expected)
            if status == "complete" and len(records) != plan.get(
                "tables", len(records)
            ):
                status, code = "incomplete", 1
        except (OSError, ValueError):
            records = []
            status, code = "invalid-evidence", 1
        try:
            if (
                "reference" in plan
                and fingerprint(plan["reference"]["template"]) != plan["reference"]
            ):
                status, code = "source-changed", 1
            if source_identity() != checkout:
                status, code = "source-changed", 1
        except (OSError, ValueError):
            status, code = "invalid-evidence", 1
        write_text(
            report,
            json.dumps(
                {
                    "schema": 2,
                    "settings": settings,
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
                    "status": status,
                    "exit_code": code,
                    "wall_budget_seconds": args.budget_seconds,
                    "elapsed_seconds": time.monotonic() - started,
                },
                sort_keys=True,
                indent=1,
            )
            + "\n",
        )
        progress.unlink(missing_ok=True)
        resume_file.unlink(missing_ok=True)
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
