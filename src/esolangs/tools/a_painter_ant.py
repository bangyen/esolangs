"""Boolean-function generator for A Painter Ant (parameterized convention).

One ant on an infinite black grid: ``n``/``e``/``s``/``w`` move onto a
black cell, ``N``/``E``/``S``/``W`` onto a white one, ``p``/``P`` paint;
the program loops.  No I/O, so the parameterized convention
(:mod:`esolangs.tools.parameterized`): one run per input, filled by
:func:`_instantiate_apa`.  The answer is the colour of the cell the ant
ends a pass on (white = 1), read by a grid model (the interpreter's
bounding box has no coordinates).

Geometry, rows named by ``y`` (north is ``-1``)::

    row -1   the lane, never painted, black for ever;
    row  0   the corridor, 2**n white cells from x = 0 east;
    row +1   the answers, cell x white iff truth_table[x] == "1".

Pass 1 paints corridor and answers and walks back to ``x = 0``.  Each
input is one character: ``n`` steps into the lane, ``N`` is blocked, so a
zero leaves the corridor.  Then ``E`` x ``2**(n-1-i)`` (the lane refuses
it, the corridor allows it) and ``SN`` (returns a lane ant to the
corridor; a corridor ant steps onto its answer cell and back, or is
blocked twice).  The ant ends at the table index and ``sS`` steps onto
the answer.  Only ``P`` is used, so white cells are monotone and every
program is a pass-stable fixed point.  Building, returning and routing
each cost O(T); the routing is uniform, with the weight in the template.
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains one one-character run per input that
    :func:`_instantiate_apa` fills with ``n`` or ``N``; the weight of each
    input is the ``E`` walk the template spells after its run.  The answer
    is the colour of the cell the ant lands on after a cycle (white is one,
    black is zero).

    Every table is supported for any ``n``, and every instantiated program
    is a cycle-stable fixed point.
    """
    n = _validate_truth_table(truth_table)
    size = len(truth_table)
    # Pass 1: ``N`` and ``W`` blocked, paint the origin.  Later: ``N``
    # lifts off the answer cell, ``W`` walks back to the origin.
    out = ["N", "W" * size, "P"]
    if truth_table[0] == "1":
        out.append("sPN")
    for bit in truth_table[1:]:
        # Pass 1: ``e`` enters black and paints, ``E`` blocked.  Later:
        # ``e`` blocked, ``E`` enters white.  Advances one cell every pass.
        out.append("ePEP")
        if bit == "1":
            # Pass 1 paints the answer cell and returns north; later ``s``
            # is blocked by it and both paints are harmless.
            out.append("sPN")
    out.append("W" * (size - 1))
    for i in range(n):
        out.append(TEMPLATE_CHAR)
        # The weight, then the return to the corridor.
        out.append("E" * (1 << (n - 1 - i)) + "SN")
    # White answer: ``s`` is blocked and ``S`` enters it.  Black answer:
    # ``s`` enters it and ``S`` is blocked by the black cell beyond.
    out.append("sS")
    return "".join(out)


def _instantiate_apa(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's input runs.

    Every input is one character, ``n`` for a zero and ``N`` for a one;
    ``bits`` must match the template built by :func:`a_painter_ant`.
    """
    return fill_runs(template, TEMPLATE_CHAR, apa_setters(template, len(bits)), bits)


def apa_setters(template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` route text for every input of ``template``.

    The same pair for every input: the template, not the embed, carries
    the weight, so ``template`` has nothing to say about the spelling.
    """
    del template
    return tuple(_PAIR for _ in range(n))
