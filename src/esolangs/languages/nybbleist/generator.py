"""Reduce a truth table by trimming a deque from either end.

The first essential selector chooses which half to enqueue. Each later
selector discards the unchosen half, from the back for zero and the
front for one. Affine tables only XOR selected inputs into X.

Size:
    O(T) characters, n=4 parity: 32 chars.
"""

from esolangs.generation.algebraic import affine_form
from esolangs.generation.projection import essential_inputs, read_at
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def nybbleist_request(request: GenerationRequest) -> Program:
    """Emit one forward branch per essential input."""
    table = request.table
    arity = len(table).bit_length() - 1
    if (affine := affine_form(table, arity)) is not None:
        reads = ("?Y?Y^XY" if needed else "?Y?Y" for needed in affine.coefficients)
        return "".join(reads) + ("^X1" if affine.bias else "") + "!3X@"

    essential = essential_inputs(table, arity)
    reduced = read_at(table, essential, arity)

    wanted = set(essential)
    parts = []
    remaining = len(reduced)
    for position in range(arity):
        parts.append("?X?X")
        if position not in wanted:
            continue
        half = remaining // 2
        if remaining == len(reduced):
            zero, one = "*" + reduced[:half], "*" + reduced[half:]
        else:
            zero, one = ">Y" * half, "<Y" * half
        odd, join = f"{2 * position:X}", f"{2 * position + 1:X}"
        parts.append(f"~X{odd}{zero}#{join}:{odd}{one}:{join}")
        remaining = half
    return "".join(parts) + ">X!3X@"
