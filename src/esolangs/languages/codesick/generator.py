"""Codesick Boolean program generator: a shared decision diagram.

Every ``in`` is the input, so ``in`` names the one variable the program
writes, holding the bits not yet read.  Node ``c`` appends its marker
``c``, a non-bit word, after the last unread bit, so ``0c`` occurs
exactly when that bit is ``0``. A hit deletes ``0c`` and jumps to
label ``0c``, which finds it gone and jumps to the 0-child. A miss
jumps to ``1c``, which deletes ``1c``, jumps to itself, misses, and
jumps to the 1-child.  Bits are read last first, so the diagram is the
one of the bit-reversed table.  Frequent references get shorter names; constant
subtables print and jump to the missing label ``*``; a constant table
reads its input during loading through the output instruction dereference.
Either bit may be the
tested one: its label ``bc`` is the instruction of a child no other
edge reaches, else a forwarder or, for a constant, the print itself; a
constant on the missed side is jumped to without the delete node.

Size:
    O(T) size and build time, at most three instructions per diagram node,
    at most 3n - 1 steps; constants: 22 chars and one step.
    n=10 parity: 1,317 chars, n=10 random 1847: 14,942 chars.

Decisions:
    An ignored input keeps a delete node per residual: 0.52x a real one at n=8.
"""

from collections import Counter
from string import ascii_letters, digits, punctuation

from esolangs.generation.helpers import (
    _validate_truth_table,
    reflected_table,
    subtree_ids,
)
from esolangs.languages.codesick.descriptor import LANGUAGE as LANGUAGE

# Non-bit ASCII words keep bit+marker tests unique without a # separator.
_ALPHABET = "".join(
    c for c in ascii_letters + digits + punctuation if c not in '01#*;"'
)


def _name(index: int) -> str:
    letters = []
    while index:
        index, digit = divmod(index - 1, len(_ALPHABET))
        letters.append(_ALPHABET[digit])
    return "".join(reversed(letters))


def _names(kids: dict[int, tuple[int, int]], parents: Counter[int]) -> dict[int, str]:
    """Name frequent references first, using linear-size frequency buckets."""
    # [ablations.trick_prototype_20261102_dense_names]
    buckets: list[list[int]] = [[] for _ in range(2 * len(kids) + 1)]
    for node in kids:
        buckets[parents[node]].append(node)
    names = {}
    index = 1
    for group in reversed(buckets):
        for node in group:
            while _name(index) in ("in", "out", "codesick"):
                index += 1
            names[node] = _name(index)
            index += 1
    return names


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
        # Loading resolves `in` before output; the dereference writes no new value.
        return f"codesick out {ids[0][0]} in * *;"
    parents = Counter(c for pair in kids.values() for c in pair)
    names = _names(kids, parents)
    entry = {0: "0", 1: "1"} | names
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
            entry[pair[hit[p]]] = f"{hit[p]}{names[p]}"
    lines: list[str] = []
    printed: set[int] = set()
    for p, pair in kids.items():
        b = hit[p]
        h, m = pair[b], pair[1 - b]
        miss = str(m) if m < 2 else f"{1 - b}{names[p]}"
        lines.append(f"{entry[p]} codesick in {names[p]} {b}{names[p]} {miss};")
        if entry[h] != f"{b}{names[p]}":
            # The hit label forwards, or prints in place of the constant.
            lines.append(
                f"{b}{names[p]} codesick out {h} * *;"
                if h < 2
                else f'{b}{names[p]} codesick in "" {b}{names[p]} {entry[h]};'
            )
        if m < 2:
            printed.add(m)
        else:
            lines.append(
                f'{1 - b}{names[p]} codesick in "" {1 - b}{names[p]} {entry[m]};'
            )
    lines += [f"{c} codesick out {c} * *;" for c in sorted(printed)]
    # Spaces, not newlines: one line per instruction is too short to wrap.
    return " ".join(lines)
