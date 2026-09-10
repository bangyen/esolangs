"""Boolean-function generator for Alight.

The construction is *derived*: the wiki has no truth machine to copy, and
the page is marked unimplemented, so nothing here is transliterated.

What Alight gives that the other grid languages do not is an indexable list
with an *out-of-line* index -- ``at{list, index}`` takes the index as an
expression rather than as a walk.  So the truth table needs no branching at
all: encode it as a string literal, fold the input bits into its row number,
and read the answer out.

    row = ((b0 * 2 + b1) * 2 + b2) ...

which is Horner's rule, and it is spelled directly as
``set i i*2+a-48`` because expressions evaluate strictly left to right --
the same reading the wiki's own ``len{l}-0.5`` forces.  Each input costs one
``inp`` and one ``set``, so the program is O(n) commands over an O(2**n)
table literal, with no decision tree, no leaves and no turns: it is one
straight eastward line.

That shape is why ``alight`` sits in the contract test's ``_UNSHAPED`` list
alongside ``ztoalc_l``.  Both are branch-free lookups, so there are
no subtrees to collapse and a one-dependency table renders the same length
as parity -- a 0% fold that is the construction working, not regressing.

The reads are unconditional and come before the lookup, so every table of a
given arity consumes exactly ``n`` inputs, whatever the table says.
"""

from esolangs.tools.boolean.helpers import _ASCII_ZERO, _validate_truth_table

__all__ = ["alight"]


def alight(truth_table: str) -> str:
    """Return an Alight program printing ``truth_table``'s entry for its input.

    Reads ``n`` characters (one per line, ``'0'`` or ``'1'``), folds them
    into the table's row index by Horner's rule, and prints the table
    character at that row.

    The table is a string literal indexed by ``at``, so the emitted program
    has no branches: its length is ``O(2**n)`` in the literal plus ``O(n)``
    in the reads, and it is a single line of commands running east from
    ``begin``.
    """
    n = _validate_truth_table(truth_table)

    # ``i`` accumulates the row index; ``a`` holds the digit just read.  A
    # digit arrives as its character code, so each read is normalized by
    # subtracting ``'0'`` -- the same offset every generator here spends.
    commands = ["begin", "var a", "var i", "var r"]
    for k in range(n):
        commands.append("inp a")
        # Horner: the first bit seeds the accumulator, each later one
        # doubles it and adds itself.  Left-to-right evaluation is what
        # makes ``i*2+a-48`` mean ``((i*2)+a)-48`` without parentheses,
        # which Alight has none of.
        if k == 0:
            commands.append(f"set i a-{_ASCII_ZERO}")
        else:
            commands.append(f"set i i*2+a-{_ASCII_ZERO}")
    # Indices run 0.5, 1.5, ... so the row number is offset by a half.
    commands.append(f'set r at{{"{truth_table}", i+0.5}}')
    commands.append("out r")
    commands.append("end")
    return ";".join(commands) + ";"
