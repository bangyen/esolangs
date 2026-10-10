"""Relocation, provenance gates and independently recoverable evidence."""

# ruff: noqa: I001, SLF001
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import _screen_evidence as evidence
from scripts import _differential_campaign as campaign
from scripts import promote_differential as promotion
import differential as d
import _replay_evidence as replay
from scripts import _screen_collect as collector


def artifact(tmp_path):
    runner = d.Runner(d.SPECS["brainfuck"], "reference {program}", 0.5)
    original = d.Case(
        "++.",
        "",
        "output differs",
        d.Outcome("halt", b"\x02"),
        d.Outcome("halt", b"\x03"),
    )
    _, value = campaign.artifact(runner, 0, 0, d._case_record(original))
    value["identity"] = {
        "checkout": {"commit": "a"},
        "runtime": {"python": "same"},
        "reference": {"sha256": "ref"},
    }
    path = tmp_path / "moved.json"
    path.write_text(json.dumps(value))
    return path, value


@pytest.mark.parametrize("legacy", [False, True])
def test_replay_rebuilds_paths_and_ignores_saved_executable(tmp_path, legacy):
    path, value = artifact(tmp_path)
    value["replay"][:2] = ["/missing/python", "/missing/differential.py"]
    value["replay"][value["replay"].index("--replay-case") + 1] = "/old/case.json"
    if legacy:
        del value["replay_parameters"]
    command = replay.command(value, path, reference="new-reference {program}")
    assert command[0] == sys.executable
    assert Path(command[1]).name == "differential.py"
    assert Path(command[1]).parent.name == "scripts"
    assert command[command.index("--replay-case") + 1] == str(path)
    assert command[command.index("--ref") + 1] == "new-reference {program}"
    assert not any(
        "/missing/" in argument or "/old/" in argument for argument in command
    )


@pytest.mark.parametrize("bound", [0, -1, True, "5", float("nan"), float("inf")])
def test_replay_rejects_invalid_structured_bounds(tmp_path, bound):
    path, value = artifact(tmp_path)
    value["replay_parameters"]["budget_seconds"] = bound
    with pytest.raises(ValueError, match="deadline"):
        replay.command(value, path)


@pytest.mark.parametrize("axis", ["checkout", "runtime", "reference", "missing"])
def test_provenance_blocks_before_execution_and_records_override(
    tmp_path, monkeypatch, capsys, axis
):
    path, value = artifact(tmp_path)
    current = json.loads(json.dumps(value["identity"]))
    if axis == "missing":
        value["identity"] = None
        path.write_text(json.dumps(value))
    else:
        current[axis] = {"changed": True}
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"identity": current}))
    monkeypatch.setenv("ESOLANGS_SCREEN_RESUME", str(context))
    runner = SimpleNamespace(
        spec=SimpleNamespace(language="brainfuck"),
        template="reference",
        check=lambda *_: pytest.fail("executed before provenance gate"),
    )
    with pytest.raises(ValueError, match="allow-drift"):
        campaign.replay(runner, path, 0, d._case_record)
    original = d._case_load(value["original"])
    runner.check = lambda *_: original
    runner.last_outcomes = original.ours, original.ref
    assert campaign.replay(runner, path, 0, d._case_record, allow_drift=True) == 1
    observation = json.loads(capsys.readouterr().out)
    assert observation["provenance"]["override"]
    assert observation["provenance"]["drift"] == (
        [axis] if axis != "missing" else ["checkout", "runtime", "reference"]
    )


def record(identifier, ordinal):
    value = {
        "language": "brainfuck",
        "table_bits": 8,
        "ordinal": ordinal,
        "rows": 0,
        "case_id": identifier,
        "status": "measured",
        "size": 4,
    }
    value["evidence_sha256"] = evidence.checksum(value)
    return value


def test_resume_reuses_valid_records_and_retries_corrupt_and_duplicate_cases(tmp_path):
    identity = {"checkout": {}, "runtime": {}, "settings": {}}
    plan = {"case_ids": ["a", "b", "c", "d"], "tables": 4}
    records = [
        record("a", 0),
        record("b", 1),
        record("c", 2),
        record("c", 3),
        record("d", 4),
    ]
    records[1]["size"] = 999
    path = tmp_path / "manifest.json"
    value = {
        "schema": 3,
        **identity,
        "plan": plan,
        "screen": "fixture",
        "status": "invalid-evidence",
        "cases": records,
        "rejected": [{"ordinal": 1}],
    }
    path.write_text(json.dumps(value))
    recovered = evidence.resume(path, identity, plan, "fixture")
    assert [item["case_id"] for item in recovered] == ["a", "d"]
    evidence.validate(recovered, plan["case_ids"])
    assert evidence.read(path) == value
    with pytest.raises(ValueError, match="do not match"):
        evidence.resume(
            path, identity | {"runtime": {"changed": True}}, plan, "fixture"
        )


def test_duplicate_with_invalid_payload_cannot_make_identity_unambiguous():
    records = [record("a", 0), record("a", 1)]
    records[1]["size"] = -1
    accepted, rejected = collector.recover(records, ["a"])
    assert accepted == []
    assert len(rejected) == 2


def test_large_promoted_case_records_reason_and_passes_lint(tmp_path, monkeypatch):
    path, value = artifact(tmp_path)
    program = "+" * 1000 + "."
    original = d.Case(
        program,
        "",
        "output differs",
        d.Outcome("halt", bytes([1000 % 256])),
        d.Outcome("halt", b"wrong"),
    )
    value["original"] = d._case_record(original)
    path.write_text(json.dumps(value))
    observation = json.dumps(
        {
            "expected_cause": original.cause,
            "observed": d._case_record(original),
            "verdict": "reproduced",
            "provenance": {"override": False, "drift": []},
        }
    ).encode()
    monkeypatch.setattr(promotion, "run", lambda *_: (1, observation, b"", None))
    destination = tmp_path / "test_large.py"
    reason = 'Byte arithmetic wraps at 256. "quoted" λ ' * 30
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote",
            str(path),
            str(destination),
            "--expected-side",
            "ours",
            "--reason",
            reason,
        ],
    )
    promotion.main()
    namespace = {}
    exec(compile(destination.read_text(), str(destination), "exec"), namespace)
    namespace["test_promoted_finding"]()
    assert namespace["CASE"]["reason"] == reason
    assert len(namespace["CASE"]["finding_sha256"]) == 64
    assert namespace["CASE"]["identity"] == value["identity"]
    code, output, error, status = promotion.run_formatter(
        [sys.executable, "-m", "ruff", "check", str(destination)], b"", 5
    )
    assert code == 0, output + error
    assert status is None


def test_collection_drops_both_copies_when_duplicate_payload_is_corrupt(tmp_path):
    records = [record("a", 0), record("a", 1), record("b", 2)]
    records[1]["size"] = -1
    progress = tmp_path / "progress"
    progress.write_text("\n".join(json.dumps(item) for item in records) + "\n")
    result = collector.collect(
        {
            "progress": str(progress),
            "expected": ["a", "b"],
            "status": "complete",
            "findings": str(tmp_path / "findings"),
        }
    )
    assert [item["case_id"] for item in result["cases"]] == ["b"]
    assert len(result["rejected"]) == 2


@pytest.mark.medium
def test_real_screen_resume_retries_only_rejected_case(tmp_path):
    import subprocess

    script = Path(__file__).resolve().parents[2] / "scripts/screens/sharing.py"
    report = tmp_path / "report.json"
    command = [
        sys.executable,
        str(script),
        "brainfuck",
        "--sample",
        "1",
        "--budget-seconds",
        "5",
        "--report",
        str(report),
    ]
    first = subprocess.run(command, capture_output=True, text=True, timeout=8)
    assert first.returncode == 0, first.stdout + first.stderr
    value = json.loads(report.read_text())
    rejected = value["cases"][0]["case_id"]
    value["cases"][0]["size"] += 1
    value["status"] = "invalid-evidence"
    report.write_text(json.dumps(value))
    resumed = subprocess.run(
        [*command, "--resume", str(report)], capture_output=True, text=True, timeout=8
    )
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    result = json.loads(report.read_text())
    assert result["status"] == "complete"
    assert len(result["cases"]) == result["plan"]["tables"]
    assert {case["case_id"] for case in result["cases"] if not case.get("reused")} == {
        rejected
    }
