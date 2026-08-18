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

The construction paints the four decision-tree leaves and routes the ant to
the leaf for its inputs.  The ``head`` paints one leaf per input combination
and returns to the origin; each leaf is painted ``P`` (white) for a one
table entry and left unpainted (a space, ignored by the interpreter) for a
zero.  Only ``P`` is ever used -- the generator never paints a cell black --
so the white cells are monotone increasing: cycle 1 establishes them and
every later cycle only re-confirms a subset, which is what makes the
programs cycle-stable.  The ``body`` then funnels the ant (from whichever
corner it ends cycle 2 at) to a canonical routing point, and the ``{X1}``
embedding does the final east/west route onto the output leaf.

The two ``{X0}`` embeddings move the ant north (``nn``) or south (``ss``);
the two ``{X1}`` embeddings route east/west: ``WWwWWEEe`` for a one bit and
``NENEESWw`` for a zero, an 8-character complement pair that lands on the
opposite-coloured leaf.  Every table of two inputs is supported and every
instantiated program is a cycle-stable fixed point (the bounding box is
identical for any whole number of cycles).

``n == 1`` uses a dedicated two-leaf head: the template paints only the
``f(0)`` and ``f(1)`` leaves and carries a single ``{X0}`` placeholder, which
:func:`instantiate` fills with the ``WWwWWEEe``/``NENEESWw`` routing onto the
``f(b0)`` leaf.  ``n >= 3`` is still open (``docs/roadmap.md``) and raises
:class:`ValueError`.
"""

from esolangs.tools.booleans.helpers import _validate_truth_table

__all__ = ["a_painter_ant"]

# The fixed routing body between the two input slots: it paints the ring and
# funnels the ant to the canonical pre-``{X1}`` routing point.
_BODY = "NwPnPwnPEsPwPswPWWePsPesPSSnPePeePNNsePSSnPePnePEEwPnPwnPNNsPwPsPwPS"

# ``{X0}``: first input (most significant) routes north/south.
_X0 = {1: "nn", 0: "ss"}
# ``{X1}``: second input routes east/west onto the output leaf.
_X1 = {1: "WWwWWEEe", 0: "NENEESWw"}


def _leaf_color(truth_table: str, b0: int, b1: int) -> str:
    """Return the ``P``/space to paint the leaf for inputs (``b0``, ``b1``)."""
    return "P" if truth_table[(b0 << 1) | b1] == "1" else " "


def a_painter_ant(truth_table: str) -> str:
    """Build an A Painter Ant template for a one- or two-input Boolean function.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.  The
    returned template contains ``{X0}`` and ``{X1}`` placeholders that
    :func:`~esolangs.tools.booleans.parameterized.instantiate` fills with
    the per-bit routing.  The answer is the colour of the cell the ant lands
    on after a cycle (white is one, black is zero).

    Every one- and two-input table is supported; ``n >= 3`` raises
    :class:`ValueError` (an open problem, see ``docs/roadmap.md``).  A
    one-input table produces a two-leaf template carrying only ``{X0}``,
    which :func:`instantiate` fills with the ``b0`` routing onto the
    ``f(b0)`` leaf.
    """
    n = _validate_truth_table(truth_table)
    if n == 1:
        # Two-leaf head: paint f(0) and f(1) at the two positions the
        # east/west routing (WWwWWEEe / NENEESWw) lands on, then body and a
        # single {X0} that instantiate fills with that per-bit routing.
        f0 = _leaf_color(truth_table, 0, 0)
        f1 = _leaf_color(truth_table, 0, 1)
        head = f"Nww{f1}eeee{f0}wwSsn"

        return head + _BODY + "{X0}"
    if n != 2:
        raise ValueError(
            "the A Painter Ant boolean generator supports n == 1 and n == 2; "
            "n >= 3 is an open problem (see docs/roadmap.md)",
        )

    # Paint the four leaves (order in the head: f(1,1), f(0,0), f(1,0), f(0,1)).
    f11 = _leaf_color(truth_table, 1, 1)
    f00 = _leaf_color(truth_table, 0, 0)
    f10 = _leaf_color(truth_table, 1, 0)
    f01 = _leaf_color(truth_table, 0, 1)
    head = f"Nnnww{f11}Wsseessee{f00}Ennwwnnee{f10}Esswwssww{f01}WnneeSsn"

    return head + "{X0}" + _BODY + "{X1}"


def instantiate(template: str, bits: list[int]) -> str:
    """Fill an A Painter Ant template's ``{X0}``/``{X1}`` placeholders.

    ``{X0}`` becomes ``nn`` for a one bit and ``ss`` for a zero (the first
    input, most significant); ``{X1}`` becomes ``WWwWWEEe`` for a one and
    ``NENEESWw`` for a zero (the second input).  ``bits`` must have length 2
    (or length 1 for an ``n == 1`` template, whose single ``{X0}`` is filled
    with the ``WWwWWEEe``/``NENEESWw`` routing -- see
    :func:`a_painter_ant`).
    """
    from esolangs.tools.booleans.parameterized import instantiate as _sub

    if len(bits) == 1:
        # n == 1 template: its single {X0} takes the east/west routing.
        return _sub(
            template,
            bits,
            lambda _i, bit: _X1[bit],
            lambda _i, _b: "",
        )

    return _sub(
        template,
        bits,
        lambda i, bit: (_X0[bit] if i == 0 else _X1[bit]),
        lambda _i, _b: "",
    )
