"""Boolean-function generator for A Painter Ant (parameterized convention).

A Painter Ant is a no-input grid language, so this follows the
parameterized convention described in
:mod:`esolangs.tools.parameterized`: the template's input runs are
filled with movement per input combination, and the ant's final cell
colour encodes the table entry.

The construction is one white corridor with the answers in the adjacent
row.  Building it, returning to its origin, and routing along it each cost
O(T), and the routing is *uniform*: every input of every table is spelled by
the same one-character pair, ``n`` for a zero and ``N`` for a one, and the
template carries the input's weight as the walk that follows its run.
"""

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    Setters,
    _validate_truth_table,
    fill_runs,
)

__all__ = ["a_painter_ant"]


# --- A Painter Ant (no-input grid language; parameterized convention) ---
#
# A Painter Ant is a single ant on an infinite grid of black or white cells
# (all black to start).  Lowercase ``n``/``e``/``s``/``w`` move one cell in
# that direction only if the destination is black; uppercase ``N``/``E``/``S``/
# ``W`` move only if the destination is white; ``p``/``P`` paint the current
# cell black/white.  The program runs in an implicit loop: after the last
# instruction the pointer returns to the first.
#
# The wiki defines no I/O, so the generator follows the parameterized
# convention (like ``bio``/``back``/``nocomment``/``bfpda``): the template
# carries one run per input bit, which :func:`_instantiate_apa` fills.  The
# answer is the **colour of the cell the ant lands on** at the end of a
# cycle (white is one, black is zero), read by a semantic grid model (the
# interpreter's own output is the visited-cell bounding box, which carries
# no coordinates).
#
# Geometry, rows named by ``y`` (north is ``-1``):
#
#   row -1   never painted: the *lane*, black for ever;
#   row  0   the corridor, ``2**n`` white cells from ``x = 0`` east;
#   row +1   the answers, cell ``x`` white iff ``truth_table[x] == "1"``.
#
# The head paints the corridor and the answers on the first pass and walks
# back to ``x = 0``.  Then each input is one character: ``n`` steps the ant
# north into the black lane, ``N`` is blocked by it, so a zero bit leaves
# the corridor and a one bit stays.  The template follows the run with
# ``E`` repeated ``2**(n-1-i)`` times -- a walk along the white corridor
# that the lane, being black, refuses entirely -- and ``SN``, which brings
# a lane ant back down onto the corridor (``S`` onto white, then ``N``
# blocked by the black lane) and leaves a corridor ant where it was (``S``
# steps onto a white answer cell, ``N`` steps straight back; on a black
# answer cell both are blocked).  So after ``n`` inputs the ant stands at
# ``x = sum(bit_i * 2**(n-1-i))``, the table index, and the closing ``sS``
# steps it onto the answer cell whichever colour that is.
#
# Only ``P`` is ever used -- the generator never paints a cell black -- so
# the white cells are monotone increasing: pass 1 establishes them and
# every later pass only re-confirms them, which makes every program a
# pass-stable fixed point.  The pair is the same for every input at every
# arity, and the weight lives in the template.

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
    # Pass 1: ``N`` and the ``W`` walk are blocked by black and paint the
    # origin.  Later passes: ``N`` lifts the ant off its answer cell onto
    # the corridor and ``W`` walks it back to the origin, stopping there
    # because the cell beyond is black.
    out = ["N", "W" * size, "P"]
    if truth_table[0] == "1":
        out.append("sPN")
    for bit in truth_table[1:]:
        # First pass: ``e`` enters the black next cell and paints it; ``E``
        # is then blocked.  Later passes: ``e`` is blocked and ``E`` enters
        # that already-white cell.  Thus the same four commands advance one
        # cell on every pass while establishing a permanent white corridor.
        out.append("ePEP")
        if bit == "1":
            # On the first pass, enter and paint the black answer cell, then
            # return north to the white corridor.  Later ``s`` is blocked by
            # that answer, so both paints are harmless and ``N`` is blocked.
            out.append("sPN")
    out.append("W" * (size - 1))
    for i in range(n):
        out.append(TEMPLATE_CHAR)
        # The weight: a walk the corridor allows and the lane refuses, then
        # the return that puts a lane ant back on the corridor.
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
