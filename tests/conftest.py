"""Shared fixtures for the esolangs test suite."""

import contextlib
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import coverage
import pytest
from _pytest.reports import TestReport
from coverage.collector import Collector

from tests.support.duration_policy import evidence_violation, hard_ceiling, violation


def _reject_stale_install() -> None:
    """Fail fast when ``esolangs`` resolves outside this checkout."""
    try:
        import esolangs
    except ModuleNotFoundError as exc:
        raise ImportError(
            "esolangs is not importable: run via `just test-py` "
            "(or with PYTHONPATH=$PWD/src)."
        ) from exc
    here = Path(__file__).resolve().parents[1] / "src" / "esolangs"
    location = esolangs.__file__
    got = Path(location).resolve().parent if location is not None else None
    if got != here:
        raise ImportError(
            f"esolangs resolves to {got}, not this checkout ({here}): "
            "a stale editable install is shadowing the repo. Run via "
            "`just test-py` (or with PYTHONPATH=$PWD/src)."
        )


_reject_stale_install()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test its hard stop and require evidence for weekly cost."""
    # The nested collection probe took 2.64s alone, 22.8s under late pool load.
    items.sort(key=lambda item: not item.nodeid.startswith("tests/scripts/"))
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
    if report.when != "call" or not report.passed:
        return report
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


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every worker process the isolated runner starts, in order."""
    from esolangs import _isolated

    children: list[Any] = []
    popen = _isolated.subprocess.Popen

    def spawn(*args: Any, **kwargs: Any) -> Any:
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", spawn)
    return children
