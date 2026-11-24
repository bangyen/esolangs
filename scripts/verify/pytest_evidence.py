"""Record pytest's selected and executed nodes in the controller."""

import json
from pathlib import Path

import pytest

from .process import write_text

OUTPUT_OPTION = "--verification-output"
PLUGIN = "scripts.verify.pytest_evidence"


class ExecutionEvidence:
    """Keep the effective selection and the reports from actual tests."""

    def __init__(self, destination: Path) -> None:
        """Start recording with an empty selection."""
        self.destination = destination
        self.collected: set[str] = set()
        self.called: set[str] = set()
        self.finished: set[str] = set()
        self.failures: set[str] = set()
        self.passed: set[str] = set()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Record the serial selection."""
        self.collected.update(item.nodeid for item in session.items)

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, ids: list[str]) -> None:
        """Record the selection reported by xdist."""
        self.collected.update(ids)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Retain call outcomes and completed test lifecycles."""
        if report.when == "call":
            self.called.add(report.nodeid)
            if report.failed:
                self.failures.add(report.nodeid)
            elif report.passed and not hasattr(report, "wasxfail"):
                self.passed.add(report.nodeid)
        elif report.when == "teardown":
            self.finished.add(report.nodeid)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Publish the reports after the session ends."""
        config = session.config
        evidence = {
            "schema": 1,
            "exitstatus": int(exitstatus),
            "selection": {
                "args": config.args,
                "keyword": config.getoption("keyword", ""),
                "marks": config.getoption("markexpr", ""),
                "deselect": config.getoption("deselect", []),
                "collect_only": config.getoption("collectonly", default=False),
            },
            "selected": sorted(self.collected),
            "called": sorted(self.called),
            "finished": sorted(self.finished),
            "failed_calls": sorted(self.failures),
            "passed_calls": sorted(self.passed),
        }
        write_text(self.destination, json.dumps(evidence, sort_keys=True) + "\n")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the evidence destination."""
    parser.addoption(OUTPUT_OPTION, type=Path)


def pytest_configure(config: pytest.Config) -> None:
    """Record results only in the controller."""
    destination = config.getoption(OUTPUT_OPTION)
    if destination is not None and not hasattr(config, "workerinput"):
        config.pluginmanager.register(ExecutionEvidence(destination))
