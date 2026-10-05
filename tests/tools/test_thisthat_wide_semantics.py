"""Wide emitted programs checked against independently represented cycles."""

import pytest

from esolangs.tools.thisthat import thisthat
from tests.interpreters.thisthat_cases import tables
from tests.interpreters.thisthat_observer import check


def cases():
    for n in range(4, 11):
        for family, table in tables(n).items():
            groups = {}
            for width in (None, 1, 13, 100):
                groups.setdefault(thisthat(table, width), []).append(width)
            for group, source in enumerate(groups):
                for start in range(0, len(table), 4):
                    yield pytest.param(
                        table, source, start, id=f"{n}-{family}-{group}-{start}"
                    )


@pytest.mark.medium
@pytest.mark.parametrize(("table", "source", "start"), list(cases()))
def test_wide_cycles(table, source, start):
    n = len(table).bit_length() - 1
    for row in range(start, min(start + 4, len(table))):
        result = check(source.splitlines(), format(row, f"0{n}b"))
        assert result["status"] == "halted"
        assert result["output"] == table[row]
        assert result["reads"] == n
