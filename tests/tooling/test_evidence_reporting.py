"""Evidence reports retain skips and reject incomplete scans."""

from types import SimpleNamespace

from conftest import pytest_terminal_summary
from scripts.ci.generator_timings import compare


def test_evidence_reports(tmp_path, monkeypatch):
    _contract_summary_counts_outcomes_and_reasons()
    _persistent_timing_regressions_rank_before_candidates()
    _failed_collection_removes_partial_coverage(tmp_path, monkeypatch)


def _contract_summary_counts_outcomes_and_reasons():
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


def _persistent_timing_regressions_rank_before_candidates():
    import json

    a, b = (json.dumps([name, "01"]) for name in ("candidate", "persistent"))

    def run(first, second):
        return {"environment": {}, "controls": {}, "timings": {a: first, b: second}}

    report, _ = compare(run(200, 130), [run(100, 100), run(100, 130)])
    assert report.index("persistent `01`") < report.index("candidate `01`")


def _failed_collection_removes_partial_coverage(tmp_path, monkeypatch):
    import importlib.util
    import subprocess
    import sys
    from pathlib import Path
    from unittest.mock import Mock

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "coverage_audit", scripts / "deadcode.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = tmp_path / ".coverage"
    data.write_text("partial coverage")
    failed = Mock(side_effect=subprocess.CalledProcessError(1, [sys.executable]))
    monkeypatch.setattr(module.subprocess, "run", failed)
    import pytest

    with pytest.raises(subprocess.CalledProcessError):
        module._collect(data, [])  # noqa: SLF001
    assert not data.exists()
    assert failed.call_args.kwargs["check"] is True
