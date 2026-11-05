"""Unary Boolean program generator: a Brainfuck program written as a count of zeros.

A Unary program is N zeros.  N in binary is a 1, then three bits per
Brainfuck command in ``><+-.,[]`` order, so the generator writes Brainfuck
and counts.  Halting answers 0; ``[]`` on a nonzero cell loops forever and
answers 1.  The identity is ``,[]``: binary ``1 101 110 111``, 887 zeros,
which halt on input 0 and loop on 255.

Inputs are bytes 0 and 255. Complementing a read with + gives 1 and 0
without an ASCII prelude. This construction unrolls all n reads, so its
source has at least n commands and ``8**n`` zeros; it accepts at most nine
inputs.

Size:
    Each command multiplies the count by eight, so growth is exponential
    in the command count.  n=1 parity: 887 chars, n=2 and: 27,452,351
    chars (n=2's ``0001``), n=2 random 1847: 109 chars.
    n=1 constant one: 6,903 chars.

Raises:
    GeneratorCapError: the zero count passes 256 Mi (n=2's ``0110``).

Decisions:
    No repeated residual survives the admitted nine-command source budget.
"""

from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import (
    _validate_truth_table,
    decision_tree_body,
    essential_inputs,
    move_text,
)
from esolangs.languages.unary.descriptor import LANGUAGE as LANGUAGE

_MAX_SOURCE = 256 * 1024 * 1024
_LIMITS = TextLimits(32 * 1024 * 1024, _MAX_SOURCE, 256 * 1024)


def _decoded(truth_table: str) -> str:
    """Return ordered reads followed by a conditional fixed loop."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    if not kept:
        # Decrement maps both input bytes, 0 and 255, to a nonzero cell.
        return "," * n + ("-[]" if truth_table[0] == "1" else "")
    if len(kept) == 1:
        # One input decides: loop on its cell, after + if the table negates it.
        index = kept[0]
        reads = "," * (index + 1)
        if index < n - 1:
            reads += ">" + "," * (n - index - 1) + "<"
        return reads + ("+" if truth_table[0] == "1" else "") + "[]"
    if truth_table == "0" * (len(truth_table) - 1) + "1":
        # Each nonzero read enters the next guard; a zero exits to halt.
        return "," + ">," * (n - 1) + "[<" * (n - 1) + "[]" + "]" * (n - 1)
    # Complemented bytes are bits; reversing the table complements every input.
    reads = ">>".join(",+" for _ in range(n))
    body, pos = decision_tree_body(
        truth_table[::-1], ">", "<", tuple(range(n)), 2 * (n - 1)
    )
    return reads + body + move_text(pos, 2 * n, ">", "<") + "[]"


def unary(truth_table: str) -> CompressedText:
    """Return gzip source within the file and expanded-work budgets."""
    n = _validate_truth_table(truth_table)
    # This construction unrolls each read, so its own source needs n commands.
    if n > 9:
        raise GeneratorCapError("Unary unrolled construction: max-inputs=9")
    return CompressedText.repeated("0", _zeros(_decoded(truth_table)), limits=_LIMITS)


def _zeros(brainfuck: str) -> int:
    """Return the zero count: a binary 1, then each command's three bits."""
    count = 1
    for command in brainfuck:
        count = 8 * count + "><+-.,[]".index(command)
        if count > _MAX_SOURCE:
            raise GeneratorCapError(
                "Unary source exceeds the 256 Mi-character generation-work cap"
            )
    return count
