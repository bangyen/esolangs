"""Acceptance and mutation results are backed by pytest call reports."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import mutants
from scripts.verify.coverage import completed
from scripts.verify.pytest_evidence import OUTPUT_OPTION, PLUGIN
from scripts.verify.receipts import AcceptanceRun, _read_execution, validate
from tests.tooling.receipt_support import _checkout

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("options", "accepted"),
    [
        ("--collect-only", False),
        ("-k test_skipped", False),
        ("-k test_selected", True),
    ],
)
def test_receipt_captures_execution_and_effective_selection(
    tmp_path, monkeypatch, options, accepted
):
    root = _checkout(tmp_path / "checkout")
    program = root / "test_probe.py"
    program.write_text(
        "import pytest\n"
        "def test_other():\n    assert False\n"
        "def test_selected():\n    assert True\n"
        'def test_skipped():\n    pytest.skip("skipped during call")\n',
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
        assert completed(output) == evidence["called"]
        for invalid in (
            json.dumps({**evidence, "passed_calls": ["test_probe.py::test_other"]}),
            json.dumps({**evidence, "called": []}),
            json.dumps({**evidence, "selected": evidence["selected"] * 2}),
            json.dumps(evidence).replace(
                '"collect_only": false', '"collect_only": true, "collect_only": false'
            ),
        ):
            output.write_text(invalid, encoding="utf-8")
            with pytest.raises(
                ValueError, match="pytest coverage collection did not complete"
            ):
                completed(output)
            assert _read_execution(root, str(output), 0) is None
        output.write_text("{}")
        with pytest.raises(ValueError, match="execution evidence was changed"):
            validate(receipt, root, {"pytest"})
    else:
        evidence = json.loads(output.read_text())
        assert evidence["passed_calls"] == []
        if options == "-k test_skipped":
            assert evidence["called"] == ["test_probe.py::test_skipped"]
        with pytest.raises(ValueError, match="acceptance"):
            validate(receipt, root, {"pytest"})


@pytest.mark.parametrize(
    ("keyword", "outcome", "accepted"),
    [
        ("", "pass", True),
        ("test_first", "pass", False),
        ("", "skip", False),
        ("", "xfail", False),
        ("", "xpass", False),
    ],
)
def test_accepted_retry_requires_each_failed_call_to_pass(
    tmp_path, monkeypatch, keyword, outcome, accepted
):
    root = _checkout(tmp_path / "checkout")
    (root / "test_probe.py").write_text(
        "import os\nimport pytest\n"
        'retry = os.getenv("RETRY")\n'
        "def test_first():\n    assert retry\n"
        '@pytest.mark.xfail(retry == "xpass", reason="expected failure")\n'
        "def test_second():\n"
        '    if retry == "skip":\n        pytest.skip("skipped in call")\n'
        '    if retry == "xfail":\n        pytest.xfail("expected failure")\n'
        "    assert retry\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("RETRY", raising=False)
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        PLUGIN,
    ]
    original = [*command, OUTPUT_OPTION, str(root / "notes" / "original.json")]
    retry = [*command, OUTPUT_OPTION, str(root / "notes" / "retry.json"), "-k", keyword]
    run = AcceptanceRun(root, [], {"default": 10.0})
    run.declare([("pytest", original, env)])
    for name, args, options, expected in (
        ("pytest", original, env, 1),
        ("pytest retry", retry, {**env, "RETRY": outcome}, 0),
    ):
        result = subprocess.run(
            args,
            cwd=root,
            env=options,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == expected, result.stdout + result.stderr
        run.record(name, 0.1, result.returncode, result.stdout, command=args)

    ids = ["test_probe.py::test_first", "test_probe.py::test_second"]
    reports = json.loads((root / "notes" / "retry.json").read_text())
    assert reports["called"] == (ids[:1] if keyword else ids)
    assert reports["passed_calls"] == (ids if accepted else ids[:1])
    assert run.pytest_retry_covers(ids) is accepted
    assert not run.pytest_retry_covers(ids[:1])
    run.accepted_retries.add("pytest")
    receipt, passed = run.finish(0)
    assert passed is accepted
    if accepted:
        validate(receipt, root, {"pytest"})
    else:
        record = json.loads(receipt.read_text())
        receipt.write_text(json.dumps({**record, "status": "passed"}))
        with pytest.raises(ValueError, match="acceptance"):
            validate(receipt, root, {"pytest"})


@pytest.mark.parametrize(
    ("body", "options", "status"),
    [
        ("assert True", [], "survived"),
        ("assert False", [], "killed"),
        ("pytest.skip('skipped during call')", [], "inconclusive"),
        ("pytest.xfail('expected failure during call')", [], "inconclusive"),
        ("assert True", ["--collect-only"], "inconclusive"),
        ("assert True", ["-k", "there_is_no_such_test"], "inconclusive"),
        ("assert True", ["--invalid-pytest-option"], "inconclusive"),
    ],
)
def test_mutation_runner_classifies_actual_test_reports(
    tmp_path, monkeypatch, body, options, status
):
    probe = tmp_path / "test_mutant.py"
    probe.write_text(
        f"import pytest\n\ndef test_effect():\n    {body}\n", encoding="utf-8"
    )
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
