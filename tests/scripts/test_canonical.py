"""Canonical screens retain execution failures and meaningful positive controls."""

from unittest.mock import patch

import pytest

from scripts.screens import canonical


def test_positive_controls_execute_and_expose_the_known_gaps() -> None:
    assert canonical.controls() == {
        "constant_characters_saved": 8,
        "shared_grid_cells_saved": 1265,
        "width_gap_grid_cells": 10_590,
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


def test_resume_accepts_matching_execution_and_retries_timeouts(tmp_path):
    import json

    checkout = {"commit": "fixture"}
    with (
        patch.object(canonical, "paths", return_value={"default": {}}),
        patch.object(canonical, "corpus", return_value={"zero": "00"}),
    ):
        record = canonical.audit("brainfuck", 1, all_rows=True, checkout=checkout)[0]
        path = tmp_path / "resume.jsonl"
        path.write_text(json.dumps(record) + "\n")
        assert canonical.resume(path, checkout, all_rows=True) == {
            ("brainfuck", 1, "default", "zero")
        }
        record["status"] = "timeout"
        path.write_text(json.dumps(record) + "\n")
        assert not canonical.resume(path, checkout, all_rows=True)


@pytest.mark.parametrize("drift", ["source", "settings", "corpus", "legacy"])
def test_resume_rejects_changed_provenance(tmp_path, drift):
    import json

    checkout = {"commit": "fixture"}
    record = {
        "schema": 1,
        "language": "brainfuck",
        "n": 1,
        "path": "default",
        "piece": "zero",
        "status": "executed",
        "rows": 2,
        "identity": canonical.evidence_identity(checkout, "00", {}),
    }
    choices, tables = {"default": {}}, {"zero": "00"}
    if drift == "source":
        checkout = {"commit": "changed"}
    elif drift == "settings":
        choices["default"] = {"width": 8}
    elif drift == "corpus":
        tables["zero"] = "01"
    else:
        del record["identity"]
    path = tmp_path / "resume.jsonl"
    path.write_text(json.dumps(record) + "\n")
    with (
        patch.object(canonical, "paths", return_value=choices),
        patch.object(canonical, "corpus", return_value=tables),
        pytest.raises(ValueError, match="canonical resume"),
    ):
        canonical.resume(path, checkout, all_rows=False)
