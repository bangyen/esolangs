"""Help. Boolean generator using straight-line Shannon reductions.

Each input is read once. Constant spans and equal cofactors collapse.
A remaining node combines its children's bits with its input and its
complement. Each depth reuses its own two scratch bytes, with the lowest
addresses nearest the leaves. Addresses near depth d then cost at most
O(n-d+1) characters, and the sum over at most 2**d nodes per depth is O(T).

Size:
    O(T) characters, n=4 parity: 924 chars.
"""

from esolangs.generation.helpers import essential_inputs, subtree_ids
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def help_program(truth_table: str) -> str:
    """Emit byte reads followed by a loop-less Boolean reduction."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    essential = set(essential_inputs(truth_table, n))
    slots = [
        tuple(f"${4 * rank + offset:x}" for offset in range(1, 5))
        for rank in reversed(range(n))
    ]
    lines = []
    for level, (bit, complement, _, _) in enumerate(slots):
        if level not in essential:
            lines.append("inp one $0")
            continue
        lines.extend(
            (f"inp one {bit}", f"sub {bit} 30 {bit}", f"boo {complement} not {bit}")
        )

    def emit(level: int, block: int, dest: str) -> str:
        node = ids[level][block]
        if node < 2:
            return str(node)
        below = level + 1
        left = 2 * block
        if ids[below][left] == ids[below][left + 1]:
            return emit(below, left, dest)
        bit, complement, zero_temp, one_temp = slots[level]
        zero = emit(below, left, zero_temp)
        one = emit(below, left + 1, one_temp)
        lines.extend(
            (
                f"boo {zero_temp} and {complement} {zero}",
                f"boo {one_temp} and {bit} {one}",
                f"boo {dest} or_ {zero_temp} {one_temp}",
            )
        )
        return dest

    answer = emit(0, 0, "$0")
    if answer == "$0":
        lines.extend(("add $0 30 $0", "out $0"))
    else:
        lines.append("out 3" + answer)
    return "\n".join(lines)


def help_request(request: GenerationRequest) -> Program:
    """Emit source from the typed backend request."""
    return help_program(request.table)
