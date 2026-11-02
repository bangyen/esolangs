"""Evidence reports retain skips and reject incomplete scans."""

from types import SimpleNamespace

from conftest import pytest_terminal_summary
from scripts.ci.generator_timings import compare


def test_contract_summary_counts_outcomes_and_reasons():
    lines = []
    reporter = SimpleNamespace(
        stats={
            "passed": [SimpleNamespace(nodeid="tests/generators/test_contract.py::ok")],
            "skipped": [
                SimpleNamespace(
                    nodeid="tests/generators/test_contract.py::cap",
                    longrepr=("file", 1, "resource cap"),
                )
            ],
            "xfailed": [
                SimpleNamespace(
                    nodeid="tests/generators/test_contract.py::open",
                    wasxfail="open bound",
                )
            ],
        },
        section=lines.append,
        write_line=lines.append,
    )
    pytest_terminal_summary(reporter)
    assert "1 passed, 1 skipped, 1 xfailed" in lines
    assert "1: resource cap" in lines
    assert "1: open bound" in lines


def test_persistent_timing_regressions_rank_before_candidates():
    import json

    a, b = (json.dumps([name, "01"]) for name in ("candidate", "persistent"))

    def run(first, second):
        return {"environment": {}, "controls": {}, "timings": {a: first, b: second}}

    report, _ = compare(run(200, 130), [run(100, 100), run(100, 130)])
    assert report.index("persistent `01`") < report.index("candidate `01`")
