"""Shared fixtures for the esolangs test suite."""

import contextlib
import time
from collections.abc import Generator
from pathlib import Path

import coverage
import pytest
from _pytest.reports import TestReport
from coverage.collector import Collector

from tests.duration_policy import hard_ceiling, violation


def _reject_stale_install() -> None:
    """Fail fast when ``esolangs`` resolves outside this checkout.

    A stale editable install shadows the repo: plain ``pytest`` then imports a
    different checkout's package while the tests read this one's files.  Run
    via ``just test-py`` (or with ``PYTHONPATH=$PWD/src``), or reinstall the
    editable install.
    """
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
    """Give every test its band's hard stop unless it set a ``timeout`` itself."""
    for item in items:
        if item.get_closest_marker("timeout") is not None:
            continue
        markers = {marker.name for marker in item.iter_markers()}
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
    """Undo a coverage C-tracer lock leak left by a signal-handler exception.

    The timeout-protection tests use ``signal.alarm`` handlers that raise an
    exception to interrupt non-terminating interpreters.  If that exception
    unwinds through coverage's C tracer between ``lock_data`` and
    ``unlock_data``, the non-reentrant ``data_lock`` stays held and the next
    traced call event deadlocks.  Repairing the lock between tests keeps a
    one-off leak from hanging the whole session.
    """
    yield
    cov = coverage.Coverage.current()
    collector = getattr(cov, "_collector", None) if cov is not None else None
    if not isinstance(collector, Collector):
        return
    lock = collector.data_lock
    if lock is not None:
        with contextlib.suppress(RuntimeError):
            lock.release()
