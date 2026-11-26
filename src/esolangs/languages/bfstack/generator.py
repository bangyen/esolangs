"""BFStack Boolean program generator: byte-indexed row lists under prefix branches.

Up to eight essential inputs are summed into a byte starting at zero.
The decoder tests before each decrement and applies the table's changes
while unwinding, so neither encoding nor decoding needs wrapping arithmetic.
Wider tables branch on the leading input into blocks. Interned subtable
IDs and bottom-up dependency masks choose the blocks without rescanning
their parent spans.

Size:
    O(T) chars; parity and and are linear in n. n=10 parity: 665 chars,
    n=10 and: 638 chars, n=10 random 1847: 7,786 chars.
    Constants use L=2n+50+b chars/commands, omitting the branch-only final pop;
    written workspace 6+bl(L)+bl(n) bits.
    A projected identity retains its raw input byte: 2n chars/commands.
"""

from collections.abc import Sequence

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    WeightedLookup,
    _validate_truth_table,
    input_weights,
    subtree_ids,
    symmetric_lookup,
)
from esolangs.generation.lookup import constant_output
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def _bfstack_encoder(weights: Sequence[int], initial_answer: str) -> str:
    """Push the answer's ASCII base, then the index in a separate cell."""
    parts = [">", "+" * (_ASCII_ZERO + int(initial_answer)), ">"]
    for weight in weights:
        if not weight:
            parts.append(",<")
            continue
        parts.append("," + "-" * _ASCII_ZERO + "[<" + "+" * weight + ">]<")
    return "".join(parts)


#: A zero-based index over eight bits reaches at most 255.
_BLOCK_INPUTS = 8


def _bfstack_decoder(truth_table: str) -> str:
    """Apply the answer differences at each change point reached by the index."""
    previous = truth_table[0]
    unwinds = []
    last_change = 0
    for row, answer in enumerate(truth_table[1:], start=1):
        if answer != previous:
            unwinds.append("]" * (row - last_change - 1))
            unwinds.append("<+>]" if answer == "1" else "<->]")
            previous, last_change = answer, row
    if not last_change:
        return ""
    # Each entered open consumes one index notch. Clear any surplus before
    # unwinding, so the restored zero exits each open after one pass.
    # The reversed differences telescope, keeping the ASCII cell in 47..50.
    return "[-" * last_change + "[-]" + "".join(reversed(unwinds))


def _bfstack_small(
    truth_table: str, n: int, build: tuple[Sequence[int], str] | None = None
) -> str:
    """Return a byte-indexed decoder over the essential inputs.

    The index covers at most 256 entries; an ignored input weighs nothing.
    """
    weights, projected = build or input_weights(truth_table, n)
    if projected == "01" and weights.count(1) == 1:
        # Projection leaves only the selected byte; later reads push/pop above
        # it. Printing after the drain preserves physical input order.
        selected = weights.index(1)
        return ",<" * selected + "," + ",<" * (n - selected - 1) + "."
    return _bfstack_encoder(weights, projected[0]) + _bfstack_decoder(projected) + "<."


def _constant_leaf(reads: int, bit: str) -> str:
    """Return the program that reads ``reads`` inputs and prints ``bit``."""
    return ",<" * reads + ">" + "+" * (_ASCII_ZERO + int(bit)) + ".<"


def bfstack(truth_table: str) -> str:
    """Build a BFStack program; a symmetric table indexes its input count.

    The count fits the byte index at any width, so the block limit does not
    apply ([ablations.symmetric_count]).  It always beats the plain build:
    no symmetric table through n=8 (12,596 at n=8) ships a different program
    when the race against the plain build is dropped.
    """
    n = _validate_truth_table(truth_table)
    if (bit := constant_output(truth_table)) is not None:
        return _constant_leaf(n, bit)[:-1]
    projected = input_weights(truth_table, n)
    symmetric = symmetric_lookup(projected)
    if symmetric is None or len(symmetric.table) > (1 << _BLOCK_INPUTS):
        return _bfstack_plain(truth_table, projected=projected)
    return _bfstack_small(truth_table, n, symmetric)


def _bfstack_plain(truth_table: str, *, projected: WeightedLookup | None = None) -> str:
    """Route wide tables using bottom-up subtable dependencies."""
    n = _validate_truth_table(truth_table)
    if n <= _BLOCK_INPUTS:
        return _bfstack_small(truth_table, n, projected)

    ids = subtree_ids(truth_table)
    # A level's input matters exactly when its children denote different
    # functions. Either child can make any later input essential.
    dependencies: dict[int, int] = {0: 0, 1: 0}
    for level in range(n - 1, -1, -1):
        bit = 1 << (n - level - 1)
        children = iter(ids[level + 1])
        for node, zero, one in zip(ids[level], children, children, strict=True):
            if node not in dependencies:
                dependencies[node] = (
                    dependencies[zero] | dependencies[one] | (bit if zero != one else 0)
                )

    parts: list[str] = []

    def emit(level: int, index: int) -> None:
        remaining = n - level
        node = ids[level][index]
        if node < 2:
            parts.append(_constant_leaf(remaining, str(node)))
        elif dependencies[node].bit_count() <= _BLOCK_INPUTS:
            lo = index << remaining
            parts.append(
                _bfstack_small(
                    truth_table[lo : lo + (1 << remaining)],
                    remaining,
                    projected if level == 0 else None,
                )
            )
            if level:
                parts.append("<")
        elif ids[level + 1][2 * index] == ids[level + 1][2 * index + 1]:
            # Drain an ignored input without duplicating the subtree.
            parts.append(",<")
            emit(level + 1, 2 * index)
        else:
            # The one arm clears the sentinel. Both arms restore stack depth.
            parts.append(">+," + "-" * _ASCII_ZERO + "[<-")
            emit(level + 1, 2 * index + 1)
            parts.append(">]<[<")
            emit(level + 1, 2 * index)
            parts.append(">]<")

    emit(0, 0)
    return "".join(parts)


def bfstack_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return bfstack(request.table)
