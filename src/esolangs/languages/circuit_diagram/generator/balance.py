"""Circuit Diagram affine chains and exact width transitions."""

from math import isqrt

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


def affine_circuit(table: str, width: int) -> str | None:
    """Return a direct XOR chain if binary-carry parity verifies the table."""
    n = _validate_truth_table(table)
    constant = int(table[0])
    coefficients = [constant ^ int(table[1 << bit]) for bit in range(n)]
    parity = constant
    for row, value in enumerate(table):
        if parity != int(value):
            return None
        # All binary carries together flip fewer than 2T bits.
        carry = row
        bit = 0
        while carry & 1:
            parity ^= coefficients[bit]
            carry >>= 1
            bit += 1
        if bit < n:
            parity ^= coefficients[bit]
    if n == 2 and all(coefficients):
        if width < _XOR2_FLAT_WIDTH:
            # Return the output below both inputs, then left. Two rows
            # isolate its final junction from the colon's diagonal pin.
            gate = "X" if constant else "x"
            return f"-.\n  {gate}.\n-. |\n   .\n  .\n .\n |\n .-:"
        # Adjacent input rows feed the two diagonal gate pins directly.
        layout = _Layout()
        for signal, row in enumerate((0, 2)):
            layout.glyph(0, row, "-")
            layout.junction(1, row, signal)
        layout.glyph(2, 1, "X" if constant else "x")
        layout.junction(3, 1, 2)
        layout.glyph(4, 1, "-")
        layout.glyph(5, 1, ":")
        return layout.render()
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
