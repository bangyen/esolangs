"""Screens price grids by rectangular area."""

from unittest.mock import patch

from scripts.screens._build import sizes


def test_grid_area_changes_candidate_order():
    programs = {"old": "> @\n> @\n> @", "new": ">      @\n>"}
    with patch("scripts.screens._build.describe", return_value={"state_model": "grid"}):
        measured = sizes("fixture", programs.__getitem__, list(programs))
    assert measured == {"old": 9, "new": 16}


def test_generation_refusal_is_retained():
    def refuse(_table):
        raise ValueError("arity refused")

    assert sizes("fixture", refuse, ["01"]) == {"01": None}
