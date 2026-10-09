"""Candidate grids are priced by rectangular area."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest

from scripts.screens import candidate
from scripts.screens.candidate import _worst


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


@pytest.mark.parametrize(
    "options",
    [
        ["--rows", "0"],
        ["--count", "0"],
        ["--rows", "-1"],
        ["--n", "0", "1"],
        ["--n", "2", "1"],
    ],
)
def test_empty_screen_rejected_before_loading(options):
    with (
        patch.object(candidate, "_load", side_effect=AssertionError("loaded")),
        pytest.raises(SystemExit) as caught,
    ):
        candidate.main(["brainfuck", "unused.py:build", *options])
    assert caught.value.code == 2


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_invalid_timeout_rejected_before_loading(timeout):
    with (
        patch.object(candidate, "_load", side_effect=AssertionError("loaded")),
        pytest.raises(SystemExit) as caught,
    ):
        candidate.main(["brainfuck", "unused.py:build", "--timeout", timeout])
    assert caught.value.code == 2


@pytest.mark.medium
def test_unsupported_stepping_candidate_is_bounded():
    assert _worst("a_painter_ant", "nn$", "00", [0], 0.02) == (1, 0)
    assert _worst("a_painter_ant", "N$", "00", [1], 0.5) == (0, 0)
