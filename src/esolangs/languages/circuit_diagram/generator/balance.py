"""Circuit Diagram affine chains and exact width transitions."""

from collections.abc import Callable
from functools import cache, partial
from math import isqrt

from esolangs.generation.algebraic import AffineForm, affine_form, parity_bias
from esolangs.generation.helpers import _validate_truth_table, grid_width
from esolangs.generation.lookup import constant_output
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.circuit_diagram.generator import (
    _OUTPUT_GLYPH_COLUMNS,
    _Builder,
    _circuit_diagram_at,
    _FoldAnalysis,
    _generate_circuit,
    _narrowest_present,
)
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.hpool import _compact_pool_layout
from esolangs.languages.circuit_diagram.generator.layout import _Layout

# Width of the 2-input all-XOR flat drawing below (``-.X.-:``).
_XOR2_FLAT_WIDTH = 6


def parity_circuit(table: str, *, folded: bool) -> str | None:
    """Return a four/six-column ladder for full parity, otherwise None."""
    n = len(table).bit_length() - 1
    if n < 2 or (bias := parity_bias(table)) is None:
        return None
    return _parity_layout(n, bias, folded=folded)


def _parity_layout(n: int, bias: int, *, folded: bool) -> str:
    layout = _Layout()
    for k in range(n):
        row = 0 if k == 0 else 2 if k == 1 else 5 * k - 3
        layout.input_port(row, 1, k)
    for k in range(n - 1):
        row = 1 + 5 * k
        signal = n + k
        layout.glyph(2, row, "X" if k == 0 and bias else "x")
        layout.junction(3, row, signal)
        if k < n - 2 or folded:
            layout.junction(3, row + 3, signal)
            layout.run_vertical(3, row, row + 3, signal)
            layout.junction(1, row + 3, signal)
            layout.run_horizontal(1, 3, row + 3, signal)
            layout.junction(1, row + 4, signal)
            layout.run_vertical(1, row + 3, row + 4, signal)
    if folded:
        layout.glyph(2, row + 4, "-")
        layout.glyph(3, row + 4, ":")
    else:
        layout.glyph(4, row, "-")
        layout.glyph(5, row, ":")
    return layout.render()


def affine_circuit(table: str, width: int) -> str | None:
    """Return a direct XOR chain for a verified affine table."""
    n = _validate_truth_table(table)
    return _affine_layout(n, affine_form(table, n), width)


def _affine_layout(n: int, form: AffineForm | None, width: int) -> str | None:
    if form is None:
        return None
    constant = form.bias
    # The layout selects rails least-significant input first.
    coefficients = form.coefficients[::-1]
    if n >= 2 and all(coefficients):
        return _parity_layout(n, constant, folded=width < _XOR2_FLAT_WIDTH or n >= 3)
    builder = _Builder(narrow=True)
    rails = [builder.input_bus() for _ in range(n)]
    selected = [rail for bit, rail in enumerate(reversed(rails)) if coefficients[bit]]
    builder.band_start = builder.next_column
    # Reserve the output dash and colon beyond the last gate group.
    builder.limit = max(1, width - _OUTPUT_GLYPH_COLUMNS)
    if not selected:
        result = builder.constant(rails[0], "X" if constant else "x")
    elif len(selected) == 1:
        result = builder.invert(selected[0]) if constant else selected[0]
    else:
        result = builder.gate("X" if constant else "x", selected[0], selected[1])
        for rail in selected[2:]:
            result = builder.gate("x", result, rail)
    builder.output(result)
    return builder.layout.render()


def _drawn_at(
    table: str,
    flat: str,
    width: int,
    *,
    draw: Callable[[int], str] | None = None,
    affine: Callable[[int], str | None] | None = None,
) -> str:
    """Return the drawing fitted to ``width``, narrowed by band and XOR chain."""
    if draw is None:
        draw = partial(_circuit_diagram_at, table)
    primary = draw(width)
    if grid_width(primary) <= width:
        return primary
    banded = draw(max(1, width - _OUTPUT_GLYPH_COLUMNS))
    chain = affine_circuit(table, width) if affine is None else affine(width)
    return _narrowest_present(flat, banded, chain)


def balance_circuit_diagram(table: str) -> str:
    """Compare the default, the flat drawing and drawings at the square widths."""
    analysis = _FoldAnalysis()
    default = _generate_circuit(table, analysis=analysis)
    if constant_output(table) is not None:
        # Native sources beat the clock/gate layouts; no H lattice is needed.
        return default
    n = len(table).bit_length() - 1
    form = affine_form(table, n)
    draw = cache(partial(_circuit_diagram_at, table, analysis=analysis))
    affine = cache(partial(_affine_layout, n, form))
    flat = draw(None)
    candidates = [default, flat]
    # Folding can shrink a wide default while increasing its imbalance.
    # Retain the former H candidate until a folded layout beats its score.
    if len(table) >= 256:
        candidates.append(_h_term_layout(table).render())
    if len(table) >= 512 and (pool := _compact_pool_layout(table)) is not None:
        # Atomic leaves trade text area for the enclosing square: n=12 seeded
        # sides fall from 8592/8548 to 5654/5718 columns (including the body).
        candidates.append(pool.render())
    # A drawing's area is about that of the flat one whatever its width, so
    # the square side is isqrt(CELL_ASPECT * area).
    area = grid_width(flat) * (flat.count("\n") + 1)
    for width in (1, isqrt(CELL_ASPECT * area), isqrt(CELL_ASPECT * len(flat))):
        candidates.append(_drawn_at(table, flat, width, draw=draw, affine=affine))
        # A parity chain also wins unbanded, where the band logic skips it.
        chain = affine(width)
        if chain is not None:
            candidates.append(chain)
    return min(candidates, key=balance_score)
