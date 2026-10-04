"""Timing alerts need comparable cases and two sustained measurements."""

import json

import pytest

from scripts.report_generator_timings import main, report


def record(ns, *, language="brainfuck", table="0110"):
    return {"language": language, "truth_table": table, "generation_ns_best": ns}


BASE = [record(20_000_000)]
SLOW = [record(40_000_000)]


def test_positive_control_reports_two_slow_runs():
    assert "Sustained slowdowns" in report(SLOW, [BASE, SLOW])
    assert "2.00x" in report(SLOW, [BASE, SLOW])


@pytest.mark.parametrize(
    ("current", "history"), [(SLOW, [BASE, BASE]), (BASE, [BASE, SLOW])]
)
def test_one_noisy_run_does_not_alert(current, history):
    assert "No sustained slowdowns" in report(current, history)


def test_noise_floor_and_changed_cases_do_not_alert():
    assert "No sustained slowdowns" in report(
        [record(900)], [[record(100)], [record(900)]]
    )
    assert "0 comparable cases" in report(
        [record(40_000_000, table="1001")], [BASE, SLOW]
    )


def test_history_and_summary_round_trip(tmp_path):
    current = tmp_path / "current.json"
    history = tmp_path / "history.json"
    summary = tmp_path / "summary.md"
    for sweep in (BASE, SLOW, SLOW):
        current.write_text(json.dumps(sweep))
        assert (
            main([str(current), "--history", str(history), "--summary", str(summary)])
            == 0
        )
    assert json.loads(history.read_text()) == [SLOW, SLOW]
    assert "Sustained slowdowns" in summary.read_text()


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_bad_timing_data_is_refused(value):
    with pytest.raises(ValueError, match="invalid generation timing"):
        report([record(value)], [])


def test_duplicate_records_are_refused():
    with pytest.raises(ValueError, match="duplicate timing"):
        report([*BASE, *BASE], [])
