"""Build a Line program computing a given boolean truth table directly.

Unlike :mod:`bf_to_line` (which compiles an existing brainfuck program),
this builds a :class:`render.Node` tree straight from the truth table --
there is no brainfuck intermediate at all, and none is needed: Line's ``i``
reads a whole number into the current cell and ``o`` prints the current
cell as a number (see :mod:`simulate`'s module docstring for both), so a
0/1 input is already exactly what a caller's ``IO.read`` should hand back,
and a 0/1 result is already exactly what ``IO.write`` receives -- no ASCII
offset ever enters the picture.  This is the reason the text generator
(``esolangs.tools.text.tape.brainfuck``) was dropped from scope and the
brainfuck boolean generator's ``+48``/``+49`` encoding (needed only because
brainfuck's own ``,``/``.`` are byte-oriented) was never ported over either:
compiling that encoding through to Line would print 48/49, not 0/1, and
there is nothing to "strip" -- the fix is to not introduce brainfuck's
byte convention in the first place, by building the decision tree directly
against Line's own integer-valued ``i``/``o``.

The generated program: read each of the ``n`` inputs into its own cell
(``i``, ``>``, ``i``, ``>``, ...), move back to cell 0, then a ``?``-fork
decision tree ``n`` levels deep -- one fork per input bit, in reading
order -- with each of the ``2**n`` leaves moving to a fresh cell, building
that combination's table entry there with ``+`` (0 or 1 increments), and
printing it with ``o``.

Matches this repo's existing boolean generators' calling convention (e.g.
``esolangs.tools.boolean.tape.brainfuck``): ``truth_table`` is a binary
string of length ``2**n`` indexed by the inputs, most significant first.

**Practical size limit**: ``render.py``'s ``_layout`` spaces sibling fork
arms far enough apart that a decision tree's own branches never re-converge
on an ancestor fork's arms.  Arms used to be sized geometrically (roughly
doubling per remaining nesting level), which made the canvas grow sharply
with ``n`` -- n=3 rendered at roughly 9000x4000px and n=4 at roughly
17000x9000px, large enough to trip Pillow's default decompression-bomb
warning.  Arms are now sized from each subtree's *measured* extent (see
``render.py``'s ``_subtree_extent``/``_arm_spacing``), which shrinks that
dramatically: n=2 at 900x1100, n=3 at 1820x1440, n=4 at 1960x2160.

**The n<=4 ceiling this file used to document is gone**, and was an artifact
of the old spacing rather than anything about decision trees.  Measured end
to end (render -> extract -> simulate, every input combination checked
against the truth table) after the change:

===  ===========  ==========  =======  ==========
 n   canvas       extract     combos   result
===  ===========  ==========  =======  ==========
 4   2000x2260      0.4s        16     all correct
 5   4000x2620      1.0s        32     all correct
 6   4160x4000      1.5s        64     all correct
 7   8160x4340      4.0s       128     all correct
===  ===========  ==========  =======  ==========

For scale, n=5 was previously projected at roughly 35000x17000px and called
impractical; it is 4000x2620 and extracts in a second.  n=7 renders 35Mpx,
which exceeds Pillow's default decompression-bomb threshold -- a caller
reading such an image back must raise ``Image.MAX_IMAGE_PIXELS`` (as the
measurement above did), which is a Pillow default rather than a limit of
this generator.

Nothing here is enforced, and n=8 upward is simply untested rather than
known-bad -- the growth is roughly 2x area per input, so the practical limit
is now whatever canvas and extraction time a caller will tolerate.
"""

from __future__ import annotations

from render import Node, chain


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A valid table has ``2**n`` binary entries, so ``n`` is recovered from
    the length (a power of two) rather than taken as a separate parameter --
    matching every boolean generator in ``esolangs.tools.boolean``.
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


def line_boolean(truth_table: str) -> Node:
    """Build a Line program computing ``truth_table`` (see module docstring).

    Returns a :class:`render.Node` graph ready for :func:`render.render`,
    not text -- Line has no text format (see ``WIP.md``), so this fills the
    same role a text-emitting generator would for a language whose registry
    entry needs source text.
    """
    n = _validate_truth_table(truth_table)

    # Read n inputs into cells 0..n-1, one `i` per cell, `>` between them.
    head = Node("i")
    tail = head
    for _ in range(n - 1):
        move = Node(">")
        tail.next = move
        read = Node("i")
        move.next = read
        tail = read
    # Walk back to cell 0 so the decision tree tests bits in reading order.
    for _ in range(n - 1):
        move = Node("<")
        tail.next = move
        tail = move

    def leaf(bits: str) -> Node:
        value = truth_table[int(bits, 2)]
        ops = [">", *(["+"] if value == "1" else []), "o"]
        return chain(*ops)

    def fork(bits: str, depth: int) -> Node:
        if depth == n:
            return leaf(bits)

        def branch(bit: str) -> Node:
            sub = fork(bits + bit, depth + 1)
            if depth + 1 < n:
                # Advance to the next input's cell before testing it.
                move = Node(">")
                move.next = sub
                return move
            return sub

        node = Node("?")
        node.zero = branch("0")
        node.nonzero = branch("1")
        return node

    tail.next = fork("", 0)
    return head


if __name__ == "__main__":
    import sys

    from render import render

    tt = sys.argv[1] if len(sys.argv) > 1 else "0001"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "line_bool_out.png"
    render(line_boolean(tt)).save(out_path)
    print(f"wrote {out_path}")
