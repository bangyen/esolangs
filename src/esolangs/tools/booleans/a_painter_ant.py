"""Parameterized Boolean generators for A Painter Ant.

A Painter Ant is a single ant on an infinite black grid.  Lowercase
``n``/``e``/``s``/``w`` move one cell in that direction onto a *black*
cell; uppercase ``N``/``E``/``S``/``W`` move onto a *white* cell; ``p``
and ``P`` paint the current cell black and white.  The program runs in an
implicit loop, so a generator's program must be a *fixed point*: after each
full cycle the ant returns to the origin with the grid in the same state,
so the output is identical for any limit that is a whole number of cycles.

The wiki defines no I/O, so the generator follows the parameterized
convention (like ``bio``/``back``/``nocomment``/``bfpda``): each input bit
is filled into the template as a lowercase/uppercase *pair* that tests the
target cell's colour — the two members of a pair point the same way but
require opposite colours, so exactly one succeeds and the ant's position
routes the computation.  The answer is the origin's colour after a whole
cycle (white is one, black is zero), read by a semantic grid model (the
interpreter's own output is the visited-cell bounding box, which carries no
coordinates).

The generator supports every one- and two-input table exactly.  n >= 3 is
an open problem (``docs/roadmap.md``): a *box-height* construction found by
search expresses most n == 3 tables (196 of 256, including AND3/OR3/XOR3/
majority via the box's height or its parity) but no general method for all
functions of an arity is known, so ``a_painter_ant`` raises for n >= 3.

The templates were found by search and verified exhaustively against the
interpreter for every instantiation; they are all fixed points
(cycle-stable).  Each base string has ``n`` slot positions, and each slot is
filled with ``{Xi}`` (bit ``i``) or ``{Ci}`` (the complemented bit), chosen
so the emitted template computes the requested table.
"""

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = ["a_painter_ant", "instantiate"]

# Two-input exact tables: table -> (base string, slot indices, (slot0 mode,
# slot1 mode)) where a mode is "X" (plain bit) or "C" (complemented bit).
_TWO_INPUT: dict[str, tuple[str, tuple[int, int], tuple[str, str]]] = {
    "0001": ("PWnnESppsSnS", (2, 3), ("C", "C")),  # AND
    "0010": ("PWnnESppsSnS", (2, 3), ("C", "X")),
    "0011": ("NPWSeEpWwWeS", (4, 2), ("C", "X")),  # b0
    "0100": ("PWnnESppsSnS", (2, 3), ("X", "C")),
    "0101": ("PNpNEpSWPePpS", (1, 9), ("X", "C")),  # b1
    "0110": ("pPPPSsNsWpWS", (2, 7), ("X", "X")),  # XOR
    "0111": ("PeNPnPpSS", (1, 4), ("C", "C")),  # OR
    "1000": ("PWnnESppsSnS", (2, 3), ("X", "X")),  # NOR
    "1001": ("pPPPSsNsWpWS", (2, 7), ("X", "C")),  # XNOR
    "1010": ("PNpNEpSWPePpS", (1, 9), ("X", "X")),  # !b0
    "1011": ("PeNPnPpSS", (1, 4), ("C", "X")),
    "1100": ("NPWSeEpWwWeS", (4, 2), ("X", "X")),  # !b1
    "1101": ("PeNPnPpSS", (1, 4), ("X", "C")),
    "1110": ("PeNPnPpSS", (1, 4), ("X", "X")),  # NAND
}

# One-input exact tables: table -> (template with one {X0} or {C0} slot).
_ONE_INPUT: dict[str, str] = {
    "00": "p",  # constant zero
    "01": "P{C0}pS",  # identity
    "10": "P{X0}pS",  # NOT
    "11": "P",  # constant one
}


def instantiate(template: str, bits: list[int]) -> str:
    """Fill a template's ``{X0}``/``{C0}`` placeholders with the bit commands.

    ``{Xi}`` becomes ``n`` for bit 0 and ``N`` for bit 1; ``{Ci}`` becomes
    ``N`` for bit 0 and ``n`` for bit 1 (the complemented bit's command).
    ``n``/``N`` both point north but require opposite target colours, so
    exactly one succeeds per input.
    """
    for i, bit in enumerate(bits):
        command = "N" if bit else "n"
        complement = "n" if bit else "N"
        template = template.replace("{X" + str(i) + "}", command)
        template = template.replace("{C" + str(i) + "}", complement)
    return template


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for a supported Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains ``{X0}``/``{C0}``.. placeholders that
    :func:`instantiate` fills with the per-bit movement commands.  The
    answer is the origin's colour after a whole cycle.

    All one- and two-input tables are supported; ``n >= 3`` raises
    :class:`ValueError`.  The n >= 3 cap is a documented open problem
    (``docs/roadmap.md``): a box-height construction expresses most tables
    (e.g. 196 of 256 at n == 3) but no general method for *all* functions of
    an arity is known.
    """
    n = _validate_truth_table(truth_table)

    if n == 0:
        return "p" if truth_table == "0" else "P"
    if n == 1:
        return _ONE_INPUT[truth_table]
    if n == 2:
        if truth_table == "0000":
            return "p"  # constant zero
        if truth_table == "1111":
            return "P"  # constant one
        template, slots, modes = _TWO_INPUT[truth_table]
        return _mark_slots(template, slots, modes)
    raise ValueError(
        "the A Painter Ant boolean generator supports n <= 2; n >= 3 is "
        "an open problem (see docs/roadmap.md)",
    )


def _mark_slots(
    template: str,
    slots: tuple[int, int],
    modes: tuple[str, str],
) -> str:
    """Replace the base template's slot positions with ``{Xi}``/``{Ci}``.

    Each slot position in the found template is replaced by the placeholder
    for its bit (``{X0}``/``{X1}``) or the complemented bit (``{C0}``/
    ``{C1}``) per ``modes``, so :func:`instantiate` fills it correctly.
    """
    chars = list(template)
    for i, (slot, mode) in enumerate(zip(slots, modes, strict=True)):
        chars[slot] = f"{{{'X' if mode == 'X' else 'C'}{i}}}"
    return "".join(chars)
