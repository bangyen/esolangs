"""Shared fixtures for the esolangs test suite."""

import contextlib
from collections.abc import Generator

import coverage
import pytest
from _pytest.reports import TestReport
from coverage.collector import Collector

from tests.duration_policy import hard_ceiling, violation


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test its band's hard stop unless it set a ``timeout`` itself."""
    for item in items:
        if item.get_closest_marker("timeout") is not None:
            continue
        markers = {marker.name for marker in item.iter_markers()}
        item.add_marker(pytest.mark.timeout(hard_ceiling(markers)))


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
    message = violation(markers, report.duration)
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
