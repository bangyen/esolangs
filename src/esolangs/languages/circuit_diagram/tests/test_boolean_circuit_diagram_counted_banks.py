"""Counted mask gates admit sparse classes beyond the pessimistic bound."""

from itertools import combinations, islice

import pytest

from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)


def _sparse_classes():
    pairs = list(islice(combinations(range(128), 2), 202))
    atoms = ["".join(str(int(row in pair)) for row in range(128)) for pair in pairs]
    return "".join(atoms[row % 202] for row in range(256)), pairs


@pytest.mark.slow
def test_counted_mask_banks_execute_class_and_prefix_boundaries() -> None:
    table, pairs = _sparse_classes()
    old_bound = 202 * (211 + 114 + 2) - 1
    assert old_bound > 2 * len(table) + 8 * 15 + 111
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 3_961_697
    rows = sorted(
        {
            0,
            len(table) - 1,
            *(
                (prefix << 7) + row
                for prefix in (0, 1, 100, 101, 127, 128, 201, 202, 255)
                for index in (prefix % len(pairs),)
                for row in (
                    *pairs[index],
                    next(row for row in range(128) if row not in pairs[index]),
                )
            ),
        }
    )
    assert _execute(table, code, rows) == 30
