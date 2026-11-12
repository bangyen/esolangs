"""Modulous Boolean program generator: the table is a pushed string literal.

Constants and one-input tables use scalar readers. Otherwise ``PSH STR``
pushes a lookup with entry 0 on top. Symmetric tables count over n + 1 entries;
up to four essential inputs discard entries directly. Larger asymmetric tables
pack row pairs, decoded by the final essential input. From six essential inputs,
higher weights accumulate a counter for a ``JMP`` walk; suffix reads discard
entries directly. Ignored inputs are read and popped before output.

Size:
    Worst case: 6T+28n+21 chars at n=2..4, 3T+28n+144 at n=5;
    from n=6, T/2+O(n²) chars including decimal weights.
    n=8 zero: 138 chars; n=10 random 1847: 1,165 chars,
    n=12 random 1847: 2,804 chars.

Decisions:
    The tail retains every ignored input in order, before output.
"""

import re
from collections.abc import Sequence
from math import isqrt

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _BRACKET_LITERAL,
    _bracket_literal,
    balance_score,
    wrap_space_delimited,
)
from esolangs.runtime._program import Program

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
    projected = input_weights(truth_table, n)
    if not any(projected.weights) or n == 1:
        # [ablations.constant_table_audit_20261101]: scalar paths need no table.
        if not any(projected.weights):
            program = (
                "[INP INT][POP]" * n
                + f"[PSH INT {_ASCII_ZERO + int(truth_table[0])}][PRT STR][END]"
            )
        elif truth_table[0] == "0":
            program = "[INP INT][ADD 48][PRT STR][END]"
        else:
            program = (
                "[INP INT][JMP F 3 IF 0][SUB 1][JMP F 2][ADD 1][ADD 48][PRT STR][END]"
            )
        if width is None:
            return program
        wrapped = _bracket_literal(program, width)
        if grid_width(wrapped) <= width:
            return wrapped
        return wrap_space_delimited(" ".join(_TOKEN.findall(program)), width)
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is not None:
        # The count reader preserves O(n) source on symmetric functions.
        return _lookup(*symmetric, width)
    # Counter-free direct tails are faster through four essential inputs;
    # pairing starts where the weighted reader otherwise needs its walk.
    if sum(weight > 0 for weight in projected.weights) <= 4:
        return _lookup(*projected, width)
    return _pair_lookup(*projected, width)


def _pair_lookup(weights: Sequence[int], table: str, width: int | None) -> str:
    """Select a pair by high bits, then decode its last input without rereading."""
    # 00/11 are already ASCII answers; 01/10 encode as ASCII 2/3.
    codes = {"00": "0", "11": "1", "01": "2", "10": "3"}
    packed = "".join(codes[table[i : i + 2]] for i in range(0, len(table), 2))
    slot = weights.index(1)
    prefix = _lookup([w // 2 for w in weights[:slot]], packed, None)
    prefix = prefix.removesuffix("[PRT STR][END]")
    # At bit1, 2->1 and 3->0; at bit0, 2->0 and 3->1.
    # Relative targets are fixed command offsets, unaffected by literal folds.
    decode = (
        "[INP INT][JMP F 9 IF 0][POP][JMP F 3 IF 50]"
        "[JMP F 4 IF 51][JMP F 10][SUB 1][JMP F 8][SUB 3]"
        "[JMP F 6][POP][JMP F 3 IF 50][JMP F 2 IF 51]"
        "[JMP F 2][SUB 2]"
    )
    program = prefix + decode + "[INP INT][POP]" * (len(weights) - slot - 1)
    return _fit(program + "[PRT STR][END]", packed, width)


def _lookup(weights: Sequence[int], truth_table: str, width: int | None) -> str:
    """Return the literal push, the weighted reads and the discard walk."""
    # Local tails win through weight4. With at most four essential inputs,
    # unrolling8 also removes the counter/walk:37 chars saved;16 loses22.
    # Keep the entire suffix in input order, including ignored inputs.
    # [ablations.trick_prototype_20261102_tail_reads]
    split = (
        0
        if max(weights, default=0) <= 8
        else max(i + 1 for i, weight in enumerate(weights) if weight > 4)
    )
    reads = ["[PSH INT 0]"] if split else []
    for weight in weights[:split]:
        if weight:
            reads.append(f"[INP INT][JMP F 4 IF 0][POP][ADD {weight}][JMP F 2][POP]")
        else:
            reads.append("[INP INT][POP]")
    tail = [
        f"[INP INT][JMP F {weight + 1} IF 0]" + "[POP]" * (weight + 1)
        if weight
        else "[INP INT][POP]"
        for weight in weights[split:]
    ]
    # With no prefix the counter is identically zero: omit it and its walk.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP]" if split else ""
    walk += "".join(tail) + "[PRT STR][END]"
    program = f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'
    return _fit(program, truth_table, width)


def _fit(program: str, table: str, width: int | None) -> str:
    """Fold a literal and its relative-command suffix without changing jumps."""
    if width is None:
        return program
    wrapped = _bracket_literal(program, width)
    if grid_width(wrapped) <= width:
        return wrapped
    # Push chunks from last to first: each string itself pushes in reverse.
    # All jumps follow the prologue and are relative, so its length is free.
    chunk = max(1, width - 3)
    starts = range(0, len(table), chunk)
    prologue = (
        "".join(f"[PSH INT {_ASCII_ZERO + int(bit)}]" for bit in reversed(table))
        if width < 4
        else "".join(
            f'[PSH STR "{table[start : start + chunk]}"]' for start in reversed(starts)
        )
    )
    tokens = _TOKEN.findall(prologue + program[len(table) + _TABLE_PUSH_OVERHEAD :])
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
    if default.startswith("[INP INT]"):
        return min(candidates, key=balance_score)
    size = len(atoms[0]) - _TABLE_PUSH_OVERHEAD
    # Skip the ``[PSH STR "`` prologue, the table, and the ``"]`` closer: the
    # rest is the instruction suffix the chunked rows pack beside the pushes.
    suffix = _TOKEN.findall(default[size + _TABLE_PUSH_OVERHEAD :])
    centre = _chunked_columns(size, list(map(len, suffix)))
    candidates.extend(modulous(table, centre + offset) for offset in (-3, -1, 1, 3))
    return min(candidates, key=balance_score)


def modulous_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.width is not None:
        return modulous(request.table, request.width)
    return modulous(request.table)


def modulous_balance_request(request: BalanceRequest) -> Program:
    """Lay out source through the declared balance request interface."""
    return _balance(request.table, request.text_source())
