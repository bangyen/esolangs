"""Shared fixtures for the esolangs test suite."""

import contextlib
import os
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import coverage
import pytest
from _pytest.reports import TestReport
from coverage.collector import Collector

from tests.support.duration_policy import (
    cost_checks_enabled,
    evidence_violation,
    hard_ceiling,
    violation,
)

_COST_CHECKS = pytest.StashKey[bool]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Keep performance checks explicit and separate from correctness runs."""
    parser.addoption("--check-cost-bands", action="store_true", default=False)


def pytest_configure(config: pytest.Config) -> None:
    """Reject parallel or traced performance measurements."""
    try:
        config.stash[_COST_CHECKS] = cost_checks_enabled(
            requested=config.getoption("check_cost_bands"),
            workers=config.getoption("numprocesses", default=None),
            coverage_active=bool(config.getoption("cov_source", default=None))
            or coverage.Coverage.current() is not None,
        )
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error


def _reject_stale_install() -> None:
    """Fail fast when ``esolangs`` resolves outside this checkout."""
    try:
        import esolangs
    except ModuleNotFoundError as exc:
        raise ImportError(
            "esolangs is not importable: run via `just test-py` "
            "(or with PYTHONPATH=$PWD/src)."
        ) from exc
    here = Path(__file__).resolve().parent / "src" / "esolangs"
    location = esolangs.__file__
    got = Path(location).resolve().parent if location is not None else None
    if got != here:
        raise ImportError(
            f"esolangs resolves to {got}, not this checkout ({here}): "
            "a stale editable install is shadowing the repo. Run via "
            "`just test-py` (or with PYTHONPATH=$PWD/src)."
        )


_reject_stale_install()


def _drop_hook_git_env() -> None:
    """Unset the repository variables git exports to hooks.

    Under a pre-push hook ``GIT_DIR`` names the pushing repository, so a
    test that runs ``git commit`` in a scratch directory would commit to
    the real branch instead.
    """
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
    ):
        os.environ.pop(name, None)


_drop_hook_git_env()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test its hard stop and require evidence for weekly cost."""
    # The nested collection probe took 2.64s alone, 22.8s under late pool load.
    items.sort(key=lambda item: not item.nodeid.startswith("tests/tooling/"))
    for item in items:
        markers = {marker.name for marker in item.iter_markers()}
        evidence = item.get_closest_marker("cost_evidence")
        message = evidence_violation(markers, evidence.args if evidence else ())
        if message is not None:
            raise pytest.UsageError(f"{item.nodeid}: {message}")
        if item.get_closest_marker("timeout") is not None:
            continue
        item.add_marker(pytest.mark.timeout(hard_ceiling(markers)))


#: CPU time the call phase spent, read back when its band is checked.
_CPU_TIME = pytest.StashKey[float]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, object, object]:
    """Record the call's CPU time, so a starved test can be told from a slow one."""
    if not item.config.stash[_COST_CHECKS]:
        return (yield)
    started = time.process_time()
    try:
        return (yield)
    finally:
        item.stash[_CPU_TIME] = time.process_time() - started


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[object]
) -> Generator[None, TestReport, TestReport]:
    """Fail tests whose call exceeds their cost band's ceiling."""
    del call
    report = yield
    if (
        not item.config.stash[_COST_CHECKS]
        or report.when != "call"
        or not report.passed
    ):
        return report
    if coverage.Coverage.current() is not None:
        raise pytest.UsageError(
            "cost checks require execution without coverage tracing"
        )
    markers = {marker.name for marker in item.iter_markers()}
    message = violation(markers, report.duration, item.stash.get(_CPU_TIME, None))
    if message is not None:
        report.outcome = "failed"
        report.longrepr = message
    return report


@pytest.fixture(autouse=True)
def _repair_coverage_lock() -> Generator[None, None, None]:
    """Undo a coverage C-tracer lock leak left by a signal-handler exception."""
    yield
    cov = coverage.Coverage.current()
    collector = getattr(cov, "_collector", None) if cov is not None else None
    if not isinstance(collector, Collector):
        return
    lock = collector.data_lock
    if lock is not None:
        with contextlib.suppress(RuntimeError):
            lock.release()


@pytest.fixture(autouse=True)
def _owned_template_boundaries(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep migrated execution cases off legacy source/template adaptation."""
    if not request.node.nodeid.startswith(("src/esolangs/languages/", "tests/")):
        return
    import esolangs

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "canonical tests reached legacy source/template adaptation"
        )

    for module, names in (
        (esolangs, ("_recover_template",)),
        (
            getattr(esolangs, "compat", None),
            ("generate", "instantiate", "load_program", "source_adapter"),
        ),
    ):
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)


@pytest.fixture
def retired_source_adapters(monkeypatch):
    """Keep retired module imports poisoned, with a live control."""
    import importlib
    import sys

    class Block:
        def find_spec(self, fullname, _path=None, _target=None):
            if fullname in {"esolangs.compat", "esolangs.tagged"}:
                raise AssertionError("retired source adapter imported")
            return

    monkeypatch.setattr(sys, "meta_path", [Block(), *sys.meta_path])
    with pytest.raises(AssertionError, match="retired source adapter"):
        importlib.import_module("esolangs.compat")


@pytest.fixture
def native_png(tmp_path: Path):
    """Encode a raster record through the native persistence boundary."""
    import esolangs

    def encode(program):
        path = tmp_path / "source.png"
        esolangs.to_file(program.language, program, path)
        return path.read_bytes()

    return encode


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every worker process the isolated runner starts, in order."""
    from esolangs.runtime import _isolated

    children: list[Any] = []
    popen = _isolated.subprocess.Popen

    def spawn(*args: Any, **kwargs: Any) -> Any:
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    return children


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Show which generator contract cases ran and why others did not."""
    counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for outcome, reports in terminalreporter.stats.items():
        if outcome not in {
            "passed",
            "failed",
            "error",
            "skipped",
            "xfailed",
            "xpassed",
        }:
            continue
        for report in reports:
            if not report.nodeid.startswith("tests/generators/"):
                continue
            counts[outcome] = counts.get(outcome, 0) + 1
            if outcome in {"skipped", "xfailed"}:
                reason = getattr(report, "wasxfail", None)
                if reason is None:
                    reason = str(report.longrepr[2])
                reasons[reason] = reasons.get(reason, 0) + 1
    if counts:
        terminalreporter.section("Generator contract coverage")
        terminalreporter.write_line(
            ", ".join(f"{n} {key}" for key, n in sorted(counts.items()))
        )
        for reason, n in sorted(reasons.items()):
            terminalreporter.write_line(f"{n}: {reason}")
