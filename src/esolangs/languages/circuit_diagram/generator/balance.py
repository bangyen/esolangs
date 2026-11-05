"""Circuit Diagram affine chains and exact width transitions."""

from math import isqrt

from esolangs.generation.algebraic import affine_form
from esolangs.generation.helpers import _validate_truth_table, grid_width
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.circuit_diagram.generator import (
    _OUTPUT_GLYPH_COLUMNS,
    _Builder,
    _circuit_diagram_at,
    _narrowest_present,
)
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.layout import _Layout

# Width of the 2-input all-XOR flat drawing below (``-.X.-:``).
_XOR2_FLAT_WIDTH = 6


def parity_circuit(table: str, *, folded: bool) -> str | None:
    """Return a four/six-column ladder for full parity, otherwise None."""
    n = len(table).bit_length() - 1
    if n < 2:
        return None
    parity = bias = int(table[0])
    for row, value in enumerate(table):
        if int(value) != parity:
            return None
        carry = row
        while carry & 1:
            parity ^= 1
            carry >>= 1
        parity ^= 1
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
    form = affine_form(table, n)
    if form is None:
        return None
    constant = form.bias
    # The layout selects rails least-significant input first.
    coefficients = form.coefficients[::-1]
    if n >= 2 and all(coefficients):
        return parity_circuit(table, folded=width < _XOR2_FLAT_WIDTH or n >= 3)
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


def _drawn_at(table: str, flat: str, width: int) -> str:
    """Return the drawing fitted to ``width``, narrowed by band and XOR chain."""
    primary = _circuit_diagram_at(table, width)
    if grid_width(primary) <= width:
        return primary
    banded = _circuit_diagram_at(table, max(1, width - _OUTPUT_GLYPH_COLUMNS))
    return _narrowest_present(flat, banded, affine_circuit(table, width))


def balance_circuit_diagram(table: str, default: str) -> str:
    """Compare the default, the flat drawing and drawings at the square widths."""
    if len(set(table)) == 1:
        # Native sources beat the clock/gate layouts; no H lattice is needed.
        return default
    flat = _circuit_diagram_at(table, None)
    candidates = [default, flat]
    # Folding can shrink a wide default while increasing its imbalance.
    # Retain the former H candidate until a folded layout beats its score.
    if len(table) >= 256 and "1" in table:
        candidates.append(_h_term_layout(table).render())
    # A drawing's area is about that of the flat one whatever its width, so
    # the square side is isqrt(CELL_ASPECT * area).
    area = grid_width(flat) * (flat.count("\n") + 1)
    for width in (1, isqrt(CELL_ASPECT * area), isqrt(CELL_ASPECT * len(flat))):
        candidates.append(_drawn_at(table, flat, width))
        # A parity chain also wins unbanded, where the band logic skips it.
        chain = affine_circuit(table, width)
        if chain is not None:
            candidates.append(chain)
    return min(candidates, key=balance_score)
