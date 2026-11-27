"""Reduce a truth table by trimming a deque from either end.

Each nybble holds four consecutive table bits. The high selectors keep
one half of the deque at a time until one nybble remains. The last two
essential bits select its answer by shifting twice or once on zero.
Affine tables XOR selected inputs into X.

Size:
    O(T) characters, n=4 parity: 32 chars, n=8 and: 311 chars.
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

    packed = "".join(
        f"{int(reduced[start : start + 4], 2):X}" for start in range(0, len(reduced), 4)
    )
    first_shift = essential[-2]
    wanted = set(essential)
    remaining = len(packed)
    parts = []
    for position in range(arity):
        if position == first_shift:
            # A four-row projection fits directly in the zeroed register.
            parts.append(f"+Y{packed}" if len(packed) == 1 else ">Y")
        parts.append("?X?X")
        if position not in wanted:
            continue
        join = f"{2 * position + 1:X}"
        if position >= first_shift:
            parts.append(f"~X{join}")
            if position == first_shift:
                # Either outcome of the first shift reaches the second.
                next_shift = f"{2 * arity:X}"
                parts.append(f"~Y{next_shift}:{next_shift}")
            parts.append(f"~Y{join}:{join}")
            continue

        half = remaining // 2
        if remaining == len(packed):
            zero, one = "*" + packed[:half], "*" + packed[half:]
        else:
            zero, one = ">X" * half, "<X" * half
        odd = f"{2 * position:X}"
        parts.append(f"~X{odd}{zero}#{join}:{odd}{one}:{join}")
        remaining = half
    # NAND with 1 followed by inversion isolates the low bit.
    return "".join(parts) + "&Y1^YF!3Y@"
