"""Public builds of repeated suffix classes, executed."""

import pytest

from esolangs.languages.circuit_diagram.generator import (
    bundled_banks,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense


def _three_classes(n):
    tail = 7 if n % 2 else 8
    atoms = [dense(tail, f"class:{i}".encode()) for i in range(3)]
    selector = dense(n - tail, b"class-selector")
    return "".join(
        atoms[(2 * int(bit) + row % 2) % 3] for row, bit in enumerate(selector)
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [9, 10])
def test_repeated_classes_execute_every_row(n) -> None:
    table = _three_classes(n)
    _execute(table, circuit_diagram(table))


@pytest.mark.medium
def test_public_abba_class_bank_executes_every_row() -> None:
    a, b = dense(8, b"bank-a"), dense(8, b"bank-b")
    table = a + b + b + a
    code = circuit_diagram(table)
    lines = code.splitlines()
    assert len(lines) * max(map(len, lines)) == 453_285
    _execute(table, code)


@pytest.mark.medium
def test_explicit_width_never_builds_class_masks(monkeypatch) -> None:
    def unexpected(*_args, **_kwargs):
        pytest.fail("class masks must not run in the width-constrained fold")

    monkeypatch.setattr(bundled_banks, "bundled_class_bank_candidate", unexpected)
    table = _three_classes(9)
    _execute(table, circuit_diagram(table, width=80), (0, len(table) - 1))
