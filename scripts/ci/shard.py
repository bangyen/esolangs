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
import re
import statistics
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import date
from typing import Any, NamedTuple

import pytest
from _pytest.reports import TestReport
from verify import coverage as coverage_evidence
from verify.process import logged_path, start_logged, wait_with_heartbeat, write_text
from verify.pytest_evidence import OUTPUT_OPTION, PLUGIN

from esolangs.runtime._json import unique_object

ROOT = Path(__file__).resolve().parents[2]
_COLLECTION_TIMEOUT = 60.0
_DURATION_OUTPUT = "--duration-output"
_DURATION_PROTECTED = "_ESOLANGS_SHARD_DURATION_PROTECTED"
_COMPLETION_SUFFIX = ".meta.json"


class CollectionError(RuntimeError):
    """A failed pytest collection with a short diagnostic and persistent log."""


def _pytest_env() -> dict[str, str]:
    """Use the declared selectors even when a caller has local pytest options."""
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env.pop(_DURATION_PROTECTED, None)
    return env


def _collection_error(
    marker: str, reason: str, log: Path, output: str
) -> CollectionError:
    """Expose pytest's errors from the bounded tail of the saved log."""
    detail = "\n".join(
        line
        for line in output.splitlines()
        if line.startswith(("E ", "ERROR ", "ERROR:", "[log error]"))
    )
    header = f"collection for -m {marker!r} {reason}"
    diagnostic = f"\n{detail[:2048]}" if detail else ""
    return CollectionError(f"{header}{diagnostic}\n[log] {log}")


def collect_ids(marker: str, *, paths: Sequence[str] = ()) -> list[str]:
    """Return the sorted node IDs pytest collects for ``-m marker``.

    ``-o addopts=`` neutralizes the repo's own ``--verbose``, which would
    otherwise switch collection output from one-node-per-line to a tree.
    IDs come from the collection hook, so diagnostics cannot become tests.
    Exit 5 (nothing collected) is an empty band, not a failure.
    """
    with tempfile.TemporaryDirectory(prefix="pytest-collection-") as directory:
        destination = Path(directory) / "ids.json"
        command = [
            sys.executable,
            "-u",
            "-m",
            "pytest",
            "--collect-only",
            "-s",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "scripts.ci.shard",
            "--collection-output",
            str(destination),
            "-m",
            marker,
            *paths,
        ]
        name = "pytest-collection"
        started = time.monotonic()
        with start_logged(
            command, name, _pytest_env(), ROOT, stream=False, cwd=ROOT
        ) as proc:
            log = logged_path(proc)
            output, status = wait_with_heartbeat(
                proc, name, started, _COLLECTION_TIMEOUT, _COLLECTION_TIMEOUT
            )
        if status == 5:
            log.unlink()
            return []
        if status != 0:
            reason = {
                124: f"timed out after {_COLLECTION_TIMEOUT:g}s",
                125: "failed (diagnostic byte limit exceeded or log error)",
            }.get(status, f"failed (pytest exit {status})")
            raise _collection_error(marker, reason, log, output)
        try:
            nodes = read_evidence_json(destination, kind="pytest collection")
            if (
                not isinstance(nodes, list)
                or not all(isinstance(node, str) and node.strip() for node in nodes)
                or len(set(nodes)) != len(nodes)
            ):
                raise ValueError("expected a list of unique, nonempty test node IDs")
        except (ValueError, RecursionError) as error:
            raise _collection_error(
                marker,
                f"produced an invalid collection report: {error}",
                log,
                output,
            ) from error
        log.unlink()
        return sorted(nodes)


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


def read_evidence_json(path: Path, *, kind: str, data: bytes | None = None) -> Any:
    """Read unique evidence fields, reusing already hashed bytes when supplied."""
    try:
        payload = path.read_bytes() if data is None else data
        return json.loads(payload.decode("utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: invalid {kind} JSON: {error}") from error


def read_completion_metadata(path: Path) -> dict[str, Any]:
    """Read the identity and unique node IDs before consumers compare them."""
    metadata = read_evidence_json(path, kind="timing")
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: timing completion metadata must be an object")
    for key in ("schema", "exitstatus"):
        if type(metadata.get(key)) is not int:
            raise ValueError(
                f"{path}: invalid completion field {key!r}: expected an integer"
            )
    run = metadata.get("run")
    if not isinstance(run, dict):
        raise ValueError(f"{path}: invalid completion field 'run': expected an object")
    for key in ("id", "attempt", "commit", "python", "platform", "machine"):
        value = run.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"{path}: invalid completion field 'run.{key}': "
                "expected a string or null"
            )
    harness = run.get("harness")
    if harness is not None and type(harness) is not int:
        raise ValueError(
            f"{path}: invalid completion field 'run.harness': "
            "expected an integer or null"
        )
    nodes = metadata.get("collected")
    if (
        not isinstance(nodes, list)
        or not all(isinstance(node, str) for node in nodes)
        or len(set(nodes)) != len(nodes)
    ):
        raise ValueError(
            f"{path}: invalid completion field 'collected': expected unique test IDs"
        )
    return metadata


def read_completion_sidecars(directory: Path) -> dict[Path, dict[str, Any]]:
    """Read the recorder's completion sidecars regardless of the timing suffix."""
    candidates = set(directory.rglob(f"*{_COMPLETION_SUFFIX}"))
    # A timing filename can itself end with the completion suffix.
    return {
        path: read_completion_metadata(path)
        for path in sorted(candidates)
        if path.name != _COMPLETION_SUFFIX
        and path.with_name(path.name + _COMPLETION_SUFFIX) not in candidates
    }


def _parse_durations(data: bytes, path: Path) -> dict[str, float]:
    """Parse the bytes read from a timing file or checked against a sidecar."""
    raw = _timing_map(read_evidence_json(path, kind="timing", data=data))
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
    parser = argparse.ArgumentParser(
        description=__doc__, epilog="Pass pytest options after --.", allow_abbrev=False
    )
    parser.add_argument("--marker", required=True, help="pytest marker band to run")
    parser.add_argument("--shard", type=int, required=True, help="this job's slice")
    parser.add_argument("--shards", type=int, required=True, help="slice count")
    parser.add_argument("--durations", type=Path, help="recorded seconds by node ID")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--exclude-node", action="append", default=[])
    parser.add_argument("--bind-coverage", type=Path, help=argparse.SUPPRESS)
    argv = sys.argv[1:] if argv is None else argv
    boundary = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:boundary])
    rest = argv[boundary + 1 :]
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    if not 0 <= args.shard < args.shards:
        parser.error("--shard must lie in [0, --shards)")
    if args.bind_coverage and (
        args.marker or args.exclude_node or "--cov-branch" not in rest
    ):
        parser.error("--bind-coverage requires the full corpus and branch coverage")
    return args, rest


def _duration_sidecars(path: Path) -> tuple[Path, Path]:
    """Return the recorder's completion record and progress log paths."""
    return (
        path.with_name(path.name + _COMPLETION_SUFFIX),
        path.with_name(path.name + ".progress.jsonl"),
    )


def _duration_output_path(pytest_args: list[str]) -> Path | None:
    """Find the last recorder destination in the pytest options."""
    end = pytest_args.index("--") if "--" in pytest_args else len(pytest_args)
    for index in range(end - 1, -1, -1):
        name, separator, value = pytest_args[index].partition("=")
        if name == _DURATION_OUTPUT:
            if separator:
                return ROOT / value
            return ROOT / pytest_args[index + 1] if index + 1 < end else None
    return None


def _check_duration_output(
    output: Path | None, protected: Sequence[tuple[str, Path]]
) -> None:
    """Keep timing recorder paths separate from the shard's own artifacts."""
    if output is None:
        return
    destinations = {path.resolve() for path in (output, *_duration_sidecars(output))}
    parent = output.parent.resolve()
    snapshot = re.compile(re.escape(output.name) + r"\.[0-9a-f]{64}\.json")
    for option, path in protected:
        if path.resolve() in destinations or (
            path.parent.resolve() == parent and snapshot.fullmatch(path.name)
        ):
            raise ValueError(
                f"{_DURATION_OUTPUT} {output} would replace {option} {path}"
            )


def shard_main(argv: list[str] | None = None) -> int:
    """Collect the band, run this shard's slice, return pytest's exit code."""
    args, rest = _parse_args(argv)
    try:
        data = args.bind_coverage.resolve() if args.bind_coverage is not None else None
        coverage_outputs = (
            (
                ("--bind-coverage", data),
                ("--bind-coverage receipt", coverage_evidence.sidecar(data)),
            )
            if data is not None
            else ()
        )
        if args.manifest is not None and coverage_outputs:
            manifest = args.manifest.resolve()
            for option, output in coverage_outputs:
                if output.resolve() == manifest:
                    raise ValueError(
                        f"--manifest {args.manifest} would replace {option} {output}"
                    )
        if args.durations is not None:
            timing = args.durations.resolve()
            outputs = (("--manifest", args.manifest), *coverage_outputs)
            for option, output in outputs:
                if output is not None and output.resolve() == timing:
                    raise ValueError(
                        f"{option} {output} would replace --durations {args.durations}"
                    )
        protected = [
            (option, path.absolute())
            for option, path in (
                ("--durations", args.durations),
                ("--manifest", args.manifest),
                *coverage_outputs,
            )
            if path is not None
        ]
        _check_duration_output(_duration_output_path(rest), protected)
        durations = load_durations(args.durations) if args.durations else None
        state = coverage_evidence.checkout(ROOT, data) if data is not None else ""
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        return 2
    try:
        collected = collect_ids(args.marker)
    except (CollectionError, OSError) as error:
        print(error, file=sys.stderr)
        return 2
    excluded = set(args.exclude_node)
    if unknown := sorted(excluded.difference(collected)):
        nodes = ", ".join(repr(node) for node in unknown)
        print(f"--exclude-node: not in the collected corpus: {nodes}", file=sys.stderr)
        return 2
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
    env = _pytest_env()
    if protected:
        env[_DURATION_PROTECTED] = json.dumps(
            [(option, str(path)) for option, path in protected]
        )
    if data is not None:
        try:
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
                env,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(
                f"coverage shard {args.shard}/{args.shards}: {error}", file=sys.stderr
            )
            return 2
    return subprocess.run(
        [sys.executable, "-m", "pytest", *rest, *ids],
        cwd=ROOT,
        env=env,
        check=False,
    ).returncode


def _run_coverage_shard(
    data: Path,
    state: str,
    pytest_args: list[str],
    selection: dict[str, Any],
    env: dict[str, str],
) -> int:
    """Publish coverage with the completed shard selection."""
    expected: list[str] = selection["nodes"]
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
                *expected,
            ],
            cwd=ROOT,
            env={**env, "COVERAGE_FILE": str(staged)},
            check=False,
        )
        if result.returncode:
            return result.returncode
        actual = coverage_evidence.completed(execution)
        if actual != expected:
            missing = sorted(set(expected).difference(actual))
            unexpected = sorted(set(actual).difference(expected))
            details = [
                f"ran a different selection (expected {len(expected)} tests, "
                f"got {len(actual)})"
            ]
            for label, nodes in (("missing", missing), ("unexpected", unexpected)):
                if nodes:
                    sample = ", ".join(repr(node) for node in nodes[:5])
                    extra = f" and {len(nodes) - 5} more" if len(nodes) > 5 else ""
                    details.append(f"{label}: {sample}{extra}")
            raise ValueError("\n".join(details))
        if coverage_evidence.checkout(ROOT, data) != state:
            raise ValueError("checkout inputs changed during coverage collection")
        coverage_evidence.publish(staged, data, state, selection)
    return 0


class _TimingRun(NamedTuple):
    """Timings from one run and the file that supplied each sample."""

    durations: dict[str, float]
    identity: dict[str, object]
    sources: dict[str, Path]


def load_run(
    directory: Path,
    expected: set[str],
    *,
    sidecars: Mapping[Path, dict[str, Any]] | None = None,
) -> dict[str, float]:
    """Return timings for a complete, validated run."""
    return _load_run(directory, expected, sidecars=sidecars).durations


def _load_run(
    directory: Path,
    expected: set[str],
    *,
    sidecars: Mapping[Path, dict[str, Any]] | None = None,
) -> _TimingRun:
    """Validate sidecars and retain the identity shared by every shard."""
    if sidecars is None:
        sidecars = read_completion_sidecars(directory)
    if not sidecars:
        raise ValueError(f"{directory}: no timing completion metadata")
    result: dict[str, float] = {}
    sources: dict[str, Path] = {}
    identity = None
    for path, metadata in sidecars.items():
        durations_path = path.with_name(path.name.removesuffix(_COMPLETION_SUFFIX))
        if "durations_file" in metadata:
            name = metadata["durations_file"]
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError(f"{path}: invalid timing snapshot path")
            durations_path = path.parent / name
        if (
            metadata.get("schema") != 1
            or metadata.get("exitstatus") != 0
            or metadata.get("finished") != metadata["collected"]
        ):
            raise ValueError(f"{path}: failed, incomplete, or altered timing run")
        data = durations_path.read_bytes()
        if metadata.get("durations_sha256") != hashlib.sha256(data).hexdigest():
            raise ValueError(f"{path}: altered timing run")
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
        data = output.read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise ValueError(f"{output}: cannot read timing snapshot: {error}") from error
    raw = read_evidence_json(output, kind="timing", data=data)
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
    seen: set[tuple[object, object]] = set()
    for directory, run in zip(directories, loaded, strict=True):
        identity = run.identity
        run_id, attempt = identity.get("id"), identity.get("attempt")
        if run_id is None:
            continue
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
    try:
        ids = collect_ids(args.marker)
        serial = set(args.serial_node)
        if unknown := sorted(serial.difference(ids)):
            nodes = ", ".join(repr(node) for node in unknown)
            raise ValueError(f"--serial-node: not in the collected corpus: {nodes}")
        refresh(args.runs, ids, args.output)
        durations = load_durations(args.output)
        parallel = [node for node in ids if node not in serial]
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
    except (CollectionError, ValueError, OSError) as error:
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
        self.completion, self.progress = _duration_sidecars(path)
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
            self.completion,
            json.dumps(metadata, sort_keys=True, indent=1) + "\n",
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the recording destination."""
    parser.addoption("--collection-output", type=Path)
    parser.addoption(_DURATION_OUTPUT, type=Path)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Write selected node IDs independently of terminal diagnostics."""
    destination = session.config.getoption("collection_output")
    if destination is not None:
        write_text(destination, json.dumps([item.nodeid for item in session.items]))


def pytest_configure(config: pytest.Config) -> None:
    """Only the controller owns the destination."""
    path = config.getoption(_DURATION_OUTPUT)
    if path is not None and not hasattr(config, "workerinput"):
        path = path.absolute()
        if raw := os.environ.get(_DURATION_PROTECTED):
            try:
                protected = [(option, Path(value)) for option, value in json.loads(raw)]
                _check_duration_output(path, protected)
            except (OSError, ValueError, RuntimeError) as error:
                raise pytest.UsageError(str(error)) from error
        config.pluginmanager.register(Recorder(path))


if __name__ == "__main__":
    raise SystemExit(main())
