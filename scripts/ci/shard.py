"""CI helpers: shard a pytest band, merge timing runs, record durations."""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ holds the sibling `verify`, `docs`, and `ci` packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import tempfile
from contextlib import suppress
from datetime import date
from typing import Any, NamedTuple

import pytest
from _pytest.reports import TestReport
from verify import coverage as coverage_evidence
from verify.process import write_text
from verify.pytest_evidence import OUTPUT_OPTION, PLUGIN

ROOT = Path(__file__).resolve().parents[2]


def _pytest_env() -> dict[str, str]:
    """Use the declared selectors even when a caller has local pytest options."""
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    return env


def collect_ids(marker: str) -> list[str]:
    """Return the sorted node IDs pytest collects for ``-m marker``.

    ``-o addopts=`` neutralizes the repo's own ``--verbose``, which would
    otherwise switch collection output from one-node-per-line to a tree.
    IDs come from the collection hook, so diagnostics cannot become tests.
    Exit 5 (nothing collected) is an empty band, not a failure.
    """
    with tempfile.TemporaryDirectory(prefix="pytest-collection-") as directory:
        destination = Path(directory) / "ids.json"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-o",
                "addopts=",
                "-p",
                "scripts.ci.shard",
                "--collection-output",
                str(destination),
                "-m",
                marker,
            ],
            cwd=ROOT,
            env=_pytest_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 5:
            return []
        if proc.returncode != 0:
            raise RuntimeError(
                f"collection for -m {marker} failed:\n{proc.stdout}\n{proc.stderr}"
            )
        return sorted(set(json.loads(destination.read_text(encoding="utf-8"))))


def _timing_map(raw: object) -> object:
    """Return the node-to-seconds map inside a timing payload.

    A raw timing file is the map itself; the committed ``snapshot.json``
    nests it under ``durations``, beside the ``collected`` dates.
    """
    if isinstance(raw, dict) and isinstance(raw.get("durations"), dict):
        return raw["durations"]
    return raw


def load_durations(path: Path) -> dict[str, float]:
    """Return finite positive timings, refusing a corrupt timing file."""
    return _parse_durations(path.read_bytes(), path)


def _parse_durations(data: bytes, path: Path) -> dict[str, float]:
    """Parse the bytes read from a timing file or checked against a sidecar."""
    try:
        raw = _timing_map(json.loads(data.decode("utf-8")))
    except ValueError as error:
        raise ValueError(f"{path}: invalid timing JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: durations must map node IDs to finite positive seconds"
        )
    durations: dict[str, float] = {}
    for node, value in raw.items():
        seconds = math.nan
        if isinstance(value, int | float) and not isinstance(value, bool):
            with suppress(OverflowError):
                seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(
                f"{path}: duration for {node!r} must be finite positive seconds"
            )
        durations[node] = seconds
    return durations


_GRID_RATIO = math.sqrt(2)


def quantize_duration(value: float) -> float:
    """Round ``value`` up to the sqrt(2) grid the committed snapshot stores.

    Shard balancing needs magnitudes, not 16 significant figures, and a
    median that wobbles by a few percent under load used to rewrite its
    entry on every refresh — churn, not signal.  On the grid (32 points
    span this corpus) an entry changes only when the median itself moves
    by 41% or more.  The epsilon keeps a median landing exactly on a grid
    point (2.0s) from being bumped a step by float dust in the log.
    """
    if value <= 0:
        return value
    return _GRID_RATIO ** math.ceil(math.log(value, _GRID_RATIO) - 1e-9)


def _fallback(durations: dict[str, float], nodes: list[str]) -> float:
    """Return the median known duration among ``nodes``, else one second."""
    known = [durations[node] for node in nodes if node in durations]
    return _median_duration(known) if known else 1.0


def _median_duration(samples: list[float]) -> float:
    """Average the center pair without overflowing for large positive timings."""
    median = statistics.median(samples)
    if math.isfinite(median):
        return median
    lower = statistics.median_low(samples)
    upper = statistics.median_high(samples)
    return lower + (upper - lower) / 2


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
    fallback = _fallback(durations, ids)
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
    parser.add_argument("--bind-coverage", type=Path, help=argparse.SUPPRESS)
    args, rest = parser.parse_known_args(argv)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    if not 0 <= args.shard < args.shards:
        parser.error("--shard must lie in [0, --shards)")
    if args.bind_coverage and (
        args.marker or args.exclude_node or "--cov-branch" not in rest
    ):
        parser.error("--bind-coverage requires the full corpus and branch coverage")
    return args, rest


def shard_main(argv: list[str] | None = None) -> int:
    """Collect the band, run this shard's slice, return pytest's exit code."""
    args, rest = _parse_args(argv)
    try:
        durations = load_durations(args.durations) if args.durations else None
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    data = args.bind_coverage.resolve() if args.bind_coverage is not None else None
    state = coverage_evidence.checkout(ROOT, data) if data is not None else ""
    collected = collect_ids(args.marker)
    excluded = set(args.exclude_node)
    if not excluded <= set(collected):
        raise ValueError("excluded nodes must belong to the collected corpus")
    eligible = [node for node in collected if node not in excluded]
    ids = shard_ids(eligible, args.shard, args.shards, durations)
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
        fallback = _fallback(durations, eligible)
        estimate = sum(durations.get(node, fallback) for node in ids)
        missing = sum(node not in durations for node in ids)
        print(
            f"estimated serial duration: {estimate:.1f}s "
            f"({missing} tests use median fallback {fallback:.3f}s)",
            flush=True,
        )
    if not ids:
        print(f"shard {args.shard}/{args.shards} of -m {args.marker}: no tests")
        return int(data is not None)
    print(f"shard {args.shard}/{args.shards} of -m {args.marker}: {len(ids)} tests")
    if data is not None:
        return _run_coverage_shard(
            data,
            state,
            rest,
            {
                "shard": args.shard,
                "shards": args.shards,
                "collected": coverage_evidence.fingerprint(collected),
                "nodes": ids,
            },
        )
    return subprocess.run(
        [sys.executable, "-m", "pytest", *rest, *ids],
        cwd=ROOT,
        env=_pytest_env(),
        check=False,
    ).returncode


def _run_coverage_shard(
    data: Path, state: str, pytest_args: list[str], selection: dict[str, Any]
) -> int:
    """Publish coverage with the completed shard selection."""
    with tempfile.TemporaryDirectory(prefix=".coverage.", dir=data.parent) as stage:
        staged = Path(stage) / ".coverage"
        execution = Path(stage) / "pytest.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *pytest_args,
                "-p",
                PLUGIN,
                OUTPUT_OPTION,
                str(execution),
                *selection["nodes"],
            ],
            cwd=ROOT,
            env={**_pytest_env(), "COVERAGE_FILE": str(staged)},
            check=False,
        )
        if result.returncode:
            return result.returncode
        if coverage_evidence.completed(execution) != selection["nodes"]:
            raise ValueError("coverage shard ran a different selection")
        if coverage_evidence.checkout(ROOT, data) != state:
            raise ValueError("checkout inputs changed during coverage collection")
        coverage_evidence.publish(staged, data, state, selection)
    return 0


class _TimingRun(NamedTuple):
    """Timings from one run and the file that supplied each sample."""

    durations: dict[str, float]
    identity: dict[str, object]
    sources: dict[str, Path]


def load_run(directory: Path, expected: set[str]) -> dict[str, float]:
    """Return timings for a complete, validated run."""
    return _load_run(directory, expected).durations


def _load_run(directory: Path, expected: set[str]) -> _TimingRun:
    """Validate sidecars and retain the identity shared by every shard."""
    paths = sorted(directory.rglob("*.json.meta.json"))
    if not paths:
        raise ValueError(f"{directory}: no timing completion metadata")
    result: dict[str, float] = {}
    sources: dict[str, Path] = {}
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
        ):
            raise ValueError(f"{path}: failed, incomplete, or altered timing run")
        data = durations_path.read_bytes()
        if metadata.get("durations_sha256") != hashlib.sha256(data).hexdigest():
            raise ValueError(f"{path}: altered timing run")
        if not isinstance(metadata.get("run"), dict):
            raise ValueError(f"{path}: missing run identity")
        if identity is not None and identity != metadata["run"]:
            raise ValueError(f"{directory}: mixed CI runs or Python versions")
        identity = metadata["run"]
        durations = _parse_durations(data, durations_path)
        if set(durations) != set(metadata["collected"]):
            raise ValueError(f"{path}: incomplete timing corpus")
        for node in expected & durations.keys():
            if node in result:
                raise ValueError(f"{directory}: duplicate test {node}")
            result[node] = durations[node]
            sources[node] = durations_path
    if result.keys() != expected:
        raise ValueError(f"{directory}: missing {len(expected - result.keys())} tests")
    assert identity is not None
    return _TimingRun(result, identity, sources)


def _rounded_duration(node: str, runs: list[_TimingRun]) -> float:
    """Round a median, naming its input files if the grid cannot represent it."""
    median = _median_duration([run.durations[node] for run in runs])
    try:
        rounded = quantize_duration(median)
    except OverflowError:
        rounded = math.inf
    if not math.isfinite(rounded) or rounded <= 0:
        sources = ", ".join(str(run.sources[node]) for run in runs)
        raise ValueError(
            f"{sources}: duration for {node!r} "
            "cannot be rounded to finite positive seconds"
        )
    return rounded


def _collected_dates(output: Path) -> dict[str, str]:
    """Return the dates the snapshot at ``output`` already records.

    A refresh rewrites the durations and stamps their date; the census
    dates beside them are another producer's record and carry over.
    """
    try:
        raw = json.loads(output.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise ValueError(f"{output}: cannot read timing snapshot: {error}") from error
    if (
        not isinstance(raw, dict)
        or not isinstance(collected := raw.get("collected"), dict)
        or not all(isinstance(value, str) for value in collected.values())
    ):
        raise ValueError(f"{output}: collected dates must map names to strings")
    return collected


def refresh(runs: list[Path], ids: list[str], output: Path) -> None:
    """Write median timings only after every input run passes validation."""
    if not runs or not ids:
        raise ValueError("runs and selected tests required")
    directories = [run.resolve() for run in runs]
    if len(set(directories)) != len(directories):
        raise ValueError("duplicate timing run directory")
    expected = set(ids)
    loaded = [_load_run(run, expected) for run in directories]
    seen: set[tuple[str, str | None]] = set()
    for directory, run in zip(directories, loaded, strict=True):
        identity = run.identity
        run_id, attempt = identity.get("id"), identity.get("attempt")
        if run_id is None:
            continue
        if not isinstance(run_id, str) or (
            attempt is not None and not isinstance(attempt, str)
        ):
            raise ValueError(f"{directory}: invalid timing run identity")
        key = (run_id, attempt)
        if key in seen:
            raise ValueError(
                f"{directory}: duplicate timing run ID {run_id}, attempt {attempt}"
            )
        seen.add(key)
    cohorts = {
        tuple(
            run.identity.get(key)
            for key in ("python", "platform", "machine", "harness")
        )
        for run in loaded
    }
    if len(cohorts) != 1:
        raise ValueError("mixed timing environments or harness versions")
    durations = {node: _rounded_duration(node, loaded) for node in sorted(expected)}
    collected = _collected_dates(output)
    collected["durations"] = date.today().isoformat()
    snapshot = {"collected": collected, "durations": durations}
    write_text(output, json.dumps(snapshot, indent=1) + "\n")


def refresh_main(argv: list[str] | None = None) -> int:
    """Each directory contains all timing artifacts from one successful run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("snapshot.json"),
    )
    parser.add_argument("--marker", default="slow and not weekly")
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--serial-node", action="append", default=[])
    args = parser.parse_args(argv)
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    ids = collect_ids(args.marker)
    try:
        if set(args.serial_node) - set(ids):
            raise ValueError("serial nodes must belong to the selected corpus")
        refresh(args.runs, ids, args.output)
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
    usage = "usage: scripts/ci/shard.py {shard|refresh} ..."
    if argv[:1] in (["-h"], ["--help"]):
        print(f"{usage}\n\n{__doc__}")
        return 0
    if not argv:
        raise SystemExit(usage)
    command, rest = argv[0], argv[1:]
    if command == "shard":
        return shard_main(rest)
    if command == "refresh":
        return refresh_main(rest)
    raise SystemExit(f"unknown subcommand {command!r}")


class Recorder:
    """Collect controller reports without shared worker writes."""

    def __init__(self, path: Path) -> None:
        """Start an empty timing collection."""
        self.path = path
        self.durations: dict[str, float] = {}
        self.collected: set[str] = set()
        self.finished: set[str] = set()
        self.failed: set[str] = set()
        self.progress = path.with_suffix(path.suffix + ".progress.jsonl")
        write_text(self.progress, "")

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
        if report.failed:
            self.failed.add(report.nodeid)
        if report.when == "teardown" or report.failed:
            record = {
                "nodeid": report.nodeid,
                "duration": self.durations[report.nodeid],
                "finished": report.when == "teardown",
                "failed": report.nodeid in self.failed,
            }
            if report.failed:
                record["failure"] = str(report.longrepr)
            # A flushed diagnostic journal survives SIGKILL; only sessionfinish
            # publishes the immutable snapshot and completion metadata.
            with self.progress.open("a", encoding="utf-8") as progress:
                progress.write(json.dumps(record) + "\n")

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
    parser.addoption("--collection-output", type=Path)
    parser.addoption("--duration-output", type=Path)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Write selected node IDs independently of terminal diagnostics."""
    destination = session.config.getoption("collection_output")
    if destination is not None:
        write_text(destination, json.dumps([item.nodeid for item in session.items]))


def pytest_configure(config: pytest.Config) -> None:
    """Only the controller owns the destination."""
    path = config.getoption("duration_output")
    if path is not None and not hasattr(config, "workerinput"):
        config.pluginmanager.register(Recorder(path))


if __name__ == "__main__":
    raise SystemExit(main())
