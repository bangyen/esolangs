"""Tests for the public benchmark command."""

from scripts.benchmark import measure


def test_measure_reports_deterministic_costs() -> None:
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["language"] == "brainfuck"
    assert result["inputs"] == 2
    assert result["source_units"] > 0
    assert result["commands"] is not None
    assert result["generation_ns_best"] >= 0
