"""Screens price grids by rectangular area."""

from unittest.mock import patch

from scripts.screens import transforms
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


def test_transform_report_reuses_builds_and_retains_reorder_metrics(capsys):
    lengths = {"00001111": 6, "00110011": 4, "01010101": 2}
    calls = []

    def build(table):
        calls.append(table)
        if table not in lengths:
            raise ValueError("fixture refusal")
        return "+" * lengths[table]

    with patch.object(transforms, "generators", return_value=[("brainfuck", build)]):
        transforms.main()
    assert len(calls) == len(set(calls)) == 272
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == [
        "language",
        "order%",
        "impr",
        "outneg%",
        "inpol%",
        "npn%",
        "ignored",
        "sec",
    ]
    assert lines[1].split()[1:3] == ["50.0", "2"]


def test_transform_report_omits_wholly_refused_generators():
    def refuse(_table):
        raise ValueError("fixture refusal")

    assert transforms.screen("brainfuck", refuse) is None
