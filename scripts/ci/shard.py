"""CI helpers: shard a pytest band, merge timing runs, record durations."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Protocol

import pytest
from _lib.process import write_text
from _pytest.reports import TestReport

ROOT = Path(__file__).resolve().parents[2]


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


def shard_main(argv: list[str] | None = None) -> int:
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


def refresh_main(argv: list[str] | None = None) -> int:
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


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CI subcommand."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit("usage: ci.py {shard|refresh} ...")
    command, rest = argv[0], argv[1:]
    if command == "shard":
        return shard_main(rest)
    if command == "refresh":
        return refresh_main(rest)
    raise SystemExit(f"unknown subcommand {command!r}")


class _Worker(Protocol):
    config: pytest.Config
    workerinput: dict[str, object]


_COSTS = pytest.StashKey[dict[str, float]]()


class Recorder:
    """Collect controller reports without shared worker writes."""

    def __init__(self, path: Path) -> None:
        """Start an empty timing collection."""
        self.path = path
        self.durations: dict[str, float] = {}
        self.collected: set[str] = set()
        self.finished: set[str] = set()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Record the selected corpus in a serial session."""
        self.collected.update(item.nodeid for item in session.items)

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, ids: list[str]) -> None:
        """Workers must agree on collection before xdist can run."""
        self.collected.update(ids)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """Accumulate every phase; zero-duration reports need no estimate."""
        if report.when == "teardown":
            self.finished.add(report.nodeid)
        self.durations[report.nodeid] = (
            self.durations.get(report.nodeid, 0) + report.duration
        )

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        """Write the measured corpus even when tests fail."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(
                {
                    node: seconds
                    for node, seconds in sorted(self.durations.items())
                    if seconds > 0
                },
                indent=1,
            )
            + "\n"
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        snapshot = self.path.with_name(f"{self.path.name}.{digest}.json")
        write_text(snapshot, payload)
        write_text(self.path, payload)

        metadata = {
            "schema": 1,
            "run": {
                "id": os.environ.get("GITHUB_RUN_ID"),
                "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                "commit": os.environ.get("GITHUB_SHA"),
                "python": platform.python_version(),
                "platform": platform.system(),
                "machine": platform.machine(),
                "harness": 1,
            },
            "exitstatus": int(exitstatus),
            "collected": sorted(self.collected),
            "finished": sorted(self.finished),
            "durations_sha256": digest,
            "durations_file": snapshot.name,
        }
        # The sidecar is the commit point; readers use its immutable snapshot.
        write_text(
            self.path.with_suffix(self.path.suffix + ".meta.json"),
            json.dumps(metadata, sort_keys=True, indent=1) + "\n",
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the recording destination."""
    parser.addoption("--duration-output", type=Path)
    parser.addoption("--duration-order", action="store_true")


def pytest_configure(config: pytest.Config) -> None:
    """Only the controller owns the destination."""
    path = config.getoption("duration_output")
    if hasattr(config, "workerinput"):
        costs = config.workerinput.get("duration_costs", {})
    else:
        costs = {}
        if path is not None and config.getoption("duration_order"):
            try:
                recorded = json.loads(path.read_text(encoding="utf-8"))
                costs = {
                    node: float(seconds)
                    for node, seconds in recorded.items()
                    if isinstance(node, str)
                    and isinstance(seconds, (int, float))
                    and math.isfinite(seconds)
                    and seconds >= 0
                }
            except (OSError, ValueError, AttributeError, OverflowError):
                pass
    config.stash[_COSTS] = costs
    if path is not None and not hasattr(config, "workerinput"):
        config.pluginmanager.register(Recorder(path))


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node: _Worker) -> None:
    """Give workers one timing snapshot even if another run rewrites it."""
    node.workerinput["duration_costs"] = node.config.stash[_COSTS]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Schedule costly modules first while preserving their fixture locality."""
    if not config.getoption("duration_order"):
        return
    costs = config.stash[_COSTS]
    modules: dict[str, float] = defaultdict(float)
    for item in items:
        modules[item.nodeid.split("::", 1)[0]] += costs.get(item.nodeid, 0.001)
    items.sort(
        key=lambda item: (
            -modules[item.nodeid.split("::", 1)[0]],
            item.nodeid.split("::", 1)[0],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
