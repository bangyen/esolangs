"""Boolean program generator for Modulous.

A string literal has no subtrees to fold or share.
"""

import re
from itertools import pairwise
from math import isqrt

from esolangs.registry._language import Language
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import _BRACKET_LITERAL, balance_score


def modulous(truth_table: str, width: int | None = None) -> str:
    """Return a Modulous table lookup; ``width`` folds command whitespace.

    Literals are chunked to fit; each quoted chunk keeps its closing bracket.
    """
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is on
    # top and discarding ``index`` of them uncovers ``truth_table[index]`` --
    # the row index read MSB first, which is what the weights below build.  A
    # pushed zero is the counter; an ignored input is read and popped, and the
    # table is indexed by the rest.  Letting the first read be the counter
    # saves 6.8% at n=6, 4.1% at n=8, 1.9% at n=10, under the 10% bar.
    weights, truth_table = input_weights(truth_table, n)
    reads = ["[PSH INT 0]"]
    for weight in weights:
        if weight:
            reads.append(f"[INP INT][JMP F 4 IF 0][POP][ADD {weight}][JMP F 2][POP]")
        else:
            reads.append("[INP INT][POP]")
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT][END]"
    program = f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'
    if width is None or width <= 0:
        return program
    from esolangs.tools.wrap import _bracket_literal, wrap_space_delimited

    wrapped = _bracket_literal(program, width)
    if max(map(len, wrapped.splitlines())) <= width:
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
    tokens = re.findall(r'"[^"]*"\]|[A-Z]+|\d+|\S', prologue + "".join(reads) + walk)
    return wrap_space_delimited(" ".join(tokens), width)


def _balance(table: str, default: str) -> str:
    """Balance bracket atoms and literal chunks at quotient and row fits."""
    atoms = re.findall(_BRACKET_LITERAL, default)
    floor = max(map(len, atoms))
    width = balanced_token_width(atoms, minimum=floor)
    candidates = [default, modulous(table, width)]
    numeric = modulous(table, 1).split()
    width = balanced_token_width(numeric, " ", maximum=3)
    candidates.append(modulous(table, width))
    # Below nine columns the three-word push prefix cannot share a row.
    candidates.extend(modulous(table, width) for width in range(4, 9))
    size = len(table)
    whole = modulous(table, size + 3).split()
    width = balanced_token_width(whole, " ", minimum=size + 3, maximum=floor - 1)
    candidates.append(modulous(table, width))
    suffix = re.findall(r'"[^"]*"\]|[A-Z]+|\d+|[^\s]', default[size + 12 :])
    lengths = list(map(len, suffix))
    fits = set()
    for start in range(len(lengths)):
        span = -1
        for length in lengths[start:]:
            span += length + 1
            fits.add(span - 3)
    fixed = [1, 3, 3, 0, 1, 3, 3]
    partial_fits = {
        sum(fixed[start:stop]) + stop - start - 1
        for start in range(4)
        for stop in range(4, 8)
    }
    quotients = {size}
    for divisor in range(1, isqrt(size - 1) + 1):
        quotients.update((divisor + 1, (size - 1) // divisor + 1))

    def height(parts: list[int], columns: int) -> int:
        rows, used = 1, 0
        for length in parts:
            if used and used + 1 + length > columns:
                rows += 1
                used = length
            else:
                used += length + bool(used)
        return rows

    best: tuple[int, int, int] | None = None
    for count in quotients:
        lower = max(6, (size + count - 1) // count)
        upper = min(size - 1, (size - 1) // (count - 1))
        if lower > upper:
            continue
        events = {lower, upper + 1}
        events.update(fit for fit in fits if lower < fit <= upper)
        events.update(
            point
            for extra in partial_fits
            if lower < (point := (size + extra + count - 1) // count) <= upper
        )
        boundaries = sorted(events)
        for start, stop in pairwise(boundaries):
            partial = size - (count - 1) * start
            rows = (
                height([1, 3, 3, partial + 3, 1, 3, 3], start + 3)
                + 2 * count
                - 3
                + height(lengths, start + 3)
            )
            columns = min(max(rows, start + 3), stop + 2)
            score = (abs(columns - rows), size + 14 * count, columns)
            if best is None or score < best:
                best = score
    if best is not None:
        candidates.append(modulous(table, best[2]))
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Modulous",
    "stack_based.modulous",
    boolean=modulous,
    balance=_balance,
)
