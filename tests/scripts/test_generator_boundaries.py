"""Every row executes on both sides of the named layout switches."""

import pytest

from checks.check_generator_sizes import BOUNDARIES, STEP_CAP, boundary_tables
from scripts.benchmark import measure


@pytest.mark.slow
@pytest.mark.parametrize(
    ("language", "table"),
    [(name, table) for name in BOUNDARIES for table in boundary_tables(name)],
)
def test_boundary_program_answers_every_row(language, table):
    record = measure(
        language, table, repeat=1, row=len(table) - 1, step_cap=STEP_CAP, all_rows=True
    )
    assert all(row["matches"] is True for row in record["executions"])
    assert all(row["commands"] is not None for row in record["executions"])
