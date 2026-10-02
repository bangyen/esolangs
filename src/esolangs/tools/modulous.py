"""Boolean program generator for Modulous."""

import re

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table


def modulous(truth_table: str, width: int | None = None) -> str:
    """Build a Modulous table lookup, chunking literals below the old width.

    Command whitespace folds; each quoted chunk keeps its closing bracket.
    """
    n = _validate_truth_table(truth_table)
    # ``PSH STR`` pushes the characters in reverse, so the leftmost entry is on
    # top and discarding ``index`` of them uncovers ``truth_table[index]`` --
    # the row index read MSB first, which is what the weights below build.  The
    # first read *is* the counter: a bit is already 0 or 1, so the top weight is
    # one conditional ``ADD`` away and no accumulator is pushed.
    top = 1 << (n - 1)
    reads = ["[INP INT]" + (f"[JMP F 2 IF 0][ADD {top - 1}]" if n > 1 else "")]
    reads += [
        f"[INP INT][JMP F 4 IF 0][POP][ADD {1 << (n - 1 - i)}][JMP F 2][POP]"
        for i in range(1, n)
    ]
    # ``SWP``/``POP`` discards the entry *under* the counter, which is what
    # keeps the counter reachable: nothing but the top two cells is.
    walk = "[JMP F 5 IF 0][SUB 1][SWP][POP][JMP B 4][POP][PRT][END]"
    program = f'[PSH STR "{truth_table}"]{"".join(reads)}{walk}'
    if width is None or width <= 0:
        return program
    from esolangs.tools.wrap import _bracket_literal, wrap_space_delimited

    previous = _bracket_literal(program, width)
    if max(map(len, previous.splitlines())) <= width:
        return previous
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
    tokens = re.findall(r'"[^"]*"\]|[A-Z]+|\d+|[^\s]', prologue + "".join(reads) + walk)
    return wrap_space_delimited(" ".join(tokens), width)
