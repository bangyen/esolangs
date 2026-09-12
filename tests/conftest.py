r"""Shared fixtures for the esolangs test suite."""

import contextlib

import coverage
import pytest
from coverage.collector import Collector


@pytest.fixture(autouse=True)
def _repair_coverage_lock():
    r"""Undo a coverage C-tracer lock leak left by a signal-handler."""
    yield
    cov = coverage.Coverage.current()
    collector = getattr(cov, "_collector", None) if cov is not None else None
    if not isinstance(collector, Collector):
        return
    lock = collector.data_lock
    if lock is not None:
        with contextlib.suppress(RuntimeError):
            lock.release()
