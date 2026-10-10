"""Record setup, call and teardown seconds by node ID, including xdist reports."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Protocol

import pytest
from _pytest.reports import TestReport


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

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """Accumulate every phase; zero-duration reports need no estimate."""
        self.durations[report.nodeid] = (
            self.durations.get(report.nodeid, 0) + report.duration
        )

    def pytest_sessionfinish(self) -> None:
        """Write the measured corpus even when tests fail."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    node: seconds
                    for node, seconds in sorted(self.durations.items())
                    if seconds > 0
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
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
