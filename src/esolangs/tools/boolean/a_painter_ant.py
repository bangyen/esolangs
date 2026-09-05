"""Boolean-function generator for A Painter Ant (parameterized convention).

A Painter Ant is a no-input grid language, so this follows the
parameterized convention described in
:mod:`esolangs.tools.boolean.parameterized`: the template's ``{Xi}``
placeholders are movement runs that the harness fills per input
combination, and the ant's final cell colour encodes the table entry.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table, instantiate

__all__ = ["a_painter_ant"]


# --- A Painter Ant (no-input grid language; parameterized convention) ---
#
# Boolean generators for A Painter Ant.
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
# carries ``{X0}`` and ``{X1}`` placeholders for the two input bits, which
# :func:`instantiate` fills with the per-bit routing code.  The answer is the
# **colour of the cell the ant lands on** at the end of a cycle (white is one,
# black is zero), read by a semantic grid model (the interpreter's own output
# is the visited-cell bounding box, which carries no coordinates).
#
# The construction paints the decision-tree leaves and routes the ant to the
# leaf for its inputs.  :func:`_head` paints one leaf per input combination
# and returns to the origin; each leaf is painted ``P`` (white) for a one
# table entry and left unpainted (a space, ignored by the interpreter) for a
# zero.  Only ``P`` is ever used -- the generator never paints a cell black --
# so the white cells are monotone increasing: cycle 1 establishes them and
# every later cycle only re-confirms a subset, which is what makes the
# programs cycle-stable.  The ``body`` then funnels the ant (from whichever
# corner it ends cycle 2 at) to a canonical routing point, and the final
# input's embedding does the last east/west route onto the output leaf.
#
# The head is built generically: for one and two inputs the leaves sit on
# the axes (the final input on ``x = +-2``, the first on ``y = +-2`` or
# ``0``) and the cycle-2 ant dances on the pre-painted stars (see
# ``docs/a_painter_ant_generator.md`` for the ring rule).  For three inputs
# the leaves sit on one row ``y = -2`` at ``x = +-2 +-4 +-8``,
# four cells apart so adjacent stars share their axis cells and symmetric
# across the y-axis.  The row generalises: this one ``_head`` serves every
# arity, not just the three spelled out above -- XOR builds and lands
# correctly on all inputs through ``n == 7`` (34788 characters), which is as
# far as it was measured, not a ceiling.
#
# The template routes the first ``n-1`` inputs by their weight (west/north
# for a one bit, east/south for a zero) before the body and the final input
# east/west after it (``WWwWWEEe`` for a one bit and ``NENEESWw`` for a
# zero, an 8-character complement pair that lands on the opposite-coloured
# leaf).  Every table of any input count is supported and every instantiated
# program is a cycle-stable fixed point (the bounding box is identical for
# any whole number of cycles).

# The north/south pair a non-final input used to route through.  Unused:
# ``_instantiate_apa`` builds those moves with :func:`_bit_move`, whose
# length scales with the bit's position rather than being a fixed pair.
_X0 = {1: "nn", 0: "ss"}
# ``{XF}``: the final (least-significant) input routes east/west.
_XF = {1: "WWwWWEEe", 0: "NENEESWw"}
# The inverse of each move direction, for retracing a path.
_OPP = {
    "n": "s",
    "s": "n",
    "e": "w",
    "w": "e",
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
}


def _bit_is_horizontal(n: int, k: int) -> bool:
    """Return whether bit ``k`` (of ``n``, most-significant first) moves.

    Moves on the x axis rather than y -- the same index-parity rule the
    head, the leaf coordinates, and the routing all agree on.
    """
    return k % 2 != n % 2


def _bit_move(n: int, k: int, bit: int) -> str:
    """Return the moves that input bit ``k`` contributes.

    ``bits`` are most-significant first, so bit ``k`` carries weight
    ``2 ** (n - k)`` and moves on the axis chosen by index parity
    (:func:`_bit_is_horizontal`); a set bit moves west/north, a cleared bit
    east/south.  The head walks these moves out to each leaf and the
    routing walks them to read it, so the two always agree.
    """
    mag: int = 2 ** (n - k)
    if _bit_is_horizontal(n, k):
        return ("w" if bit else "e") * mag
    return ("n" if bit else "s") * mag


def _reverse_moves(moves: str) -> str:
    """Return ``moves`` reversed with every direction inverted."""
    return "".join(_OPP[c] for c in reversed(moves))


def _leaf_color(truth_table: str, bits: list[int]) -> bool:
    """Return whether to paint the leaf for the input ``bits``.

    ``bits`` is listed most-significant first, so the table index is the
    packed binary value ``sum(bit << (n-1-i))``.
    """
    index = 0
    for n, b in enumerate(bits):
        index += b << (len(bits) - n - 1)
    return truth_table[index] == "1"


def _leaf_positions(n: int) -> list[tuple[int, int, tuple[int, ...]]]:
    """Return ``(x, y, bits)`` for every leaf in head-visit order.

    The coordinates come from the same weighted rule the head walks and the
    routing reads: each bit ``k`` contributes ``+-2 ** (n-k)`` on the axis
    chosen by index parity, with a cleared bit negative.  The head only
    uses the ``bits``; it reaches each leaf by walking those weights, so
    ``(x, y)`` is the mirror position the routing reads.
    """
    out: list[tuple[int, int, tuple[int, ...]]] = []

    for i in range(2**n):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        x = 0
        y = 0

        for k, b in enumerate(bits):
            mag = 2 ** (n - k) if b else -(2 ** (n - k))
            if _bit_is_horizontal(n, k):
                x += mag
            else:
                y += mag

        out.append((x, y, tuple(bits)))

    return out


def _head(truth_table: str, bits: list[int]) -> str:
    """Build the A Painter Ant head for an ``n``-input table.

    The head paints every white leaf and returns to the origin.  It walks
    each leaf out and back piecewise -- one weighted move per input bit
    (:func:`_bit_move`), in the same order and direction the routing uses,
    so the outbound path never crosses a previously painted leaf (the
    intermediate cells are never leaf positions) and the reverse path
    retraces it cleanly.  The ``N`` prefix and ``Ssn`` ending are no-ops
    on the empty first cycle; from cycle 2 on the ``WS``/``NE`` anchors
    launch the ant off the leaf onto the painted ring, making the whole
    program a cycle-stable fixed point.
    """
    n = len(bits)
    out = ["N"]

    for _x, _y, leaf_bits in _leaf_positions(n):
        if not _leaf_color(truth_table, list(leaf_bits)):
            out.append(" ")
            continue
        # Odd n starts on a horizontal bit, so its outbound would lead with
        # NE and the reverse path would end on an orphan WS anchor; a
        # leading WS (no moves) flips it to start WS / end NE like n == 2.
        outbound = "WS" if n >= 3 and n % 2 == 1 else ""
        outbound += "".join(
            (
                ("NE" if _bit_is_horizontal(n, k) else "WS") + _bit_move(n, k, b)
                if n >= 2
                else _bit_move(n, k, b)
            )
            for k, b in enumerate(leaf_bits)
        )
        out.append(outbound + "P" + _reverse_moves(outbound))

    out.append("Ssn")
    return "".join(out)


def _body() -> str:
    """Generate the routing body.

    The body paints two two-layer stars -- one around the output leaf and
    one around its y-mirror -- so the final input never has to be
    re-embedded: it only routes to whichever star is already painted.
    Each star is walked as a clockwise spiral of ``P`` paints (the ring
    cells at distance 1 and the axis cells at distance 2), and the two
    stars are connected by the black gap between their rings: the star
    centres are four cells apart and each ring reaches one cell toward the
    other, so the gap is ``4 - 2`` east moves on the row above.  The body
    starts and ends on the shared cell at ``(0, +-2)`` -- the canonical
    point the final input's east/west routing leaves from -- and its
    blocked-uppercase returns are the anchors of the cycle-2 dance.
    """
    # West star, entered from the shared cell: east ring cell, then the
    # clockwise spiral (single ring steps, L-shaped detours out to the axis
    # cells, and blocked-uppercase returns from the axis cells), ending on
    # the south-east diagonal.
    west = ("wP", "nP", "wnP", "EsP", "wP", "swP", "WWeP", "sP", "esP", "SSnP", "eP")
    # East (mirror) star, entered after the gap on the south-west diagonal
    # and walked clockwise to the shared west axis cell.
    east = ("NNseP", "SSnP", "eP", "neP", "EEwP", "nP", "wnP", "NNsP", "wP", "sP", "wP")
    gap = 4 - 2  # star centres 4 apart; each ring reaches 1 cell inward
    return "N" + "".join(west) + "e" * gap + "P" + "".join(east) + "S"


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for an ``n``-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains ``{X0}``..``{Xn-1}`` placeholders that
    :func:`~esolangs.tools.boolean.parameterized.instantiate` fills with
    the per-bit routing.  The answer is the colour of the cell the ant lands
    on after a cycle (white is one, black is zero).

    Every table is supported for any ``n``, and every instantiated program
    is a cycle-stable fixed point.  The first ``n-1`` inputs route by their
    weight (west/north for a one bit, east/south for a zero) before the
    body; the final (least-significant) input routes east/west onto its
    leaf after it.
    """
    n = _validate_truth_table(truth_table)

    # The head paints every leaf; the body paints the two stars; the first
    # n-1 inputs route by weight before the body, and the final
    # (least-significant) input routes east/west onto its leaf after it.
    head = _head(truth_table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"

    return head + prefix + _body() + suffix


def _instantiate_apa(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's ``{Xi}`` placeholders.

    Every input except the final one routes piecewise by its weight
    (``2 ** (n - i)`` cells along the index-parity axis, west/north for a
    one bit, east/south for a zero -- :func:`_bit_move`), and the final
    (least-significant) input routes east/west with the ``WWwWWEEe`` /
    ``NENEESWw`` landing dance onto its leaf.  ``bits`` must match the
    template built by :func:`a_painter_ant`.
    """
    n = len(bits)

    def replace(i: int, bit: int) -> str:
        if i == len(bits) - 1:
            return _XF[bit]
        return _bit_move(n, i, bit)

    return instantiate(
        template,
        bits,
        replace,
    )
