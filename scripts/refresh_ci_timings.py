"""Merge complete successful timing runs and report predicted shard loads."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scope import write_text
from pytest_shard import collect_ids, load_durations, shard_ids


def load_run(directory: Path, expected: set[str]) -> dict[str, float]:
    """Validate sidecars and require every selected test exactly once per run."""
    paths = sorted(directory.rglob("*.json.meta.json"))
    if not paths:
        raise ValueError(f"{directory}: no timing completion metadata")
    result: dict[str, float] = {}
    identity = None
    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        durations_path = path.with_suffix("").with_suffix("")
        if isinstance(metadata, dict) and "durations_file" in metadata:
            name = metadata["durations_file"]
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError(f"{path}: invalid timing snapshot path")
            durations_path = path.parent / name
        if (
            not isinstance(metadata, dict)
            or metadata.get("schema") != 1
            or metadata.get("exitstatus") != 0
            or not isinstance(metadata.get("collected"), list)
            or not all(isinstance(node, str) for node in metadata["collected"])
            or metadata.get("finished") != metadata["collected"]
            or len(set(metadata["collected"])) != len(metadata["collected"])
            or metadata.get("durations_sha256")
            != hashlib.sha256(durations_path.read_bytes()).hexdigest()
        ):
            raise ValueError(f"{path}: failed, incomplete, or altered timing run")
        if not isinstance(metadata.get("run"), dict):
            raise ValueError(f"{path}: missing run identity")
        if identity is not None and identity != metadata["run"]:
            raise ValueError(f"{directory}: mixed CI runs or Python versions")
        identity = metadata["run"]
        durations = load_durations(durations_path)
        if set(durations) != set(metadata["collected"]):
            raise ValueError(f"{path}: incomplete timing corpus")
        for node in expected & durations.keys():
            if node in result:
                raise ValueError(f"{directory}: duplicate test {node}")
            result[node] = durations[node]
    if result.keys() != expected:
        raise ValueError(f"{directory}: missing {len(expected - result.keys())} tests")
    return result


def refresh(runs: list[Path], ids: list[str], output: Path, shards: int) -> list[float]:
    """Write median timings only after every input run passes validation."""
    if not runs or not ids or shards < 1:
        raise ValueError("runs, selected tests, and a positive shard count required")
    samples = [load_run(run, set(ids)) for run in runs]
    cohorts = {
        tuple(
            json.loads(next(run.rglob("*.json.meta.json")).read_text())["run"].get(key)
            for key in ("python", "platform", "machine", "harness")
        )
        for run in runs
    }
    if len(cohorts) != 1:
        raise ValueError("mixed timing environments or harness versions")
    durations = {
        node: statistics.median(sample[node] for sample in samples)
        for node in sorted(set(ids))
    }
    loads = [
        sum(durations[node] for node in shard_ids(ids, index, shards, durations))
        for index in range(shards)
    ]
    write_text(output, json.dumps(durations, indent=1) + "\n")
    return loads


def main(argv: list[str] | None = None) -> int:
    """Each directory contains all timing artifacts from one successful run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument(
        "--output", type=Path, default=Path("tests/fixtures/slow_durations.json")
    )
    parser.add_argument("--marker", default="slow and not weekly")
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--serial-node", action="append", default=[])
    args = parser.parse_args(argv)
    ids = collect_ids(args.marker)
    try:
        if set(args.serial_node) - set(ids):
            raise ValueError("serial nodes must belong to the selected corpus")
        refresh(args.runs, ids, args.output, args.shards)
        durations = load_durations(args.output)
        parallel = [node for node in ids if node not in args.serial_node]
        for index in range(args.shards):
            load = sum(
                durations[node]
                for node in shard_ids(parallel, index, args.shards, durations)
            )
            print(f"shard {index}: {load:.1f}s estimated serial test duration")
        for node in args.serial_node:
            if node in durations:
                print(f"serial {node}: {durations[node]:.1f}s")
        print(f"updated {args.output}: {len(ids)} tests, {len(args.runs)} runs")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
