"""Every emitted construction compared cycle by cycle with an independent model."""

import pytest

from tests.interpreters.thisthat_cases import legacy_tables, sources
from tests.interpreters.thisthat_observer import check


def cases():
    tables = [
        (n, f"small:{value}", format(value, f"0{1 << n}b"))
        for n in range(1, 4)
        for value in range(1 << (1 << n))
    ] + list(legacy_tables())
    for n, label, table in tables:
        for group, (source, _modes) in enumerate(sources(table).items()):
            for start in range(0, len(table), 4):
                yield pytest.param(
                    table, source, start, id=f"{n}-{label}-{group}-{start}"
                )


@pytest.mark.medium
@pytest.mark.parametrize(("table", "source", "start"), list(cases()))
def test_emitted_cycles(table, source, start):
    n = len(table).bit_length() - 1
    for row in range(start, min(start + 4, len(table))):
        result = check(source.splitlines(), format(row, f"0{n}b"))
        assert result["status"] == "halted"
        assert result["output"] == table[row]
        assert result["reads"] == n
