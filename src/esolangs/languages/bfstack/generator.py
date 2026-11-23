"""BFStack Boolean program generator: byte-indexed row lists under prefix branches.

Up to eight essential inputs are summed into a byte starting at zero.
The decoder tests before each decrement and applies the table's changes
while unwinding, so neither encoding nor decoding needs wrapping arithmetic.
Wider tables branch on the leading input into blocks.

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
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    input_weights,
    symmetric_weights,
)
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
    if len(set(truth_table)) == 1:
        return _constant_leaf(n, truth_table[0])[:-1]
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is None or len(symmetric.table) > (1 << _BLOCK_INPUTS):
        return _bfstack_plain(truth_table)
    return _bfstack_small(truth_table, n, symmetric)


def _fits(truth_table: str, n: int) -> bool:
    """Whether one byte-indexed block holds the table's essential inputs."""
    return (
        n <= _BLOCK_INPUTS or 0 < len(essential_inputs(truth_table, n)) <= _BLOCK_INPUTS
    )


def _bfstack_plain(truth_table: str) -> str:
    """Build a BFStack program, routing wide tables into blocks.

    Prefix branches select blocks of up to eight essential inputs before the
    byte-indexed decoder runs.
    """
    n = _validate_truth_table(truth_table)
    if _fits(truth_table, n):
        return _bfstack_small(truth_table, n)
    constant = constant_span_test(truth_table)

    def build(level: int, lo: int, hi: int) -> str:
        remaining = n - level
        if constant(lo, hi):
            return _constant_leaf(remaining, truth_table[lo])
        if _fits(truth_table[lo:hi], remaining):
            return _bfstack_small(truth_table[lo:hi], remaining) + "<"
        mid = (lo + hi) // 2
        if truth_table[lo:mid] == truth_table[mid:hi]:
            # An input this subtree ignores is read and popped, not branched.
            return ",<" + build(level + 1, lo, mid)
        zero, one = build(level + 1, lo, mid), build(level + 1, mid, hi)
        # The one arm clears the sentinel below the bit. Both arms restore
        # their stack depth, so the zero arm runs only when the bit was zero.
        return ">+," + "-" * _ASCII_ZERO + "[<-" + one + ">]<[<" + zero + ">]<"

    return build(0, 0, len(truth_table))


def bfstack_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return bfstack(request.table)
