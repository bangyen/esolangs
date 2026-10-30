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
first takes its input in a test that misses.  Either bit may be the
tested one: its label ``b#c`` is the instruction of a child no other
edge reaches, else a forwarder or, for a constant, the print itself; a
constant on the missed side is jumped to without the delete node.

Size:
    O(T) size and build time, at most three instructions per diagram node,
    at most 3n - 1 steps; n=10 parity: 1,544 chars, n=10 random 1847: 18,181 chars.

Decisions:
    An ignored input keeps a delete node per residual: 0.52x a real one at n=8.
"""

from collections import Counter

from esolangs.generation.helpers import (
    _validate_truth_table,
    reflected_table,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.codesick.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


def codesick(truth_table: str) -> str:
    """Build a Codesick program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(reflected_table(truth_table, n))
    kids: dict[int, tuple[int, int]] = {}
    frontier = {0}
    for depth in range(n + 1):
        below: set[int] = set()
        for k in sorted(frontier):
            c = ids[depth][k]
            if c < 2 or c in kids:
                continue
            kids[c] = (ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1])
            below |= {2 * k, 2 * k + 1}
        frontier = below
    if not kids:
        # A constant table still takes its input, through a test that misses.
        c = ids[0][0]
        return f'codesick in "" * {c}; {c} codesick out {c} * *;'
    parents = Counter(c for pair in kids.values() for c in pair)
    entry = {0: "0", 1: "1"} | {c: str(c) for c in kids}
    hit: dict[int, int] = {}
    for p, pair in kids.items():
        # The hit side costs a forwarder unless its child has this edge alone
        # and takes the hit label as its own; the miss side costs a delete
        # node unless its child is constant.
        hit[p] = min(
            (0, 1),
            key=lambda b: (
                (pair[b] < 2 or parents[pair[b]] > 1) + (pair[1 - b] >= 2),
                b,
            ),
        )
        if pair[hit[p]] >= 2 and parents[pair[hit[p]]] == 1:
            entry[pair[hit[p]]] = f"{hit[p]}#{p}"
    lines: list[str] = []
    printed: set[int] = set()
    for p, pair in kids.items():
        b = hit[p]
        h, m = pair[b], pair[1 - b]
        miss = str(m) if m < 2 else f"{1 - b}#{p}"
        lines.append(f"{entry[p]} codesick in #{p} {b}#{p} {miss};")
        if entry[h] != f"{b}#{p}":
            # The hit label forwards, or prints in place of the constant.
            lines.append(
                f"{b}#{p} codesick out {h} * *;"
                if h < 2
                else f'{b}#{p} codesick in "" {b}#{p} {entry[h]};'
            )
        if m < 2:
            printed.add(m)
        else:
            lines.append(f'{1 - b}#{p} codesick in "" {1 - b}#{p} {entry[m]};')
    lines += [f"{c} codesick out {c} * *;" for c in sorted(printed)]
    # Spaces, not newlines: one line per instruction is too short to wrap.
    return " ".join(lines)


LANGUAGE = Language(
    "Codesick",
    "codesick",
    category="other",
    boolean=codesick,
    contract=BooleanContract(input_shape="char_stream"),
    eof="the whole input is read once to replace every `in`; no read meets EOF",
    # An argument holds no whitespace, so break only between arguments.
    wrap=wrap_space_delimited,
    proof_workspace=(workspace, False, (3, 4, 5, 6, 7)),
)
