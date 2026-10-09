"""Candidate grids are priced by rectangular area."""

from contextlib import nullcontext
from unittest.mock import patch

from scripts.screens import candidate


def test_shorter_text_with_larger_grid_is_reported_as_growth(capsys) -> None:
    old, new = "> @\n> @\n> @", ">      @\n>"
    with (
        patch.object(candidate, "resolve", side_effect=lambda name: name),
        patch.object(candidate, "_load", return_value=lambda _table: new),
        patch.object(candidate, "_tables", return_value=[("random", "00000000")]),
        patch.object(candidate, "_patched", return_value=nullcontext()),
        patch.object(candidate, "_worst", return_value=(0, 1)),
        patch.object(candidate.esolangs, "generate", side_effect=[old, new]),
        patch("_build.describe", return_value={"state_model": "grid"}),
    ):
        assert candidate.main(["fixture", "fixture.py:build", "--n", "3", "3"]) == 0
    row = capsys.readouterr().out.splitlines()[-1].split()
    assert row[4] == "1"
    assert row[5] == "1.778/1.778"
