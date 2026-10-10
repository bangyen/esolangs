"""Record setup, call and teardown seconds by node ID, including xdist reports."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
from collections import defaultdict
from pathlib import Path
from typing import Protocol

import pytest
from _pytest.reports import TestReport

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import write_text


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
