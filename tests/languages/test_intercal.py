"""INTERCAL through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.witness_tables import witnesses


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
