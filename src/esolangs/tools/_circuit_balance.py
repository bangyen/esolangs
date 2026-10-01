"""Circuit Diagram affine chains and exact width transitions."""

from esolangs.tools._circuit_layout import _Layout
from esolangs.tools.circuit_diagram import (
    _Builder,
    _circuit_diagram_at,
    _selector_orders,
)
from esolangs.tools.helpers import _validate_truth_table, grid_width, narrowest_grid


def affine_circuit(
    table: str, width: int, *, _events: list[int] | None = None
) -> str | None:
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
        if width < 6:
            if _events is not None:
                _events.append(6)
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
    builder.limit = max(1, width - 2)
    if not selected:
        result = builder.constant(rails[0], "X" if constant else "x")
    elif len(selected) == 1:
        result = builder.invert(selected[0]) if constant else selected[0]
    else:
        result = builder.gate("X" if constant else "x", selected[0], selected[1])
        for rail in selected[2:]:
            result = builder.gate("x", result, rail)
    builder.output(result)
    if _events is not None and builder.next_limit is not None:
        _events.append(builder.next_limit + 2)
    return builder.layout.render()


def balance_circuit_diagram(table: str, default: str) -> str:
    """Compare reachable gate-column thresholds and band-fit transitions."""
    flat, order = min(
        (
            (_circuit_diagram_at(table, None, order), order)
            for order in _selector_orders(table, compact=False)
        ),
        key=lambda built: len(built[0]),
    )
    floor = grid_width(flat)
    candidates = [default, flat]
    width = 1
    while width < floor:
        events = [floor]
        primary = _circuit_diagram_at(table, width, order, _events=events)
        span = grid_width(primary)
        if span <= width:
            candidates.append(primary)
        else:
            events.append(span)
            shifted: list[int] = []
            banded = _circuit_diagram_at(
                table, max(1, width - 2), order, _events=shifted
            )
            events.extend(point + 2 for point in shifted)
            affine = affine_circuit(table, width, _events=events)
            forms = (flat, banded) if affine is None else (flat, banded, affine)
            candidates.append(narrowest_grid(*forms))
        # Until a failed column comparison becomes true, the drawing and its
        # band decisions stay fixed. A drawing's own span can also start fitting.
        width = min(events)
    from esolangs.tools.wrap import balance_score

    return min(candidates, key=balance_score)
