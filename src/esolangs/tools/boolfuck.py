"""Boolfuck Boolean generator via the author's fixed Brainfuck lowering.

The decision tree is the Brainfuck tree lowered command by command, but
the reads and the print are specialized at the bit level. A lowered ``,``
reads one input character as a byte at offsets 1..8 of a cell (head
resting on the separator at offset 0); under the Boolean input contract
that byte is ``'0'`` or ``'1'``, so the input bit is its low bit, and
clearing the upper seven bits leaves the byte 0 or 1 -- exactly the
state the Brainfuck prologue's 48 decrements per read would produce, at
61 lowered commands per read instead of 2,328. The print likewise sets
the two ASCII bits of the 0/1 result byte directly instead of adding 48.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    decision_tree_body,
    in_input_order,
    move_text,
)

_LOWER = {
    "+": ">[>]+<[+<]>>>>>>>>>[+]<<<<<<<<<",
    "-": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>[+]<<<<<<<<<",
    "<": "<<<<<<<<<",
    ">": ">>>>>>>>>",
    ",": ">,>,>,>,>,>,>,>,<<<<<<<<",
    ".": ">;>;>;>;>;>;>;>;<<<<<<<<",
    "[": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>[+<<<<<<<<[>]+<[+<]",
    "]": ">>>>>>>>>+<<<<<<<<+[>+]<[<]>>>>>>>>>]<[+<]",
}

# After a lowered read, keep the byte's low bit (offset 1) and clear the
# bits at offsets 2..8 (``[+]`` clears a bit whether or not it was set),
# leaving the head back on the separator.
_EXTRACT_BIT = ">" + ">[+]" * 7 + "<" * 8

# Turn a result byte of 0 or 1 into '0' or '1' by setting bits 4 and 5
# (offsets 5 and 6); each ``[+]+`` sets a bit whether or not it was set.
_ASCIIFY = ">>>>>" + "[+]+" + ">" + "[+]+" + "<<<<<<"


def _lower(program: str) -> str:
    """Lower Brainfuck source with the fixed per-command replacements."""
    return "".join(_LOWER.get(c, "") for c in program)


def _boolfuck_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered.

    Mirrors the Brainfuck builder's choreography (bits at cells 2i, flag
    cells 2i+1 left zero, head left on cell 2(n-1)) with bit-level reads.
    """
    n = _validate_truth_table(truth_table)

    parts: list[str] = []
    pos = 0
    for i in range(n):
        parts.append(_LOWER[","])
        parts.append(_EXTRACT_BIT)
        if i < n - 1:
            parts.append(_LOWER[">"] * 2)
            pos += 2

    body, pos = decision_tree_body(truth_table, ">", "<", perm, pos)
    parts.append(_lower(body))
    parts.append(_lower(move_text(pos, 2 * n, ">", "<")))
    parts.append(_ASCIIFY)
    parts.append(_LOWER["."])
    return "".join(parts)


def boolfuck(truth_table: str) -> str:
    """Return the lowered decision tree for an MSB-first truth table."""
    return in_input_order(truth_table, _boolfuck_ordered)
