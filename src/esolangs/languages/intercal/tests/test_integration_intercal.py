"""INTERCAL through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from tests.support.cli_support import call_main, run_cli
from tests.support.witness_tables import witnesses


def test_describe_keeps_the_newline_answer_on_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The zero answer ``"_\\n"`` was printed raw and split its line."""
    out = call_main(["describe", "INTERCAL"], capsys)
    assert "answer: printed output (_\\n for 0, I for 1)" in out


@pytest.mark.medium
def test_cli_feeds_stdin_to_handwritten_source(tmp_path: Path) -> None:
    path = tmp_path / "program.i"
    path.write_text("PLEASE WRITE IN .1\nDO READ OUT .1\nDO GIVE UP")
    result = run_cli("run", "INTERCAL", str(path), stdin="FOUR TWO\n")
    assert (result.returncode, result.stdout, result.stderr) == (0, "XLII\n", "")


@pytest.mark.parametrize("width", [1, 40])
def test_intercal_layout_candidates_keep_exact_provenance(width: int) -> None:
    for inputs in range(1, 4):
        for table in witnesses(inputs):
            template = esolangs.generate("INTERCAL", table, width=width)
            esolangs.Language("INTERCAL").instantiate(
                template, [0] * inputs, truth_table=table
            )
            wrong = table.translate(str.maketrans("01", "10"))
            with pytest.raises(esolangs.TemplateError, match="is not the template"):
                esolangs.Language("INTERCAL").instantiate(
                    template, [0] * inputs, truth_table=wrong
                )
