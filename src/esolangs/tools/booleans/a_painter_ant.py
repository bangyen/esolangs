"""Boolean generators for A Painter Ant.

A Painter Ant is a single ant on an infinite grid of black or white cells
(all black to start).  Lowercase ``n``/``e``/``s``/``w`` move one cell in
that direction only if the destination is black; uppercase ``N``/``E``/``S``/
``W`` move only if the destination is white; ``p``/``P`` paint the current
cell black/white.  The program runs in an implicit loop: after the last
instruction the pointer returns to the first.

The wiki defines no I/O, so the generator follows the parameterized
convention (like ``bio``/``back``/``nocomment``/``bfpda``): the template
carries ``{X0}`` and ``{X1}`` placeholders for the two input bits, which
:func:`instantiate` fills with the per-bit routing code.  The answer is the
**colour of the cell the ant lands on** at the end of a cycle (white is one,
black is zero), read by a semantic grid model (the interpreter's own output
is the visited-cell bounding box, which carries no coordinates).

The construction paints the decision-tree leaves and routes the ant to the
leaf for its inputs.  :func:`_head` paints one leaf per input combination
and returns to the origin; each leaf is painted ``P`` (white) for a one
table entry and left unpainted (a space, ignored by the interpreter) for a
zero.  Only ``P`` is ever used -- the generator never paints a cell black --
so the white cells are monotone increasing: cycle 1 establishes them and
every later cycle only re-confirms a subset, which is what makes the
programs cycle-stable.  The ``body`` then funnels the ant (from whichever
corner it ends cycle 2 at) to a canonical routing point, and the final
input's embedding does the last east/west route onto the output leaf.

The head is built generically: leaves sit on the axes (the final input on
``x = +-2``, the first on ``y = +-2`` for two inputs or ``0`` for one),
visited in an opposite-corner order so the ``_leg`` staircases between them
pass through the clean origin.  Every non-first leg carries an uppercase
``W``/``E`` prefix that points away from the origin -- a blocked no-op on
cycle 1, but the anchor of the closed cycle-2 dance.  This one ``_head``
handles both ``n == 1`` and ``n == 2``.

The template routes the first ``n-1`` inputs north/south (``nn``/``ss``)
before the body and the final input east/west after it (``WWwWWEEe`` for a
one bit and ``NENEESWw`` for a zero, an 8-character complement pair that
lands on the opposite-coloured leaf).  Every one- and two-input table is
supported and every instantiated program is a cycle-stable fixed point (the
bounding box is identical for any whole number of cycles).  ``n >= 3`` is
still open (``docs/roadmap.md``) and raises :class:`ValueError`.
"""

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = ["a_painter_ant"]

# The fixed routing body: it paints the ring and funnels the ant to the
# canonical pre-final-route point (the final input routes east/west after it).
_BODY = "NwPnPwnPEsPwPswPWWePsPesPSSnPePeePNNsePSSnPePnePEEwPnPwnPNNsPwPsPwPS"

# ``{X0}``: non-final inputs route north/south.
_X0 = {1: "nn", 0: "ss"}
# ``{XF}``: the final (least-significant) input routes east/west.
_XF = {1: "WWwWWEEe", 0: "NENEESWw"}


def _leaf_color(truth_table: str, bits: list[int]) -> str:
    """Return the ``P``/space to paint the leaf for the input ``bits``.

    ``bits`` is listed most-significant first, so the table index is the
    packed binary value ``sum(bit << (n-1-i))``.
    """
    index = 0
    for n, b in enumerate(bits):
        index += b << (len(bits) - n - 1)
    return "P" if truth_table[index] == "1" else " "


def _leaf_positions(n: int) -> list[tuple[int, int, tuple[int, ...]]]:
    """Return ``(x, y, bits)`` for every leaf in head-visit order.

    The final input sits on the east/west axis (``x = +-2``), the first on
    the north/south axis (``y = +-2`` for two inputs, ``0`` for one).  The
    visit order keeps consecutive leaves opposite corners so the ``_leg``
    staircases through the clean origin (``docs/a_painter_ant_generator.md``).
    """
    order: tuple[tuple[int, ...], ...]
    if n == 1:
        order = ((1,), (0,))
    elif n == 2:
        order = ((1, 1), (0, 0), (1, 0), (0, 1))
    else:
        raise ValueError(
            "the A Painter Ant head generator supports n == 1 and n == 2; "
            "n >= 3 is an open problem (see docs/roadmap.md)",
        )
    out: list[tuple[int, int, tuple[int, ...]]] = []
    for bits in order:
        x = 2 if bits[-1] == 0 else -2
        y = 0 if n == 1 else (2 if bits[0] == 0 else -2)
        out.append((x, y, bits))
    return out


def _leg(px: int, py: int, qx: int, qy: int) -> str:
    """Lowercase path from ``(px, py)`` to ``(qx, qy)``.

    A purely horizontal run goes straight along the x-axis.  Any other leg
    is a staircase of alternating two-cell y/x chunks through the origin
    (leaves sit at ``+-2`` on both axes, so the origin is the one clean cell
    the lower-case moves can always reach).
    """
    dy = qy - py
    dx = qx - px
    if dy == 0:
        return ("e" if dx > 0 else "w") * abs(dx)

    m = max(abs(dy), abs(dx)) // 2
    ny = abs(dy) // 2
    nx = abs(dx) // 2
    yd = "s" if dy > 0 else "n"
    xd = "e" if dx > 0 else "w"
    ychunks = [yd] * ny
    xchunks = [xd] * nx
    for _ in range(m - ny):  # extra y chunks detour out and back
        ychunks.append("n" if py > 0 else "s")
        ychunks.append("s" if py > 0 else "n")
    for _ in range(m - nx):  # extra x chunks detour out and back
        xchunks.append("w" if px > 0 else "e")
        xchunks.append("e" if px > 0 else "w")
    ychunks = ychunks[:m]
    xchunks = xchunks[:m]
    out = []
    for i in range(m):
        out.append(ychunks[i] * 2)
        out.append(xchunks[i] * 2)
    return "".join(out)


def _head(truth_table: str, bits: list[int]) -> str:
    """Build the A Painter Ant head for a one- or two-input truth table.

    The head paints every leaf and returns to the origin.  It walks each
    ``_leg`` with an uppercase prefix before it that points *away* from the
    origin (``W`` for a west leaf, ``E`` for an east leaf); those prefixes
    are blocked no-ops on cycle 1 but anchor the closed cycle-2 dance, which
    is what makes every instantiated program cycle-stable.
    """
    out = ["N"]
    cx = cy = 0
    for x, y, leaf_bits in _leaf_positions(len(bits)):
        if (cx, cy) != (0, 0):
            out.append("W" if cx < 0 else "E")
        out.append(_leg(cx, cy, x, y))
        out.append(_leaf_color(truth_table, list(leaf_bits)))
        cx, cy = x, y
    out.append("W" if cx < 0 else "E")
    out.append(_leg(cx, cy, 0, 0))
    out.append("Ssn")
    return "".join(out)


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for a one- or two-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains ``{X0}``..``{Xn-1}`` placeholders that
    :func:`~esolangs.tools.booleans.parameterized.instantiate` fills with
    the per-bit routing.  The answer is the colour of the cell the ant lands
    on after a cycle (white is one, black is zero).

    Every one- and two-input table is supported; ``n >= 3`` raises
    :class:`ValueError` (an open problem, see ``docs/roadmap.md``).  The
    first ``n-1`` inputs route north/south before the body; the final
    (least-significant) input routes east/west onto its leaf after it.
    """
    n = _validate_truth_table(truth_table)
    if n > 2:
        raise ValueError(
            "the A Painter Ant boolean generator supports n == 1 and n == 2; "
            "n >= 3 is an open problem (see docs/roadmap.md)",
        )

    # The head paints every leaf; the first n-1 inputs route north/south
    # before the body, and the final (least-significant) input routes
    # east/west onto its leaf after it.
    head = _head(truth_table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"

    return head + prefix + _BODY + suffix


def instantiate(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's ``{Xi}`` placeholders.

    Every input except the final one routes north/south (``nn`` for a one
    bit, ``ss`` for a zero); the final (least-significant) input routes
    east/west (``WWwWWEEe`` for a one, ``NENEESWw`` for a zero).  ``bits``
    must have length 1 or 2, matching the template built by
    :func:`a_painter_ant`.
    """
    from esolangs.tools.booleans.parameterized import instantiate as _sub

    return _sub(
        template,
        bits,
        lambda i, bit: (_XF[bit] if i == len(bits) - 1 else _X0[bit]),
        lambda _i, _b: "",
    )
