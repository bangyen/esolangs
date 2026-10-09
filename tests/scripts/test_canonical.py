"""Canonical screens retain execution failures and meaningful positive controls."""

from unittest.mock import patch

import pytest

from scripts.screens import canonical


def test_positive_controls_execute_and_expose_the_known_gaps() -> None:
    assert canonical.controls() == {
        "constant_characters_saved": 8,
        "shared_grid_cells_saved": 770,
        "width_gap_grid_cells": 10_095,
    }


def test_execution_errors_are_not_generation_refusals() -> None:
    with (
        patch.object(canonical, "paths", return_value={"default": {}}),
        patch.object(canonical, "corpus", return_value={"zero": "00"}),
        patch.object(canonical, "execute", side_effect=ValueError("bad output")),
        pytest.raises(ValueError, match="bad output"),
    ):
        canonical.audit("brainfuck", 1, all_rows=False)


def test_generation_refusals_are_retained() -> None:
    with (
        patch.object(canonical, "paths", return_value={"default": {}}),
        patch.object(canonical, "corpus", return_value={"zero": "00"}),
        patch.object(
            canonical.esolangs, "generate", side_effect=ValueError("arity cap")
        ),
    ):
        records = canonical.audit("brainfuck", 1, all_rows=False)
    assert records[0]["status"] == "refused"
    assert records[0]["reason"] == "arity cap"


def test_text_grid_size_charges_blank_padding() -> None:
    from scripts.screens import paths

    program = ">   @\n>"
    with (
        patch.object(paths.esolangs, "generate", return_value=program),
        patch("_build.describe", return_value={"state_model": "grid"}),
    ):
        assert paths._size("fixture", "01", {}) == 10  # noqa: SLF001
        assert canonical.size("fixture", program) == 10


def test_text_size_counts_characters() -> None:
    with patch("_build.describe", return_value={"state_model": "tape"}):
        assert canonical.size("fixture", "+\n.") == 3
