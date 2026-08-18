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

The head is built generically: for one and two inputs the leaves sit on
the axes (the final input on ``x = +-2``, the first on ``y = +-2`` or
``0``) and the cycle-2 ant dances on the pre-painted stars (see
``docs/a_painter_ant_generator.md`` for the ring rule).  For three inputs
the leaves sit on two rows ``y = +-2`` with ``x`` in ``{-6,-2,2,6}``,
four cells apart so adjacent stars share their axis cells.  This one
``_head`` handles ``n == 1``, ``n == 2``, and ``n == 3``.

The template routes the first ``n-1`` inputs north/south (``nn``/``ss``)
before the body and the final input east/west after it (``WWwWWEEe`` for a
one bit and ``NENEESWw`` for a zero, an 8-character complement pair that
lands on the opposite-coloured leaf).  Every one- and two-input table is
supported and every instantiated program is a cycle-stable fixed point (the
bounding box is identical for any whole number of cycles).  The ``n == 3``
two-row construction is exact for cycle 1 on every three-input table but is
**not yet cycle-stable** -- the cycle-2 dance for that layout is still open
(``docs/a_painter_ant_generator.md``) -- so ``n >= 3`` raises
:class:`ValueError`.
"""

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = ["a_painter_ant"]

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

    For one and two inputs the leaves sit on the axes (the final input on
    ``x = +-2``, the first on ``y = +-2`` or ``0``) and the visit order
    keeps consecutive leaves opposite corners so the head's legs pass
    through the clean origin.  For three inputs the leaves sit on two rows
    ``y = +-2`` with ``x = (2*b1-1)*2 + (2*b2-1)*4`` in ``{-6,-2,2,6}``:
    four cells apart, so adjacent stars share their axis cells
    (``docs/a_painter_ant_generator.md``).
    """
    if n == 3:
        positions: list[tuple[int, int, tuple[int, ...]]] = []
        for b0, b1, b2 in (
            (1, 1, 0),
            (0, 1, 0),
            (1, 1, 1),
            (0, 1, 1),
            (1, 0, 0),
            (0, 0, 0),
            (1, 0, 1),
            (0, 0, 1),
        ):
            x = (2 * b1 - 1) * 2 + (2 * b2 - 1) * 4
            y = -2 if b0 == 1 else 2
            positions.append((x, y, (b0, b1, b2)))
        return positions
    order: tuple[tuple[int, ...], ...]
    if n == 1:
        order = ((1,), (0,))
    elif n == 2:
        order = ((1, 1), (0, 0), (1, 0), (0, 1))
    else:
        raise ValueError(
            "the A Painter Ant head generator supports n == 1, n == 2, and "
            "n == 3; n >= 4 is an open problem (see docs/roadmap.md)",
        )
    out: list[tuple[int, int, tuple[int, ...]]] = []
    for bits in order:
        x = 2 if bits[-1] == 0 else -2
        y = 0 if n == 1 else (2 if bits[0] == 0 else -2)
        out.append((x, y, bits))
    return out


def _head(truth_table: str, bits: list[int]) -> str:
    """Build the A Painter Ant head for a one-, two-, or three-input table.

    The head paints every leaf and returns to the origin.  For one and two
    inputs the cycle-2 ant dances on the pre-painted stars: an uppercase
    prefix fires it from the output leaf onto the ring -- ``N`` onto the
    top-middle cell, where the following moves flow horizontally, or ``W``
    onto the middle-left cell, where they flow vertically.  A leafward
    move from either cell would split the ants: a south move from the
    top-middle returns the black-output ant to the leaf while the
    white-output ant stays on the ring (and symmetrically an east move
    from the middle-left), so the dance alternates the two cells through
    the ring's diagonals, and only the ``Ssn`` ending may move leafward
    (``S`` fires a white output onto the leaf, ``s`` moves a black one
    onto it).  For three inputs it walks the two leaf rows, detouring onto
    the clean outer row to cross from the west half to the east half of
    each row (the cycle-2 dance for that layout is still open, see
    ``docs/a_painter_ant_generator.md``).
    """
    n = len(bits)
    if n == 3:
        # Two rows at y = +-2: walk each row west, painting the leaves,
        # detour one cell outward to the clean row, cross east, walk the
        # row west again, and return to the origin (cycle 1 only; the
        # cycle-2 dance for this layout is still open -- see
        # docs/a_painter_ant_generator.md).
        out: list[str] = []
        for b0 in (1, 0):
            detour = "n" if b0 else "s"
            cross = "s" if b0 else "n"
            back = "sss" if b0 else "nnn"
            row_bits: list[list[int]] = [
                [b0, 1, 0],
                [b0, 0, 0],
                [b0, 1, 1],
                [b0, 0, 1],
            ]
            out.append("nn" if b0 else "ss")
            out.append("ww" + _leaf_color(truth_table, row_bits[0]))
            out.append("wwww" + _leaf_color(truth_table, row_bits[1]))
            out.append(
                detour + "e" * 12 + cross + _leaf_color(truth_table, row_bits[2])
            )
            out.append("wwww" + _leaf_color(truth_table, row_bits[3]))
            out.append(detour + "ww" + back)
        return "".join(out)

    # The cycle-2 dance circuits, one ``prefix + leg`` pair per leaf plus
    # the return leg; every leg is a no-op from its dance cell:
    #   n == 1: leaf -N-> top -W-> west diag -E-> top -S/s-> leaf
    #   n == 2: leaf -W-> middle-left -N-> NW diag -E-> top-middle
    #           -E-> NE diag -W-> top-middle -S/s-> leaf
    # A leafward move from the top-middle (south) or the middle-left (east)
    # would split the ants -- the black-output ant returns to the leaf
    # while the white-output ant stays on the ring -- so the legs dancing
    # on those cells (``nnww`` on the middle-left, ``nnnn``/``nnee`` on the
    # top-middle) never move leafward, and only the ``Ssn`` ending may.
    prefixes: tuple[str, ...]
    legs: tuple[str, ...]
    if n == 1:
        prefixes = ("N", "W", "E")
        legs = ("ww", "eeee", "ww")
    else:
        prefixes = ("W", "N", "E", "E", "W")
        legs = ("nnww", "sseessee", "nnnn", "sswwssww", "nnee")

    out = [prefixes[0]]
    for i, (_x, _y, leaf_bits) in enumerate(_leaf_positions(n)):
        if i:
            out.append(prefixes[i])
        out.append(legs[i])
        out.append(_leaf_color(truth_table, list(leaf_bits)))
    out.append(prefixes[len(legs) - 1])
    out.append(legs[-1])
    out.append("Ssn")
    return "".join(out)


def _body(n: int = 2) -> str:
    """Generate the routing body for ``n`` inputs.

    For ``n == 2`` the body paints two two-layer stars -- one around the
    output leaf and one around its y-mirror -- so the final input never has
    to be re-embedded: it only routes to whichever star is already painted.
    Each star is walked as a clockwise spiral of ``P`` paints (the ring
    cells at distance 1 and the axis cells at distance 2), and the two
    stars are connected by the black gap between their rings: the star
    centres are four cells apart and each ring reaches one cell toward the
    other, so the gap is ``4 - 2`` east moves on the row above.  The body
    starts and ends on the shared cell at ``(0, +-2)`` -- the canonical
    point the final input's east/west routing leaves from -- and its
    blocked-uppercase returns are the anchors of the cycle-2 dance.

    For ``n == 3`` the body paints the output row's cells that the
    ``{X1}``/``{X2}`` dances cross (one ring or axis cell per leaf, walked
    around the leaves on the clean row above) -- enough for cycle 1; the
    full stars and the cycle-2 dance are still open (see
    ``docs/a_painter_ant_generator.md``).
    """
    if n == 3:
        out: list[str] = []
        x = 0
        for tx in (-1, -3, -4, -5, -7, 1, 3, 4, 5, 7, 0):
            out.append("n")
            out.append(("e" if tx > x else "w") * abs(tx - x))
            out.append("s")
            out.append("P")
            x = tx
        return "".join(out)

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
        # The n == 3 two-row construction exists (_head/_body build it and
        # it is cycle-1 exact on every table), but the cycle-2 dance is
        # still an open problem (docs/a_painter_ant_generator.md), and the
        # boolean harness requires every program to be a cycle-stable fixed
        # point.
        raise ValueError(
            "the A Painter Ant boolean generator supports n == 1 and n == 2; "
            "n >= 3 is an open problem (see docs/roadmap.md)",
        )

    # The head paints every leaf; the body paints the two stars; the first
    # n-1 inputs route north/south before the body, and the final
    # (least-significant) input routes east/west onto its leaf after it.
    head = _head(truth_table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"

    return head + prefix + _body() + suffix


def instantiate(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's ``{Xi}`` placeholders.

    For one- and two-input templates every input except the final one routes
    north/south (``nn`` for a one bit, ``ss`` for a zero) and the final
    (least-significant) input routes east/west (``WWwWWEEe`` for a one,
    ``NENEESWw`` for a zero).  For a three-input two-row template ``b0``
    routes north/south to the output row and ``b1``/``b2`` route east/west
    onto the inner/outer leaf with the ``E``/``e`` (or ``W``/``w``) landing
    dual.  ``bits`` must match the template built by
    :func:`a_painter_ant`.
    """
    from esolangs.tools.booleans.parameterized import instantiate as _sub

    if len(bits) == 3:
        # n == 3 two-row template: b0 routes north/south to the output
        # row, b1 routes east/west to the inner leaf (``EEe``/``WWw``), and
        # b2 routes east/west to the outer leaf (``EEEEe``/``WWWWw``), each
        # landing with the E/e (or W/w) dual so both output colours land
        # on the leaf.
        return _sub(
            template,
            bits,
            lambda i, bit: (
                ("nn" if bit else "ss")
                if i == 0
                else (
                    ("EEe" if bit else "WWw")
                    if i == 1
                    else ("EEEEe" if bit else "WWWWw")
                )
            ),
            lambda _i, _b: "",
        )

    return _sub(
        template,
        bits,
        lambda i, bit: (_XF[bit] if i == len(bits) - 1 else _X0[bit]),
        lambda _i, _b: "",
    )
