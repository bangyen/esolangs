"""Exact screen coverage and resume preserve only matching completed evidence."""

import json
import shlex
import sys
from pathlib import Path

import pytest

from scripts import _reference_identity as reference
from scripts import _screen_evidence as evidence


def record(identifier, status="measured", **fields):
    value = {
        "language": "brainfuck",
        "table_bits": 8,
        "ordinal": 0,
        "rows": 0,
        "case_id": identifier,
        "status": status,
        **fields,
    }
    value["evidence_sha256"] = evidence.checksum(value)
    return value


@pytest.mark.parametrize(
    "change", ["duplicate", "unplanned", "modified", "planned-duplicate"]
)
def test_exact_coverage_rejects_invalid_evidence(change):
    a, b = evidence.case_id("a"), evidence.case_id("b")
    records, expected = [record(a)], [a, b]
    if change == "duplicate":
        records.append({**records[0], "ordinal": 1})
    elif change == "unplanned":
        records = [record(evidence.case_id("c"))]
    elif change == "modified":
        records[0]["rows"] = 8
    else:
        expected = [a, a]
    with pytest.raises(ValueError, match=r"duplicate|invalid"):
        evidence.validate(records, expected)


def test_resume_filters_interrupted_cases_and_checks_provenance(tmp_path):
    identifiers = [evidence.case_id(i) for i in range(3)]
    identity = {
        "checkout": {"commit": "abc"},
        "settings": {"cap": 1},
        "runtime": {"python": "3.14", "dependencies": [["pytest", "9.1"]]},
    }
    plan = {"case_ids": identifiers, "tables": 3}
    records = [
        record(identifier, status, size=4, rows=1 if status == "dropped" else 0)
        for identifier, status in zip(
            identifiers, ["measured", "dropped", "skipped"], strict=True
        )
    ]
    for index, value in enumerate(records):
        value["ordinal"] = index
    manifest = {
        "schema": 3,
        "screen": "fixture",
        **identity,
        "plan": plan,
        "status": "timeout",
        "cases": records,
    }
    path = tmp_path / "resume.json"
    path.write_text(json.dumps(manifest))
    assert evidence.resume(path, identity, plan, "fixture") == records[:1]
    for key, value in [
        ("checkout", {"commit": "other"}),
        ("settings", {"cap": 2}),
        ("plan", {"case_ids": identifiers[::-1], "tables": 3}),
        ("schema", 1),
        ("runtime", {"python": "3.12"}),
        ("runtime", {"python": "3.14", "dependencies": [["pytest", "9.2"]]}),
        ("status", "source-changed"),
    ]:
        path.write_text(json.dumps({**manifest, key: value}))
        with pytest.raises(ValueError, match="do not match"):
            evidence.resume(path, identity, plan, "fixture")


def test_resumed_size_build_does_not_generate(tmp_path, monkeypatch):
    from scripts.screens import _build

    identifier = _build.size_cases("brainfuck", ["0001"])[0]
    path = tmp_path / "worker.json"
    path.write_text(json.dumps({"cases": [record(identifier, size=17)]}))
    monkeypatch.setenv("ESOLANGS_SCREEN_RESUME", str(path))
    monkeypatch.setattr(evidence, "_CACHE", None)
    # _build uses the script import, shared with actual CLI workers.
    import _screen_evidence

    monkeypatch.setattr(_screen_evidence, "_CACHE", None)
    assert _build.sizes(
        "brainfuck", lambda _: pytest.fail("regenerated"), ["0001"]
    ) == {"0001": 17}


def test_reference_identity_tracks_script_and_arguments(tmp_path):
    script = tmp_path / "reference.py"
    script.write_text('print("one")\n')
    command = shlex.join([sys.executable, str(script), "{program}"])
    before = reference.fingerprint(command)
    assert before["version"]["status"] is None
    assert before["arguments"][-1] == "{program}"
    assert str(Path(sys.executable).resolve()) in before["files"]
    script.write_text('print("two")\n')
    after = reference.fingerprint(command)
    assert before["files"][str(script)] != after["files"][str(script)]


@pytest.mark.medium
def test_campaign_timeout_preserves_original_before_minimizing(tmp_path):
    import subprocess

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    worker = tmp_path / "scripts/finding.py"
    worker.parent.mkdir()
    worker.write_text(
        "import argparse,sys,time\n"
        f"sys.path[:0] = [{str(scripts)!r}, {str(scripts / 'screens')!r}]\n"
        "import differential as d\nfrom _budget import options,supervise\n"
        "from _screen_evidence import case_id\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser();options(p);a=p.parse_args()\n"
        "plan={'tables':1,'case_ids':[case_id('brainfuck',0,0)],'work_bound':1}\n"
        "if supervise(p,a,Path(__file__),plan):\n"
        " r=d.Runner(d.SPECS['brainfuck'],'reference-command',1)\n"
        " r.check=lambda *_: d.Case('+','input','output',"
        "d.Outcome('halt',b'0'),d.Outcome('halt',b'1'))\n"
        " r.minimize=lambda *_: time.sleep(10)\n"
        " d.campaign(r,1,0)\n"
    )
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(worker), "--budget-seconds", "1", "--report", str(report)],
        capture_output=True,
        text=True,
        timeout=4,
    )
    assert result.returncode == 124, result.stdout + result.stderr
    manifest = json.loads(report.read_text())
    assert manifest["status"] == "timeout"
    assert manifest["completed_cases"] == 1
    finding = manifest["cases"][0]
    assert (finding["seed"], finding["index"], finding["reference"]) == (
        0,
        0,
        "reference-command",
    )
    assert finding["counterexample"]["program"] == "+"
    assert finding["counterexample"]["stdin"] == "input"
    assert finding["counterexample"]["ours"]["output"] == "MA=="
    assert finding["counterexample"]["ref"]["output"] == "MQ=="
