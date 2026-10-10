"""Reject malformed worker records without losing legitimate row deadlines."""

import json
import sys

import pytest

from scripts._benchmark_client import MAX_RECORD_CHARS, Worker


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
def test_invalid_protocol_reaps_worker(records):
    command = (
        "import sys,time; "
        + "; ".join(f"print({json.dumps(record)!r}, flush=True)" for record in records)
        + "; time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError):
        worker.measure({"timeout": 1, "table": "01", "all_rows": True}, {}, 1)
    assert worker.process is None


def test_oversized_record_is_bounded():
    command = (
        f"import sys,time; sys.stdout.write('x'*{MAX_RECORD_CHARS + 1}); "
        "sys.stdout.flush(); time.sleep(10)"
    )
    worker = Worker([sys.executable, "-c", command])
    with pytest.raises(RuntimeError, match="exceeds limit"):
        worker.measure({"timeout": 1}, {}, 2)
    assert worker.process is None


def test_valid_multiline_protocol_runs_all_rows():
    from scripts import benchmark

    record = benchmark.measure(
        "Brainfuck", "01", repeat=1, row=0, step_cap=100000, all_rows=True
    )
    assert [entry["row"] for entry in record["executions"]] == [0, 1]
    assert all(
        entry["actual_answer"] == entry["expected_answer"]
        for entry in record["executions"]
    )


def test_total_deadline_cannot_be_extended_by_valid_row_phases():
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
