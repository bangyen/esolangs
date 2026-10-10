"""Setup and publication deadlines bound filesystem work and reject invalid reuse."""

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import _runtime_identity as runtime
from scripts import _screen_evidence as evidence
from scripts import _screen_phase as phase
from scripts.screens import _budget, sharing


def test_sharing_prices_before_corpus_preparation(monkeypatch):
    monkeypatch.setattr(sharing, "setup", lambda *_: pytest.fail("prepared corpus"))
    monkeypatch.setattr(
        sys, "argv", ["sharing", "brainfuck", "--sample", "100", "--max-work", "1"]
    )
    with pytest.raises(SystemExit) as caught:
        sharing.main()
    assert caught.value.code == 2
    monkeypatch.setattr(sys, "argv", ["sharing", "brainfuck", "--dry-run"])
    sharing.main()


def test_setup_phases_share_the_deadline(monkeypatch):
    ticks = iter([100, 101, 103])
    monkeypatch.setattr(_budget, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    remaining = []
    monkeypatch.setattr(
        _budget, "run_phase", lambda _op, _data, bound: remaining.append(bound) or {}
    )
    args = argparse.Namespace(setup_seconds=5)
    _budget.setup(args, "metadata", {})
    _budget.setup(args, "reference", {})
    assert remaining == [4, 2]


@pytest.mark.medium
def test_publication_deadline_preserves_previous_complete_report(tmp_path):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    worker = tmp_path / "slow_write.py"
    marker = tmp_path / "fsync_started"
    worker.write_text(
        "import sys,json,time\nfrom pathlib import Path\n"
        f"sys.path.insert(0,{str(scripts)!r})\n"
        "import _screen_phase as phase\nimport _atomic as atomic\n"
        "def stalled(fd):\n"
        f" Path({str(marker)!r}).write_text('started')\n time.sleep(10)\n"
        "atomic.os.fsync=stalled\n"
        "print(json.dumps(phase.execute(sys.argv[1],json.load(sys.stdin))))\n"
    )
    report = tmp_path / "report.json"
    report.write_text('{"status":"previous"}')
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="phase deadline"):
        phase.run(
            "write",
            {"path": str(report), "value": {"status": "complete"}},
            0.3,
            script=worker,
        )
    assert marker.exists()
    assert time.monotonic() - started < 2
    assert json.loads(report.read_text()) == {"status": "previous"}


def test_runtime_fingerprint_changes_with_dependency_version(monkeypatch):
    distribution = SimpleNamespace(metadata={"Name": "fixture"}, version="1")
    monkeypatch.setattr(
        runtime.importlib.metadata, "distributions", lambda: [distribution]
    )
    before = runtime.fingerprint()
    distribution.version = "2"
    after = runtime.fingerprint()
    assert before["dependencies"] == [("fixture", "1")]
    assert after["dependencies"] == [("fixture", "2")]
    assert before["python"] == sys.version
    assert before["lock_sha256"]


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "measured", "size": True},
        {"status": "measured", "size": 1.5},
        {"status": "measured", "size": -1},
        {"status": "stepped", "commands": "12", "rows": 8},
        {"status": "stepped", "commands": 12, "rows": 7},
        {"status": "executed", "before": 4, "after": 5, "spaces": 0, "rows": 8},
        {"status": "executed", "before": 4, "after": 1, "spaces": 4, "rows": 8},
        {"status": "executed", "profile": {}, "rows": 8},
        {
            "status": "compared",
            "seed": 0,
            "index": 0,
            "reference": "ref",
            "disagreement": True,
            "counterexample": {},
        },
    ],
)
def test_recomputed_checksums_do_not_validate_bad_measurements(fields):
    identifier = evidence.case_id("test")
    value = {
        "ordinal": 0,
        "rows": 0,
        "case_id": identifier,
        "language": "brainfuck",
        "table_bits": 8,
        **fields,
    }
    value["evidence_sha256"] = evidence.checksum(value)
    with pytest.raises(ValueError, match="invalid"):
        evidence.validate([value], [identifier])


@pytest.mark.medium
def test_saved_minimized_finding_replays_the_executed_discrepancy(tmp_path):
    import shlex
    import subprocess

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    command = shlex.join(
        [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'\\x03')"]
    )
    worker = tmp_path / "scripts/minimized.py"
    worker.parent.mkdir()
    worker.write_text(
        "import argparse,sys,json\nfrom pathlib import Path\n"
        "from dataclasses import replace\n"
        f"sys.path[:0]=[{str(scripts)!r},{str(scripts / 'screens')!r}]\n"
        "import differential as d\nfrom _budget import options,supervise\n"
        "from _screen_evidence import case_id\n"
        "p=argparse.ArgumentParser();options(p);a=p.parse_args()\n"
        "plan={'tables':1,'case_ids':[case_id('brainfuck',0,0)],"
        "'work_bound':1000000,'work_unit':'vm_steps',"
        f"'reference_template':{command!r}}}\n"
        "if supervise(p,a,Path(__file__),plan):\n"
        " spec=replace(d.SPECS['brainfuck'],program=lambda _: '++.',"
        "stdin=lambda *_: '')\n"
        # 2s not .2s: the reference is a fresh interpreter, whose startup
        # exceeds .2s on Windows, which would time it out and empty its output.
        f" r=d.Runner(spec,{command!r},2)\n"
        " r.minimize_calls=3\n r.minimize_seconds=1\n d.campaign(r,1,0)\n"
    )
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(worker), "--budget-seconds", "5", "--report", str(report)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads(report.read_text())
    saved = manifest["findings"][0]
    assert saved["original"]["program"] == "++."
    assert len(saved["minimized"]["program"]) < len("++.")
    assert saved["minimized"]["cause"] == saved["original"]["cause"]
    assert saved["minimization_status"] in {"complete", "call-limit"}
    assert saved["identity"]["runtime"] == manifest["runtime"]
    assert (
        json.loads(Path(saved["path"]).read_text())["minimized"] == saved["minimized"]
    )
    replayed = subprocess.run(
        saved["replay"], capture_output=True, text=True, timeout=20
    )
    assert replayed.returncode == 1, replayed.stdout + replayed.stderr
    observation = next(
        json.loads(line)
        for line in replayed.stdout.splitlines()
        if line.startswith('{"expected_cause"')
    )
    assert observation["observed"]["cause"] == saved["minimized"]["cause"]
    assert observation["observed"]["ref"]["output"] == "Aw==", observation


def test_sharing_rejects_unpublishable_corpus_before_sampling(monkeypatch):
    import importlib

    screen = importlib.import_module("sharing")
    monkeypatch.setattr(screen, "sample", lambda *_: pytest.fail("sampled"))
    with pytest.raises(ValueError, match="corpus exceeds"):
        phase.execute(
            "sharing", {"count": 1000000, "seed": 0, "languages": ["brainfuck"]}
        )
