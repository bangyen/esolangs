"""OBrainfuck Boolean program generator: a tape-laid table indexed by the inputs.

The table, projected onto its m essential inputs, is written loop-free, row
``k``'s bit at cell ``k`` of ``t = 2^m``, and the head steps onto cell ``t``.
Each input byte is read there and reduced to 0 or 1; a one of essential input
``j`` moves the head right ``2^(m-1-j)`` cells inside ``[-...]``, and the
closer tests the untouched cell it landed on and exits.  The head ends at
``t + row``, steps back ``t`` and prints the bit.  An ignored input is read
and left for the next read to overwrite.  Every loop is flat, so ordinal and
nested pairing agree.

Size:
    O(T): 3t + ones + 52m + (n - m) + 48 chars for t = 2^m rows of the
    projected table, ``ones`` its count of 1;
    n=4 parity: 312 chars, n=10 random 1847: 4,152 chars (Brainfuck's
    tree: 9,648).  Constant tables: n + 50 + b chars, b the answer.

Decisions:
    The head moves by data, so the cell each read lands on must be zero for
    every row: reads use the zero block ``t..2t-1``, and the closing ``<``
    run of length t is the price.  Interleaving a scratch beside each bit
    instead costs 4t moves ([ablations.interleaved_scratch_20261117]).
    Marking the minority bit saves ``ones`` past t/2, but the complementing
    print needs a zero beside the bit, 3t more commands here.
"""

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program

__all__ = ["obrainfuck"]


def obrainfuck(truth_table: str) -> str:
    """Build a program printing ``truth_table[row]`` after consuming all inputs."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = read_at(truth_table, essential, n)
    print_answer = "+" * _ASCII_ZERO + "."
    if not essential:
        # Reads land in cell 0; print from a clean neighbour.
        return "," * n + ">" + "+" * (table == "1") + print_answer
    # The zero cells t..2t-1 are the scratch; the head starts at cell t.
    layout = ">".join("+" * (bit == "1") for bit in table) + ">"
    # Essential input j of m moves the head 2^(m-1-j) rows on a one.
    stride = {i: 1 << (len(essential) - 1 - j) for j, i in enumerate(essential)}
    reads = "".join(
        "," + "-" * _ASCII_ZERO + "[-" + ">" * stride[i] + "]" if i in stride else ","
        for i in range(n)
    )
    return layout + reads + "<" * len(table) + print_answer


def obrainfuck_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return obrainfuck(request.table)
