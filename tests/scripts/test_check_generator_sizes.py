"""Tests for the emitted-size and step-count baseline gate."""

import hashlib
import json
from typing import Any

import pytest

import esolangs
from checks.check_generator_sizes import (
    BASELINE,
    BOUNDARIES,
    SCHEMA,
    TABLES,
    baseline,
    boundary_tables,
    differences,
)
from scripts import benchmark as b
from tests.reference import REFERENCE

RECORD = {
    "language": REFERENCE,
    "truth_table": TABLES[0],
    "source_units": 205,
    "commands": 179,
    "generation_ns_best": 1234,
    "generation_ns_median": 5678,
}


def _measured() -> dict[str, Any]:
    return baseline([dict(RECORD)])


class TestProjection:
    """A sweep is reduced to exactly the fields that repeat run to run."""

    def test_timings_are_dropped(self) -> None:
        rows = _measured()["records"][REFERENCE][TABLES[0]]
        assert rows == {"source_units": 205, "commands": 179}

    def test_the_header_carries_the_corpus(self) -> None:
        measured = _measured()
        assert measured["schema"] == SCHEMA
        assert measured["tables"] == list(TABLES)


class TestDifferences:
    """Every way the measurement can disagree with the baseline is reported."""

    def test_an_identical_baseline_is_silent(self) -> None:
        assert differences(_measured(), _measured()) == []

    def test_a_size_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "source_units": 206}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] source_units: 205 -> 206"
        ]

    def test_a_step_count_change_is_reported(self) -> None:
        changed = baseline([{**RECORD, "commands": 180}])
        assert differences(_measured(), changed) == [
            f"brainfuck [{TABLES[0]}] commands: 179 -> 180"
        ]

    def test_a_win_fails_too(self) -> None:
        """A smaller program is still a diff the baseline has to record."""
        smaller = baseline([{**RECORD, "source_units": 12}])
        assert differences(_measured(), smaller) != []

    def test_a_new_language_is_reported(self) -> None:
        added = baseline([dict(RECORD), {**RECORD, "language": "Newcomer"}])
        assert differences(_measured(), added) == [
            "Newcomer: not in the baseline (new language?)"
        ]

    def test_a_dropped_language_is_reported(self) -> None:
        empty = baseline([])
        assert differences(_measured(), empty) == [
            "brainfuck: in the baseline but not in the registry"
        ]

    def test_a_stale_schema_short_circuits(self) -> None:
        stale = {**_measured(), "schema": SCHEMA - 1}
        assert differences(stale, _measured()) == [
            f"baseline schema {SCHEMA - 1!r}, expected {SCHEMA}"
        ]

    def test_a_changed_corpus_short_circuits(self) -> None:
        """Comparing across corpora would read as a whole-registry change."""
        stale = {**_measured(), "tables": ["0110"]}
        lines = differences(stale, _measured())
        assert len(lines) == 1
        assert lines[0].startswith("baseline tables")


class TestCommittedBaseline:
    """The file in the tree is the corpus this gate claims to cover."""

    def test_it_covers_every_language_and_table(self) -> None:
        recorded = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert recorded["schema"] == SCHEMA
        assert recorded["tables"] == list(TABLES)
        assert recorded["records"]
        for name, rows in recorded["records"].items():
            assert sorted(rows) == sorted((*TABLES, *boundary_tables(name))), name
            for table, fields in rows.items():
                assert fields["source_units"] > 0, (name, table)


def test_sweep_refuses_incorrect_or_undecided_rows(monkeypatch) -> None:
    import pytest

    from checks import check_generator_sizes as sizes

    monkeypatch.setattr(sizes.esolangs, "list_languages", lambda: [REFERENCE])
    monkeypatch.setattr(sizes, "BOUNDARIES", {})
    for matches in (False, None):
        monkeypatch.setattr(
            sizes,
            "measure",
            lambda *_args, matches=matches, **_kwargs: {
                **RECORD,
                "matches": matches,
                "execution_status": "step_cap",
                "expected_answer": "1",
                "actual_answer": None,
            },
        )
        with pytest.raises(ValueError, match="expected 1, got None"):
            sizes.sweep()


def test_boundary_rows_are_pinned_and_corpus_drift_fails():
    name = next(iter(BOUNDARIES))
    table = boundary_tables(name)[0]
    measured = baseline(
        [
            {
                **RECORD,
                "language": name,
                "truth_table": table,
                "executions": [{"row": 0, "commands": 2}, {"row": 1, "commands": 3}],
            }
        ]
    )
    assert measured["records"][name][table]["commands_by_row"] == {
        "0": 2,
        "1": 3,
    }
    stale = {**measured, "boundaries": {}}
    assert differences(stale, measured) == ["baseline boundary corpus changed"]


def test_sweep_checks_and_pins_every_small_table_row(monkeypatch):
    from checks import check_generator_sizes as sizes

    monkeypatch.setattr(sizes.esolangs, "list_languages", lambda: [REFERENCE])
    monkeypatch.setattr(sizes, "BOUNDARIES", {})
    records = sizes.sweep()
    pinned = sizes.baseline(records)["records"][REFERENCE]
    assert len(records) == 8
    for record in records:
        table = record["truth_table"]
        executions = record["executions"]
        assert [row["row"] for row in executions] == list(range(len(table)))
        assert all(row["matches"] is True for row in executions)
        assert len(pinned[table]["commands_by_row"]) == len(table)


def test_executed_artifact_and_provenance():
    r = b.measure("Brainfuck", "01", repeat=1, row=1, step_cap=10000, all_rows=True)
    p = esolangs.generate("Brainfuck", "01")
    assert all(row["matches"] for row in r["executions"])
    assert r["schema"] == 6
    assert r["provenance"]["generated_artifact_sha256"] == b.artifact_hash(p)
    assert all(row["artifact_sha256"] == b.artifact_hash(p) for row in r["executions"])
    assert len(r["provenance"]["commit"]) == 40
    assert isinstance(r["provenance"]["dirty"], bool)
    assert b.artifact_hash("é") == hashlib.sha256(b"text\0" + "é".encode()).hexdigest()
    pixel = (0, 0, 0)
    assert b.artifact_hash(esolangs.Raster(((pixel, pixel),))) != b.artifact_hash(
        esolangs.Raster(((pixel,), (pixel,)))
    )


def test_checkout_change_invalidates_benchmark(monkeypatch):
    identities = iter([{"commit": "before"}, {"commit": "after"}])
    monkeypatch.setattr(b, "source_identity", lambda: next(identities))
    with pytest.raises(RuntimeError, match="checkout changed"):
        b.measure("Brainfuck", "01", repeat=1, row=1, step_cap=100)


@pytest.mark.parametrize("phase", ["generation", "execution", "startup"])
def test_benchmark_deadline_reaps_workers_with_positive_control(
    tmp_path, monkeypatch, phase
):
    import sys
    import time
    from pathlib import Path

    factory = b.Worker
    marker = tmp_path / "worker"
    child = f"""
import time
from pathlib import Path
p = Path({str(marker)!r})
while True:
    p.write_text(str(time.monotonic()))
    time.sleep(0.01)
"""
    setup = f"""
import sys, subprocess, time
sys.path.insert(0, {str(Path(__file__).resolve().parents[2] / "scripts")!r})
import benchmark
import _benchmark_worker as worker
def hang(*args, **kwargs):
    subprocess.Popen([sys.executable, '-c', {child!r}])
    time.sleep(30)
"""
    setup += (
        "benchmark.esolangs.generate = hang\n"
        if phase == "generation"
        else "benchmark._execute = hang\n"
    )
    setup += (
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(30)"
        if phase == "startup"
        else "worker._worker_main()"
    )
    monkeypatch.setattr(b, "Worker", lambda: factory([sys.executable, "-c", setup]))
    start = time.monotonic()
    expected = "execution" if phase == "execution" else "generation"
    with pytest.raises(esolangs.ExecutionTimeoutError, match=f"{expected} deadline"):
        b.measure(
            "Brainfuck",
            "0" * 131072 if phase == "startup" else "01",
            repeat=1,
            row=1,
            step_cap=10000,
            timeout=1,
            generation_timeout=1,
        )
    # The worker sleeps 30s, so the 1s deadline ending the call well before
    # that is the fact under test.  The bound stays loose because an xdist
    # sibling or a shared CI runner can deschedule this process for seconds;
    # at 4s it failed a clean run under load.
    assert time.monotonic() - start < 15
    before = marker.read_text()
    time.sleep(0.1)
    assert marker.read_text() == before
    monkeypatch.setattr(b, "Worker", factory)
    record = b.measure(
        "Brainfuck", "01", repeat=1, row=1, step_cap=10000, all_rows=True
    )
    assert all(row["matches"] for row in record["executions"])
