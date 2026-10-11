"""CI and release helpers.

``shard`` runs one slice of a pytest marker band, ``refresh`` merges complete
timing runs, ``normalize`` rewrites sdist metadata to SOURCE_DATE_EPOCH, and
``smoke`` exercises an installed distribution.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import signal
import statistics
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

import pytest
from _pytest.reports import TestReport

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.registry import LANGUAGES

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _process import write_text

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


def normalize(path: Path, epoch: int) -> None:
    """Preserve payloads while fixing gzip and tar metadata deterministically."""
    buffer = io.BytesIO()
    with (
        tarfile.open(path, "r:gz") as source,
        tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as target,
    ):
        for member in source.getmembers():
            member.mtime = epoch
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key not in {"mtime", "atime", "ctime"}
            }
            target.addfile(
                member, source.extractfile(member) if member.isfile() else None
            )
    with (
        path.open("wb") as stream,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=stream, mtime=epoch
        ) as compressed,
    ):
        compressed.write(buffer.getvalue())


def normalize_main(argv: list[str]) -> int:
    """Normalize every archive named on the command line to SOURCE_DATE_EPOCH."""
    epoch = int(os.environ["SOURCE_DATE_EPOCH"])
    for name in argv:
        normalize(Path(name), epoch)
    return 0


def _cli(args: list[str], stdin: str = "") -> str:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "esolangs", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout


def _refuses_timeout() -> None:
    try:
        esolangs.run("brainfuck", "+.", timeout=0.1)
    except esolangs.ArgumentError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsupported signal timeout was accepted")
    assert "Unix main thread" in message


def _generator(name: str, *, math_extra: bool, image_extra: bool) -> None:
    """Execute all rows in one process; its parent supplies the deadline."""
    generated = esolangs.generate(name, "0110")
    if image_extra and isinstance(generated, esolangs.Raster):
        generated = esolangs.Raster.from_png(generated.to_png())
    try:
        assert _evaluate(name, generated, timeout=None, inputs=2) == "0110", name
    except esolangs.MissingDependencyError:
        assert not math_extra, name


def _generator_process(name: str, *, math_extra: bool, image_extra: bool) -> None:
    """Bound one language's four rows together, retaining process isolation."""
    args = [sys.executable, "-I", str(Path(__file__).resolve()), "--language", name]
    if math_extra:
        args.append("--math")
    if image_extra:
        args.append("--image")
    subprocess.run(args, timeout=30, check=True)


def smoke(*, math_extra: bool, image_extra: bool = False) -> None:
    """Check installed resources and behaviour outside the source checkout."""
    package = Path(esolangs.__file__).resolve().parent
    assert package.parent.name in {"site-packages", "dist-packages"}, package
    assert (package / "py.typed").is_file()
    assert "brainfuck" in _cli(["list"])
    bound = esolangs.Language("BRAINFUCK")
    program = bound.generate("0110", balance=True)
    assert (
        _evaluate(bound.name, program, inputs=2, isolated=True, max_output=1) == "0110"
    )
    assert (
        bound.read_answer(bound.run(program, stdin=bound.encode_inputs([0, 1]))) == "1"
    )
    assert esolangs.run("brainfuck", "+.", max_steps=2) == "\x01"
    assert esolangs.run("brainfuck", "+.", timeout=1, isolated=True) == "\x01"
    try:
        esolangs.run("brainfuck", "+[]", max_steps=10)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("the bounded runner accepted a diverging program")

    executable = Path(sys.executable).with_name(
        "esolangs.exe" if sys.platform == "win32" else "esolangs"
    )
    entrypoint = subprocess.run(
        [str(executable), "list"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "brainfuck" in entrypoint.stdout
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts["boolean_generator"]:
            _generator_process(name, math_extra=math_extra, image_extra=image_extra)
            assert facts["examples"], name
            for filename in facts["examples"]:
                assert not Path(filename).is_absolute(), filename
                assert (package / filename).is_file(), filename
    examples = esolangs.describe("brainfuck")["examples"]
    assert examples
    example = package / examples[0]
    assert (
        esolangs.read_answer(
            "brainfuck", esolangs.run("brainfuck", example, stdin="0\n1\n")
        )
        == "0"
    )
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "xor.txt"
        source.write_text(_cli(["generate", "brainfuck", "0110"]), encoding="utf-8")
        for row in range(4):
            stdin = esolangs.encode_inputs("brainfuck", [row >> 1, row & 1])
            assert (
                esolangs.read_answer(
                    "brainfuck", _cli(["run", "brainfuck", str(source)], stdin)
                )
                == "0110"[row]
            )
        assert _evaluate("brainfuck", source, timeout=None, inputs=2) == "0110"
        for program, options, code, output, diagnostic in (
            (",.+[]", ["--timeout", "2"], 124, "A\n", "deadline"),
            (",[.]", ["--max-output", "3"], 1, "AAA\n", "output limit exceeded"),
        ):
            source.write_text(program, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "esolangs",
                    "run",
                    "--isolated",
                    *options,
                    "brainfuck",
                    str(source),
                ],
                input="A",
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert result.returncode == code, result
            assert result.stdout == output, result
            assert diagnostic in result.stderr, result
        source.write_text(",>,<.", encoding="utf-8")
        assert _evaluate("brainfuck", source, timeout=None, inputs=2) == "0011"
    rasters = [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["source_kind"] == "raster"
        and esolangs.describe(name)["boolean_generator"]
        and not esolangs.describe(name)["parameterized"]
    ]
    for language in rasters[:2]:
        raster = esolangs.generate(language, "0110")
        assert isinstance(raster, esolangs.Raster)
        if image_extra:
            decoded = esolangs.Raster.from_png(raster.to_png())
        else:
            decoded = raster
            for operation in (raster.to_png, lambda: esolangs.Raster.from_png(b"")):
                try:
                    operation()
                except esolangs.MissingDependencyError as exc:
                    message = str(exc)
                else:
                    raise AssertionError("PNG I/O ran without its image extra")
                assert "esolangs[image]" in message
        for row in range(4):
            bits = [row >> 1, row & 1]
            output = esolangs.run(
                language, decoded, stdin=esolangs.encode_inputs(language, bits)
            )
            assert esolangs.read_answer(language, output) == "0110"[row]
    if hasattr(signal, "SIGALRM"):
        assert (
            _evaluate(
                "brainfuck", esolangs.generate("brainfuck", "0110"), timeout=1, inputs=2
            )
            == "0110"
        )
        try:
            esolangs.run("brainfuck", "+[]", timeout=0.02)
        except esolangs.ExecutionTimeoutError:
            pass
        else:
            raise AssertionError("signal timeout did not stop a loop")
    else:
        _refuses_timeout()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_refuses_timeout).result(timeout=5)
    # A language never halting by itself, and one answering by termination;
    # each check drops out with the last language of its kind.
    for language in [
        name
        for name in esolangs.list_languages()
        if not esolangs.describe(name)["self_halts"]
        and esolangs.describe(name)["boolean_generator"]
        and esolangs.describe(name)["reads_input"]
    ][:1]:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert (
                pool.submit(
                    _evaluate,
                    language,
                    esolangs.generate(language, "0110"),
                    inputs=2,
                    isolated=True,
                ).result(timeout=30)
                == "0110"
            )
    terminating = [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["answer_mode"] == "termination"
        and esolangs.describe(name)["boolean_generator"]
    ][:1]
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), inputs=1, isolated=True
            )
            == "01"
        )
    try:
        esolangs.run("brainfuck", "+[]", timeout=0.5, isolated=True)
    except esolangs.ExecutionTimeoutError:
        pass
    else:
        raise AssertionError("isolated timeout did not stop a loop")
    for language in terminating:
        assert (
            _evaluate(
                language, esolangs.generate(language, "01"), timeout=None, inputs=1
            )
            == "01"
        )
    assert (importlib.util.find_spec("PIL") is not None) == image_extra
    # Each language whose interpreter needs the math extra runs with it and
    # refuses without it; none left means nothing to check.
    for language in [n for n, lang in LANGUAGES.items() if lang.extra == "math"]:
        program = esolangs.generate(language, "01")
        if math_extra:
            assert importlib.util.find_spec("sympy") is not None
            assert _evaluate(language, program, timeout=None, inputs=1) == "01"
        else:
            assert importlib.util.find_spec("sympy") is None
            try:
                esolangs.run(language, program, stdin="")
            except esolangs.MissingDependencyError:
                pass
            else:
                raise AssertionError(f"{language} ran without its math extra")


def smoke_main() -> None:
    """Run the artifact smoke check with or without its optional extra."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math", action="store_true")
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--language", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.language is not None:
        _generator(args.language, math_extra=args.math, image_extra=args.image)
        return
    smoke(math_extra=args.math, image_extra=args.image)
    print("installed distribution smoke check passed")


def main(argv: list[str] | None = None) -> int:
    """Dispatch one CI or release subcommand."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit("usage: ci.py {shard|refresh|normalize|smoke} ...")
    command, rest = argv[0], argv[1:]
    if command == "shard":
        return shard_main(rest)
    if command == "refresh":
        return refresh_main(rest)
    if command == "normalize":
        return normalize_main(rest)
    if command == "smoke":
        sys.argv = [sys.argv[0], *rest]
        smoke_main()
        return 0
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
