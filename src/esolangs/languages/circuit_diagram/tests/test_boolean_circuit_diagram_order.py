"""Executed fixed-order folds, including expander cofactor incidence."""

import pytest

from esolangs.generation.helpers import grid_area, permute_truth_table
from esolangs.languages.circuit_diagram.generator import (
    _circuit_diagram_model,
    _dag,
    circuit_diagram,
)
from esolangs.languages.circuit_diagram.generator.compete import (
    select_competing_model,
)
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _best_linear_fold,
    _execute,
)


def _margulis_cofactors(log_side):
    """Encode Margulis neighbors as pairs of distinct, essential cofactors."""
    # Hoory--Linial--Wigderson, Construction 8.1:
    # https://www.math.ias.edu/~avi/PUBLICATIONS/MYPAPERS/HLW06/hlw06.pdf
    side = 1 << log_side
    bits = 2 * log_side
    tail = (2 * bits + 1).bit_length()
    width = 1 << tail
    labels = [
        f"{vertex:0{bits}b}" + "0" * (width - bits - 1) + "1"
        for vertex in range(side * side)
    ]
    chunks = []
    for x in range(side):
        for y in range(side):
            neighbors = (
                ((x + 2 * y) % side, y),
                ((x - 2 * y) % side, y),
                ((x + 2 * y + 1) % side, y),
                ((x - 2 * y - 1) % side, y),
                (x, (y + 2 * x) % side),
                (x, (y - 2 * x) % side),
                (x, (y + 2 * x + 1) % side),
                (x, (y - 2 * x - 1) % side),
            )
            chunks.extend(
                labels[x * side + y] + labels[a * side + b] for a, b in neighbors
            )
    return "".join(chunks)


@pytest.mark.medium
def test_every_three_input_function_with_permuted_physical_ports() -> None:
    for value in range(256):
        table = f"{value:08b}"
        rotated = permute_truth_table(table, (2, 0, 1))
        model = _circuit_diagram_model(rotated, None, input_order=[2, 0, 1])
        _execute(table, model.render())


@pytest.mark.medium
@pytest.mark.parametrize("log_side", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
def test_named_orders_avoid_literal_expander_routing_within_existing_bounds(
    log_side,
) -> None:
    table = _margulis_cofactors(log_side)
    n = len(table).bit_length() - 1
    if log_side >= 2:
        assert len(_dag(table, n)[0]) ** 2 > 4 * len(table)
    code = circuit_diagram(table)
    # The contract is the fallback cap, not a fold win: the shipped grid is
    # never larger than the pool / bank fallback the generator renders.
    fallback = select_competing_model(table, n).render()
    assert grid_area(code) <= grid_area(fallback)
    rows = None if log_side == 1 else {i * (len(table) - 1) // 64 for i in range(65)}
    _execute(table, code, rows)


@pytest.mark.medium
def test_projected_fold_preserves_original_read_order() -> None:
    core = _margulis_cofactors(1)
    kept = [0, 2, 3, 4, 6, 7, 8, 10, 11]
    table = "".join(
        core[sum(((row >> (11 - at)) & 1) << (8 - i) for i, at in enumerate(kept))]
        for row in range(4096)
    )
    model = _best_linear_fold(table, 12)
    assert circuit_diagram(table) == model.render()
    _execute(table, model.render())


@pytest.mark.parametrize(
    ("order", "ports"), [([0, 1], 3), ([0, 0, 1], 3), ([0, 1, 3], 3)]
)
def test_invalid_fold_ports_abort(order, ports) -> None:
    with pytest.raises(ValueError, match="distinct original ports"):
        _circuit_diagram_model("00010111", None, input_order=order, port_inputs=ports)
