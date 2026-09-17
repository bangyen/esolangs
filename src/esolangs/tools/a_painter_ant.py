"""Boolean-function generator for A Painter Ant (parameterized convention).

Lowercase moves onto black, uppercase onto white, ``P`` paints white; the
program loops and the answer is the colour of the cell the ant ends a
pass on.  Row -1 is the never-painted lane, row 0 the corridor of
``2**n`` white cells, row +1 the answers.  Each input is ``n`` (into the
lane) or ``N`` (blocked), then ``E`` x ``2**(n-1-i)`` which only the
corridor allows, then ``SN`` returning a lane ant.  Every program is a
pass-stable fixed point.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)

__all__ = ["a_painter_ant"]


#: The one ``(zero, one)`` pair every input is spelled with.
_PAIR = ("n", "N")


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for an ``n``-input Boolean function.

    One character run per input, the weight in the ``E`` walk after it.
    """
    n = _validate_truth_table(truth_table)
    size = len(truth_table)
    # Pass 1 paints the origin; later ``N`` lifts off the answer, ``W`` returns.
    out = ["N", "W" * size, "P"]
    if truth_table[0] == "1":
        out.append("sPN")
    for bit in truth_table[1:]:
        # ``e`` paints on pass 1, ``E`` enters white later: one cell per pass.
        out.append("ePEP")
        if bit == "1":
            # Paints the answer cell on pass 1; harmless later.
            out.append("sPN")
    out.append("W" * (size - 1))
    for i in range(n):
        out.append(TEMPLATE_CHAR)
        out.append("E" * (1 << (n - 1 - i)) + "SN")
    # ``sS`` steps onto the answer whichever colour it is.
    out.append("sS")
    return "".join(out)


def _instantiate_apa(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's input runs (``n`` zero, ``N`` one)."""
    return fill_runs(template, TEMPLATE_CHAR, apa_setters(template, len(bits)), bits)


def apa_setters(template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` route text for every input of ``template``."""
    del template
    return tuple(_PAIR for _ in range(n))
