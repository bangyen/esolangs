"""A hard stop that fires while a test holds the GIL.

pytest-timeout's thread method needs the GIL to act, so one C-level operation
outlasts it: seeded FRACTRAN fuzz built ``2^8460347622`` (8867738b5) and its
fast-band 30s stop never fired.  Under ``--dist worksteal`` the stuck worker
also keeps its queue, so weekly run 43846216189 sat silent until the 45-minute
job limit, naming nothing.  faulthandler's watchdog is a C thread: it dumps
every thread's stack and exits, and xdist reports the crashed node.
"""

import faulthandler
import os
import sys
from collections.abc import Generator

import pytest

_STDERR = pytest.StashKey[int]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Seconds past a test's timeout marker before the process is killed."""
    parser.addini("gil_watchdog_grace", "watchdog seconds past timeout", default="60")


def pytest_configure(config: pytest.Config) -> None:
    """Keep a descriptor that capture cannot redirect, as pytest's plugin does."""
    try:
        fileno = sys.stderr.fileno()
    except (AttributeError, ValueError):
        assert sys.__stderr__ is not None
        fileno = sys.__stderr__.fileno()
    config.stash[_STDERR] = os.dup(fileno)


def pytest_unconfigure(config: pytest.Config) -> None:
    if _STDERR in config.stash:
        os.close(config.stash[_STDERR])
        del config.stash[_STDERR]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, object, object]:
    """Arm the watchdog over setup, call and teardown, like pytest-timeout."""
    marker = item.get_closest_marker("timeout")
    limit = marker.kwargs.get("timeout", marker.args[0]) if marker else None
    if not limit:
        return (yield)
    grace = float(str(item.config.getini("gil_watchdog_grace")))
    faulthandler.dump_traceback_later(
        float(limit) + grace, exit=True, file=item.config.stash[_STDERR]
    )
    try:
        return (yield)
    finally:
        faulthandler.cancel_dump_traceback_later()
