"""Compile a truth table to a straight-line Onecode memory lookup.

Retain only essential coordinates in the literal and the binary index.
The row lists double on each retained coordinate, so their total size
is less than twice the table length. Every original input is read once.

Size:
    O(T) characters, n=4 parity: 96 chars.
"""

from esolangs.generation.helpers import essential_inputs
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def onecode_fergusq_request(request: GenerationRequest) -> Program:
    """Accumulate an index from the essential bits and print its character."""
    table = request.table
    arity = len(table).bit_length() - 1
    essential = essential_inputs(table, arity)
    if not essential:
        return "getc();\n" * arity + f"putc({ord(table[0])});"

    rows = [0]
    for level in essential:
        stride = 1 << (arity - level - 1)
        rows = [row + offset for row in rows for offset in (0, stride)]
    literal = "".join(table[row] for row in rows)
    kept = set(essential)
    lines = [
        (
            "i~getc()-48;"
            if level == essential[0]
            else "i~2*i+getc()-48;"
            if level in kept
            else "getc();"
        )
        for level in range(arity)
    ]
    lines.extend((f'*0~"{literal}";', "putc(*i);"))
    return "\n".join(lines)
