"""Run one shard of a pytest marker band.

Without timings, partitions node IDs round-robin (``ids[index::total]``).
With timings, balances estimated duration, longest tests first.
Runs pytest on just that slice, so N CI jobs cover the band with no
overlap and no omission.  Round-robin rather than contiguous because one
file holds nearly half the slow band; contiguous slices would leave one
shard carrying it whole.  Sorting the IDs keeps the assignment stable
across runs; an empty slice exits clean, for more shards than tests.

Usage:
    python scripts/pytest_shard.py --marker slow --shard 0 --shards 4 -- -n auto
"""

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text  # noqa: E402


def collect_ids(marker: str) -> list[str]:
    """Return the sorted node IDs pytest collects for ``-m marker``.

    ``-o addopts=`` neutralizes the repo's own ``--verbose``, which would
    otherwise switch collection output from one-node-per-line to a tree.
    Exit 5 (nothing collected) is an empty band, not a failure.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "-m",
            marker,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 5:
        return []
    if proc.returncode != 0:
        raise RuntimeError(f"collection for -m {marker} failed:\n{proc.stderr}")
    return sorted({line.strip() for line in proc.stdout.splitlines() if "::" in line})


def load_durations(path: Path) -> dict[str, float]:
    """Return finite positive timings, refusing a corrupt timing file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(
        not isinstance(key, str)
        or isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
        for key, value in raw.items()
    ):
        raise ValueError("durations must map node IDs to finite positive seconds")
    return {key: float(value) for key, value in raw.items()}


def shard_ids(
    ids: list[str],
    index: int,
    total: int,
    durations: dict[str, float] | None = None,
) -> list[str]:
    """Partition once; place longest tests on the least loaded shard."""
    if total < 1 or not 0 <= index < total:
        raise ValueError("invalid shard index or count")
    ids = sorted(set(ids))
    if not durations:
        return ids[index::total]
    known = [durations[node] for node in ids if node in durations]
    fallback = statistics.median(known) if known else 1.0
    weights = {node: durations.get(node, fallback) for node in ids}
    parts: list[list[str]] = [[] for _ in range(total)]
    loads = [0.0] * total
    for node in sorted(ids, key=lambda node: (-weights[node], node)):
        target = min(
            range(total), key=lambda part: (loads[part], len(parts[part]), part)
        )
        parts[target].append(node)
        loads[target] += weights[node]
    return sorted(parts[index])


def _parse_args(argv: list[str] | None) -> tuple[argparse.Namespace, list[str]]:
    """Split the shard selection from the pytest arguments after ``--``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", required=True, help="pytest marker band to run")
    parser.add_argument("--shard", type=int, required=True, help="this job's slice")
    parser.add_argument("--shards", type=int, required=True, help="slice count")
    parser.add_argument("--durations", type=Path, help="recorded seconds by node ID")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--exclude-node", action="append", default=[])
    args, rest = parser.parse_known_args(argv)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    if not 0 <= args.shard < args.shards:
        parser.error("--shard must lie in [0, --shards)")
    return args, rest


def main(argv: list[str] | None = None) -> int:
    """Collect the band, run this shard's slice, return pytest's exit code."""
    args, rest = _parse_args(argv)
    durations = load_durations(args.durations) if args.durations else None
    collected = collect_ids(args.marker)
    excluded = set(args.exclude_node)
    if not excluded <= set(collected):
        raise ValueError("excluded nodes must belong to the collected corpus")
    ids = shard_ids(
        [node for node in collected if node not in excluded],
        args.shard,
        args.shards,
        durations,
    )
    if args.manifest is not None:
        write_text(
            args.manifest,
            json.dumps(
                {
                    "schema": 1,
                    "shard": args.shard,
                    "shards": args.shards,
                    "marker": args.marker,
                    "collected": collected,
                    "selected": ids,
                    "excluded": sorted(excluded),
                    "run": {
                        "id": os.environ.get("GITHUB_RUN_ID"),
                        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                        "commit": os.environ.get("GITHUB_SHA"),
                    },
                },
                sort_keys=True,
            )
            + "\n",
        )
    if durations:
        known = [durations[node] for node in collected if node in durations]
        fallback = statistics.median(known) if known else 1.0
        estimate = sum(durations.get(node, fallback) for node in ids)
        missing = sum(node not in durations for node in ids)
        print(
            f"estimated serial duration: {estimate:.1f}s "
            f"({missing} tests use median fallback {fallback:.3f}s)",
            flush=True,
        )
    if not ids:
        print(f"shard {args.shard}/{args.shards} of -m {args.marker}: no tests")
        return 0
    print(f"shard {args.shard}/{args.shards} of -m {args.marker}: {len(ids)} tests")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *rest, *ids], cwd=ROOT, check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
