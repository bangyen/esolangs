"""Acceptance and mutation results are backed by pytest call reports."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import mutants
from scripts.verify.pytest_evidence import OUTPUT_OPTION, PLUGIN
from scripts.verify.receipts import AcceptanceRun, validate
from tests.tooling.receipt_support import _checkout

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("options", "accepted"),
    [("--collect-only", False), ("-k test_selected", True)],
)
def test_receipt_captures_execution_and_effective_selection(
    tmp_path, monkeypatch, options, accepted
):
    root = _checkout(tmp_path / "checkout")
    program = root / "test_probe.py"
    program.write_text(
        "def test_other():\n    assert False\ndef test_selected():\n    assert True\n",
        encoding="utf-8",
    )
    output = root / "notes" / "execution.json"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        PLUGIN,
        OUTPUT_OPTION,
        str(output),
    ]
    monkeypatch.setenv("PYTEST_ADDOPTS", options)
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    run = AcceptanceRun(root, [], {"default": 10.0})
    run.declare([("pytest", command, env)])
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    run.record("pytest", 0.1, result.returncode, result.stdout)
    receipt, passed = run.finish(result.returncode)
    assert passed is accepted
    if accepted:
        validate(receipt, root, {"pytest"})
        evidence = json.loads(output.read_text())
        assert evidence["selection"]["keyword"] == "test_selected"
        assert evidence["called"] == ["test_probe.py::test_selected"]
        output.write_text("{}")
        with pytest.raises(ValueError, match="execution evidence was changed"):
            validate(receipt, root, {"pytest"})
    else:
        with pytest.raises(ValueError, match="acceptance"):
            validate(receipt, root, {"pytest"})


@pytest.mark.parametrize(
    ("assertion", "options", "status"),
    [
        ("True", [], "survived"),
        ("False", [], "killed"),
        ("True", ["--collect-only"], "inconclusive"),
        ("True", ["-k", "there_is_no_such_test"], "inconclusive"),
        ("True", ["--invalid-pytest-option"], "inconclusive"),
    ],
)
def test_mutation_runner_classifies_actual_test_reports(
    tmp_path, monkeypatch, assertion, options, status
):
    probe = tmp_path / "test_mutant.py"
    probe.write_text(f"def test_effect():\n    assert {assertion}\n", encoding="utf-8")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        str(probe),
        *options,
    ]
    actual, output = mutants._run(command, 10)
    assert actual == status, output
