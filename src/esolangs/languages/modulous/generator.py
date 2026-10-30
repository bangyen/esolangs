"""Modulous Boolean program generator: the table is a pushed string literal.

``PSH STR`` pushes the table so entry 0 is on top.  Each input is read and
added into a counter at its weight (an ignored input is read and popped), then
a ``JMP`` loop discards one entry per count and prints the entry left on top.
A symmetric table counts its inputs at weight 1 over n + 1 entries
([ablations.symmetric_count]).

Size:
    T + a few dozen characters per input; one loop step per row index.
    n=10 random 1847: 1,605 chars, n=12 random 1847: 4,781 chars.

Decisions:
    A string literal has no subtrees to fold or share.  Letting the first
    read be the counter saves 6.8% at n=6, 4.1% at n=8, 1.9% at n=10, under
    the 10% bar.
"""

import re
from math import isqrt

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _BRACKET_LITERAL,
    _bracket_literal,
    balance_score,
    wrap_space_delimited,
)
from esolangs.registry._language import Language, Shape

# Characters around the table in its literal push: ``[PSH STR "`` opens it
# (10 chars) and ``"]`` closes the literal (2 chars).
_TABLE_PUSH_OVERHEAD = len('[PSH STR ""]')

# Narrowest chunk width: ``[ PSH STR`` (9 characters) needs its own row.
_MIN_CHUNK_WIDTH = 6

# A bracketed string literal with its closer, a mnemonic, a number or a glyph.
_TOKEN = re.compile(r'"[^"]*"\]|[A-Z]+|\d+|\S')


def modulous(truth_table: str, width: int | None = None) -> str:
    """Return a Modulous table lookup; ``width`` folds command whitespace.

    Literals are chunked to fit; each quoted chunk keeps its closing bracket.
    """
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is on
    # top and discarding ``index`` of them uncovers ``truth_table[index]`` --
    # the row index read MSB first, which is what the weights below build.  A
    # pushed zero is the counter; an ignored input is read and popped, and the
    # table is indexed by the rest.
    builds = [input_weights(truth_table, n), symmetric_weights(truth_table, n)]
    return min(
        (_lookup(*build, width) for build in builds if build is not None), key=len
    )


def _lookup(weights: list[int], truth_table: str, width: int | None) -> str:
    """Return the literal push, the weighted reads and the discard walk."""
    reads = ["[PSH INT 0]"]
    for weight in weights:
        if weight:
            reads.append(f"[INP INT][JMP F 4 IF 0][POP][ADD {weight}][JMP F 2][POP]")
        else:
            reads.append("[INP INT][POP]")
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT STR][END]"
    program = f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'
    if width is None:
        return program
    wrapped = _bracket_literal(program, width)
    if grid_width(wrapped) <= width:
        return wrapped
    # Push chunks from last to first: each string itself pushes in reverse.
    # All jumps follow the prologue and are relative, so its length is free.
    chunk = max(1, width - 3)
    starts = range(0, len(truth_table), chunk)
    prologue = (
        "".join(f"[PSH INT {_ASCII_ZERO + int(bit)}]" for bit in reversed(truth_table))
        if width < 4
        else "".join(
            f'[PSH STR "{truth_table[start : start + chunk]}"]'
            for start in reversed(starts)
        )
    )
    tokens = _TOKEN.findall(prologue + "".join(reads) + walk)
    return wrap_space_delimited(" ".join(tokens), width)


def _chunked_columns(size: int, suffix_lengths: list[int]) -> int:
    """Square width ``w^2 = 4 size + 2 S`` of the chunked table, suffix ``S``.

    Within 1.5% of the swept side at n=2..12 (test oracle).
    """
    suffix = sum(suffix_lengths) + len(suffix_lengths)
    return max(_MIN_CHUNK_WIDTH + 3, isqrt(4 * size + 2 * suffix) + 1)


def _balance(table: str, default: str) -> str:
    """Return the squarest rendering of the table lookup program.

    Keeps the ``balance_score`` minimum of the unwrapped ``default``, whole
    bracket atoms (``[PSH STR "…"]`` intact) at the optimal greedy width above
    the longest atom, and the chunked table at four widths around
    ``_chunked_columns``.  Numeric, narrow (4-8) and whole-literal widths never
    won on 488 tables at n=1..12 (``[ablations.balance_dead_widths]``).
    """
    atoms = re.findall(_BRACKET_LITERAL, default)
    floor = max(map(len, atoms))
    width = balanced_token_width(atoms, minimum=floor)
    candidates = [default, modulous(table, width)]
    size = len(table)
    # Skip the ``[PSH STR "`` prologue, the table, and the ``"]`` closer: the
    # rest is the instruction suffix the chunked rows pack beside the pushes.
    suffix = _TOKEN.findall(default[size + _TABLE_PUSH_OVERHEAD :])
    centre = _chunked_columns(size, list(map(len, suffix)))
    candidates.extend(modulous(table, centre + offset) for offset in (-3, -1, 1, 3))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Modulous",
    "modulous",
    category="stack_based",
    random=True,
    boolean=modulous,
    # Not a tree: pops a ``PSH STR`` table down to the indexed character.
    shape=Shape.LOOKUP,
    balance=_balance,
)
