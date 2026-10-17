"""Codesick Boolean program generator: a shared decision diagram.

Every ``in`` is the input, so ``in`` names the one variable the program
writes, holding the bits not yet read.  Node ``c`` appends its marker
``#c``; the only ``#`` in the string then sits after the last unread
bit, so ``0#c`` occurs in it exactly when that bit is ``0``.  A hit
deletes ``0#c`` -- the bit and the marker -- and jumps to the label
``0#c``, which finds ``0#c`` gone and jumps to the 0-child.  A miss
jumps to ``1#c``, which deletes ``1#c``, jumps to itself, misses, and
jumps to the 1-child.  Bits are read last first, so the diagram is the
one of the bit-reversed table.  Labels are ``subtree_ids`` ids; constant
subtables print and jump to the missing label ``*``; a constant table
first takes its input in a test that misses.

Size:
    O(T) size and build time, three instructions per diagram node, at most
    3n + 1 steps; n=10 parity: 1,631 chars, n=10 random 1847: 22,728 chars.

Decisions:
    An ignored input keeps a delete node per residual: 0.52x a real one at n=8.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def codesick(truth_table: str) -> str:
    """Build a Codesick program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    rows = range(len(truth_table))
    reverse = [int(format(row, f"0{n}b")[::-1], 2) if n else 0 for row in rows]
    ids = subtree_ids("".join(truth_table[reverse[row]] for row in rows))
    lines: dict[int, list[str]] = {}
    frontier = {0}
    for depth in range(n + 1):
        below: set[int] = set()
        for k in sorted(frontier):
            c = ids[depth][k]
            if c in lines:
                continue
            if c < 2:
                lines[c] = [f"{c} codesick out {c} * *;"]
                continue
            zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
            lines[c] = [
                f"{c} codesick in #{c} 0#{c} 1#{c};",
                f'0#{c} codesick in "" 0#{c} {zero};',
                f'1#{c} codesick in "" 1#{c} {one};',
            ]
            below |= {2 * k, 2 * k + 1}
        frontier = below
    # A constant table still takes its input, through a test that misses.
    start = [f'codesick in "" * {ids[0][0]};'] if ids[0][0] < 2 else []
    # Spaces, not newlines: one line per instruction is too short to wrap.
    return " ".join([*start, *(line for node in lines.values() for line in node)])


LANGUAGE = Language(
    "Codesick",
    "codesick",
    category="other",
    boolean=codesick,
    contract=BooleanContract(input_shape="char_stream"),
    eof="the whole input is read once to replace every `in`; no read meets EOF",
    # An argument holds no whitespace, so break only between arguments.
    wrap=wrap_space_delimited,
)
