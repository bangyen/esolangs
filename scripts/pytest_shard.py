"""Run one shard of a pytest marker band.

Partitions the band's collected node IDs round-robin (``ids[index::total]``)
and runs pytest on just that slice, so N CI jobs cover the band with no
overlap and no omission.  Round-robin rather than contiguous because one
file holds nearly half the slow band; contiguous slices would leave one
shard carrying it whole.  Sorting the IDs keeps the assignment stable
across runs; an empty slice exits clean, for more shards than tests.

Usage:
    python scripts/pytest_shard.py --marker slow --shard 0 --shards 4 -- -n auto
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def shard_ids(ids: list[str], index: int, total: int) -> list[str]:
    """Return every ``total``-th ID starting at ``index``."""
    return ids[index::total]


def _parse_args(argv: list[str] | None) -> tuple[argparse.Namespace, list[str]]:
    """Split the shard selection from the pytest arguments after ``--``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", required=True, help="pytest marker band to run")
    parser.add_argument("--shard", type=int, required=True, help="this job's slice")
    parser.add_argument("--shards", type=int, required=True, help="slice count")
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
    ids = shard_ids(collect_ids(args.marker), args.shard, args.shards)
    if not ids:
        print(f"shard {args.shard}/{args.shards} of -m {args.marker}: no tests")
        return 0
    print(f"shard {args.shard}/{args.shards} of -m {args.marker}: {len(ids)} tests")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *rest, *ids], cwd=ROOT, check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
