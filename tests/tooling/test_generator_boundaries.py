"""Every row executes for the benchmarked construction controls."""

import pytest

from checks.check_generator_sizes import BOUNDARIES, STEP_CAP
from scripts.benchmark import measure


@pytest.mark.slow
@pytest.mark.parametrize(
    ("language", "table"),
    [
        pytest.param(
            name,
            witness.table(),
            id=f"{name}-{label}-n{witness.arity}-{witness.name}",
        )
        for name, cases in BOUNDARIES.items()
        for label, witnesses in cases.items()
        for witness in witnesses
    ],
)
def test_boundary_program_answers_every_row(language, table) -> None:
    record = measure(
        language, table, repeat=1, row=len(table) - 1, step_cap=STEP_CAP, all_rows=True
    )
    assert all(row["matches"] is True for row in record["executions"])
    assert all(row["commands"] is not None for row in record["executions"])
