"""Compile a truth table to a straight-line Onecode memory lookup.

The Horner expression reads ASCII digits in input order and subtracts
the accumulated ASCII-zero bias once. Each lookup character holds four
answers in its low bits. A shared divisor table selects one bit from the
indexed character by division and subtraction.

Size:
    O(T) characters, n=4 parity: 109 chars, n=8 parity: 215 chars.
"""

from esolangs.generation.requests import GenerationRequest, project_inputs
from esolangs.runtime._program import Program
from esolangs.runtime.memory import format_integer


def onecode_fergusq_request(request: GenerationRequest) -> Program:
    """Index a packed lookup by the essential inputs."""
    arity, essential, table = project_inputs(request.truth_table)
    if not essential:
        return "getc();\n" * arity + f"putc({ord(table[0])});"

    first, last = essential[0], essential[-1]
    kept = set(essential)
    index = ["2*(" * (len(essential) - 1), "getc()"]
    # Interior ignored inputs run in order and add zero to the index.
    index.extend(
        ")+getc()" if level in kept else "+getc()*0"
        for level in range(first + 1, last + 1)
    )
    bias = format_integer(48 * (len(table) - 1))
    # Adding 64 makes printable cells. Dividing by 1, 2, 4 or 8 leaves
    # its contribution even, so the final parity test drops it.
    packed = "".join(
        chr(64 + int(table[at : at + 4][::-1], 2)) for at in range(0, len(table), 4)
    )
    return (
        "getc();\n" * first
        + f"i~{''.join(index)}-{bias};\n"
        + "getc();\n" * (arity - last - 1)
        + f'*0~"1248{packed}";\n'
        + "j~i/4;\nv~*(4+j)/(*(i-4*j)-48);\nputn(v-2*(v/2));"
    )
