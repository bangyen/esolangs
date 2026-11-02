"""Timing reports refuse unlike evidence and distinguish repeated increases."""

from copy import deepcopy

import pytest

from scripts.ci.generator_timings import compare, snapshot


def _records(value=100):
    return [
        {
            "language": "test",
            "truth_table": "01",
            "generation_ns_median": value,
            "provenance": dict.fromkeys(
                ("python", "platform", "machine", "harness"), "same"
            ),
            "matches": True,
            "schema": 6,
            "track_store": False,
            "step_cap": 100,
            "timeout": 30,
        }
    ]


def test_matching_cohorts_regressions_and_invalid_evidence():
    baseline = snapshot(_records())
    slow = snapshot(_records(130))
    report, history = compare(slow, [baseline, baseline])
    assert "candidate" in report
    report, history = compare(slow, history)
    assert "persistent" in report
    assert "30.0%" in report
    assert "No generation" in compare(baseline, history)[0]
    assert len(compare(baseline, [baseline] * 20)[1]) == 8
    for field in ("environment", "controls"):
        _changed_cohort_starts_over(field)
    for value in (0, -1, True, float("nan"), float("inf")):
        _invalid_measurements(value)
    _rejects_duplicate_failed_and_mixed_evidence()


def test_malformed_history_entries_are_dropped_not_crashed_on():
    baseline = snapshot(_records())
    slow = snapshot(_records(130))
    # A restored history holding a raw measurements list (the 2026-11-02
    # weekly crash) or other non-snapshot entries must not crash compare.
    report, history = compare(slow, [[{"language": "test"}], "junk", baseline])
    assert "candidate" in report
    assert history == [baseline, slow]
    report, _ = compare(slow, [[{"language": "test"}]])
    assert "first reference" in report


def _changed_cohort_starts_over(field):
    old = snapshot(_records())
    new = deepcopy(old)
    new[field] = {}
    report, history = compare(new, [old])
    assert "first reference" in report
    assert history == [new]


def _invalid_measurements(value):
    with pytest.raises(ValueError, match="invalid timing"):
        snapshot(_records(value))


def _rejects_duplicate_failed_and_mixed_evidence():
    rows = _records()
    with pytest.raises(ValueError, match="duplicate"):
        snapshot(rows * 2)
    rows[0]["matches"] = False
    with pytest.raises(ValueError, match="unsuccessful"):
        snapshot(rows)
    rows = _records() + _records()
    rows[1]["provenance"]["python"] = "different"
    with pytest.raises(ValueError, match="mixed"):
        snapshot(rows)
    with pytest.raises(ValueError, match="empty"):
        snapshot([])
