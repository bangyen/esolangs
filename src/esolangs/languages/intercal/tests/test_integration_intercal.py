"""INTERCAL through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.cli.test_cli import call_main
from tests.support.witness_tables import witnesses


def test_describe_keeps_the_newline_answer_on_one_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The zero answer ``"_\\n"`` was printed raw and split its line."""
    out = call_main(["describe", "INTERCAL"], capsys)
    assert "answer: printed output (_\\n for 0, I for 1)" in out


@pytest.mark.parametrize("width", [1, 40])
def test_intercal_layout_candidates_keep_exact_provenance(width: int) -> None:
    for inputs in range(1, 4):
        for table in witnesses(inputs):
            template = str(esolangs.generate("INTERCAL", table, width=width))
            esolangs.instantiate("INTERCAL", template, [0] * inputs, truth_table=table)
            wrong = table.translate(str.maketrans("01", "10"))
            with pytest.raises(esolangs.TemplateError, match="is not the template"):
                esolangs.instantiate(
                    "INTERCAL", template, [0] * inputs, truth_table=wrong
                )
