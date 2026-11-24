"""Evidence reports retain skips and reject incomplete scans."""

from types import SimpleNamespace

import pytest

from conftest import pytest_terminal_summary


def test_evidence_reports(tmp_path, monkeypatch):
    _contract_summary_counts_outcomes_and_reasons()
    _failed_collection_removes_partial_coverage(tmp_path, monkeypatch)


def test_deadcode_rejects_partial_coverage_before_reporting_or_updating(
    tmp_path, monkeypatch, capsys
):
    import sys

    from coverage import CoverageData

    from tests.support.reference import REFERENCE
    from tests.tooling.script_support import REPO_ROOT, load

    scripts = REPO_ROOT / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = load(scripts / "deadcode.py")
    package = module.REGISTRY[module.resolve(REFERENCE)].id
    source = module.LANGUAGES / package / "generator.py"
    data = tmp_path / ".coverage"
    coverage = CoverageData(basename=str(data))
    coverage.add_arcs({str(source): [(-1, 1), (1, -1)]})
    coverage.write()
    baseline = tmp_path / "known.toml"
    baseline.write_text("# existing baseline\n")
    monkeypatch.setattr(module, "KNOWN", baseline)
    for flags in ([], ["--update"]):
        monkeypatch.setattr(sys, "argv", ["deadcode", "--data", str(data), *flags])
        with pytest.raises(SystemExit) as caught:
            module.main()
        assert caught.value.code == 2
        captured = capsys.readouterr()
        assert "generator source files" in captured.err
        assert captured.out == ""
        assert baseline.read_text() == "# existing baseline\n"
    assert len(module._report(data, [package])) == 1


def _contract_summary_counts_outcomes_and_reasons():
    lines = []
    reporter = SimpleNamespace(
        stats={
            "": [SimpleNamespace(nodeid="tests/generators/test_contract.py::setup")],
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
    with pytest.raises(subprocess.CalledProcessError):
        module._collect(data, [])
    assert not data.exists()
    assert failed.call_args.kwargs["check"] is True
