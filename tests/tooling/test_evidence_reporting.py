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
    state = module.evidence.checkout(module.ROOT, data)
    module.evidence.record(data, state, {"packages": [], "nodes": ["test_probe"]})
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


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ("source", "checkout inputs changed"),
        ("test", "checkout inputs changed"),
        ("database", "does not match its receipt"),
        ("selection", "different test selection"),
        ("receipt", "no coverage receipt"),
    ],
)
def test_deadcode_refuses_stale_saved_coverage(
    tmp_path, monkeypatch, capsys, change, problem
):
    import subprocess
    import sys

    from coverage import CoverageData

    from tests.tooling.script_support import REPO_ROOT, load

    scripts = REPO_ROOT / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = load(scripts / "deadcode.py")
    root = tmp_path.resolve()
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=5)
    languages = root / "languages"
    source = languages / "sample/generator.py"
    source.parent.mkdir(parents=True)
    source.write_text("if True:\n    value = 1\n")
    test = root / "test_sample.py"
    test.write_text("def test_example():\n    pass\n")
    baseline = root / "known.toml"
    baseline.write_text("# saved\n")
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "LANGUAGES", languages)
    monkeypatch.setattr(module, "KNOWN", baseline)
    data = root / "saved.coverage"
    coverage = CoverageData(basename=str(data))
    coverage.add_arcs({str(source): [(-1, 1), (1, 2), (2, -1)]})
    coverage.write()
    state = module.evidence.checkout(root, data)
    selection = {"packages": [], "nodes": ["test_sample.py::test_example"]}
    module.evidence.record(data, state, selection)
    assert module._saved_report(data, [], []) == {}
    if change == "source":
        source.write_text("if True:\n    value = 2\n")
    elif change == "test":
        test.write_text("def test_new():\n    pass\n")
    elif change == "database":
        data.write_bytes(data.read_bytes() + b"different")
    elif change == "selection":
        module.evidence.record(data, state, selection | {"packages": ["sample"]})
    else:
        module.evidence.sidecar(data).unlink()

    monkeypatch.setattr(module, "_report", lambda *_: pytest.fail("parsed stale data"))
    monkeypatch.setattr(sys, "argv", ["deadcode", "--data", str(data), "--update"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert problem in capsys.readouterr().err
    assert baseline.read_text() == "# saved\n"


def test_deadcode_combines_only_complete_bound_shards(tmp_path, monkeypatch):
    import subprocess

    from coverage import CoverageData

    from tests.tooling.script_support import REPO_ROOT, load

    scripts = REPO_ROOT / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    module = load(scripts / "deadcode.py")
    root = tmp_path.resolve()
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=5)
    monkeypatch.setattr(module, "ROOT", root)
    (root / ".gitignore").write_text(".coverage\n.coverage.*\n")
    source = root / "languages/sample/generator.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n")
    monkeypatch.setattr(module, "LANGUAGES", source.parents[1])
    dest, left, right = (
        root / part for part in (".coverage", ".coverage.0", ".coverage.1")
    )
    state = module.evidence.checkout(root, dest, left, right)
    nodes = ["test_sample.py::test_first", "test_sample.py::test_second"]
    for index, shard in enumerate((left, right)):
        coverage = CoverageData(basename=str(shard))
        coverage.add_arcs({str(source): [(-1, 1), (1, -1)]})
        coverage.write()
        module.evidence.record(
            shard,
            state,
            {
                "shard": index,
                "shards": 2,
                "collected": module.evidence.fingerprint(nodes),
                "nodes": [nodes[index]],
            },
        )
    with pytest.raises(ValueError, match="invalid or overlapping"):
        module._saved_report(dest, [], [left, left])
    assert not dest.exists()
    assert module._saved_report(dest, [], [left, right]) == {}
    assert module._saved_report(dest, [], []) == {}
    assert module.evidence.read(dest, state) == {"packages": [], "nodes": nodes}


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
