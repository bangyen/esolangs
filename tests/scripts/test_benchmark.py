"""Tests for the public benchmark command."""

import esolangs
from scripts.benchmark import measure


def test_measure_reports_deterministic_costs() -> None:
    result = measure("brainfuck", "0110", repeat=1, row=1, step_cap=10_000)
    assert result["language"] == "brainfuck"
    assert result["inputs"] == 2
    assert result["source_units"] > 0
    assert result["commands"] is not None
    assert result["generation_ns_best"] >= 0


def test_measure_counts_commands_for_a_parameterized_language() -> None:
    """A parameterized language embeds its inputs and reads no stdin.

    ``encode_inputs`` raises for one rather than returning an empty string,
    so calling it before the parameterized branch made every parameterized
    language raise ``ArgumentError``.  Only brainfuck was ever measured, so
    the break went unseen until a sweep ran the whole registry.
    """
    name = next(
        lang
        for lang in esolangs.list_languages()
        if esolangs.describe(lang)["parameterized"]
    )
    result = measure(name, "0110", repeat=1, row=3, step_cap=10_000)
    assert result["source_units"] > 0
