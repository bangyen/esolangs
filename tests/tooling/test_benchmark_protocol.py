"""Reject malformed worker records without losing legitimate row deadlines."""

import json
import sys

import pytest

from scripts.benchmark import MAX_RECORD_CHARS, Worker


@pytest.mark.parametrize(
    "records",
    [
        [{"phase": "execution", "index": 0}],
        [{"phase": "generation"}, {"phase": "generation"}],
        [
            {"phase": "generation"},
            {"phase": "execution", "index": 0},
            {"phase": "execution", "index": 0},
        ],
        [{"phase": "generation"}, {"phase": "execution", "index": 1}],
        [{"result": {}}],
        [[]],
        [{"error": {"message": "bad"}}],
    ],
)
def test_invalid_protocol_reaps_worker(records) -> None:
    command = (
        "import sys,time; "
        + "; ".join(f"print({json.dumps(record)!r}, flush=True)" for record in records)
        + "; time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError):
        worker.measure({"timeout": 1, "table": "01", "all_rows": True}, {}, 1)
    assert worker.process is None


def test_oversized_record_is_bounded() -> None:
    command = (
        f"import sys,time; sys.stdout.write('x'*{MAX_RECORD_CHARS + 1}); "
        "sys.stdout.flush(); time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError, match="exceeds limit"):
        worker.measure({"timeout": 1}, {}, 2)
    assert worker.process is None


def test_valid_multiline_protocol_runs_all_rows() -> None:
    from scripts import benchmark

    record = benchmark.measure(
        "Brainfuck", "01", repeat=1, row=0, step_cap=100000, all_rows=True
    )
    assert [entry["row"] for entry in record["executions"]] == [0, 1]
    assert all(
        entry["actual_answer"] == entry["expected_answer"]
        for entry in record["executions"]
    )
    record["executions"][0] |= {"matches": False, "actual_answer": "1"}
    record["peak_stack_items"] = 3
    head, wrong, peak, tail = benchmark.summary(record).splitlines()
    assert head.startswith(
        f"{record['language']} 01: 1/2 rows correct, {record['source_units']} "
    )
    assert head.endswith(f"worst {record['worst_row_commands']} commands")
    assert wrong == "  row 0: answered '1', expected '0', halted"
    assert peak == "  peak stack items 3"
    assert tail == "--json for the full record"


def test_total_deadline_cannot_be_extended_by_valid_row_phases() -> None:
    import time

    import esolangs

    command = (
        'import time; print(\'{"phase":"generation"}\',flush=True); '
        'print(\'{"phase":"execution","index":0}\',flush=True); '
        "time.sleep(.2); "
        'print(\'{"phase":"execution","index":1}\',flush=True); '
        "time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    started = time.monotonic()
    with pytest.raises(esolangs.ExecutionTimeoutError, match="total work deadline"):
        worker.measure({"timeout": 5, "sample_rows": [0, 1]}, {}, 5, total_timeout=0.3)
    assert time.monotonic() - started < 2
    assert worker.process is None


@pytest.mark.medium
@pytest.mark.parametrize("directory", [".", "notes/ci"])
def test_timing_journal_is_scratch_but_source_edits_change_identity(
    tmp_path, monkeypatch, directory
) -> None:
    import subprocess
    from types import SimpleNamespace

    from scripts import benchmark
    from scripts.ci.shard import Recorder

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    (tmp_path / ".gitignore").write_text("notes/\n")
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    git("add", ".")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-qm",
        "fixture",
    )
    monkeypatch.setattr(benchmark, "__file__", str(tmp_path / "scripts/benchmark.py"))
    recorder = Recorder(tmp_path / directory / "test-durations.json")
    before = benchmark.source_identity()
    recorder.pytest_runtest_logreport(
        SimpleNamespace(
            when="teardown",
            nodeid="test_example.py::test_value",
            duration=0.01,
            failed=False,
        )
    )
    during = benchmark.source_identity()
    if directory == ".":
        assert before["untracked_sha256"] != during["untracked_sha256"]
    else:
        assert during == before
        recorder.pytest_sessionfinish(0)
        assert benchmark.source_identity() == before
    source.write_text("value = 2\n")
    assert (
        benchmark.source_identity()["tracked_diff_sha256"]
        != before["tracked_diff_sha256"]
    )
