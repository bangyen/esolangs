"""Shared fixtures for the esolangs test suite."""

import contextlib

import coverage
import pytest
from coverage.collector import Collector


@pytest.fixture(autouse=True)
def _repair_coverage_lock():
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
