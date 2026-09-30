"""Record setup, call and teardown seconds by node ID, including xdist reports."""

import json
from pathlib import Path

import pytest
from _pytest.reports import TestReport


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


def pytest_configure(config: pytest.Config) -> None:
    """Only the controller owns the destination."""
    path = config.getoption("duration_output")
    if path is not None and not hasattr(config, "workerinput"):
        config.pluginmanager.register(Recorder(path))
