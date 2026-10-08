"""Boolean program generator for Modulous."""

import re

from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table, input_weights


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
