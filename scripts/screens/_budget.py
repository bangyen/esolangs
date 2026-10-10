"""Price screen workloads and supervise their complete CLI process trees."""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _verify_process import start_logged, wait_with_heartbeat


def options(parser: argparse.ArgumentParser) -> None:
    """Add explicit whole-screen limits and a generation-free cost preview."""
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget-seconds", type=float, default=60)
    parser.add_argument("--max-work", type=int, default=10**10)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)


def supervise(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    path: Path,
    plan: dict[str, int],
) -> bool:
    """Return true only inside the worker; otherwise print a plan or run it."""
    if (
        not math.isfinite(args.budget_seconds)
        or args.budget_seconds <= 0
        or args.max_work < 1
    ):
        parser.error("wall budget and work limit must be positive and finite")
    if plan["step_bound"] > args.max_work:
        parser.error("screen exceeds --max-work")
    if args.worker:
        return True
    print(
        json.dumps(
            {**plan, "wall_budget_seconds": args.budget_seconds}, sort_keys=True
        ),
        flush=True,
    )
    if args.dry_run:
        return False
    process = start_logged(
        [sys.executable, str(path), *sys.argv[1:], "--worker"],
        path.stem,
        dict(os.environ),
        path.resolve().parents[2],
        stream=True,
    )
    output, code = wait_with_heartbeat(
        process, path.stem, time.monotonic(), args.budget_seconds, 10
    )
    if code:
        print(output, file=sys.stderr)
        raise SystemExit(code)
    return False
