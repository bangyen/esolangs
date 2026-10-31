"""BFStack Boolean program generator: byte-indexed row lists under prefix branches.

Up to eight essential inputs are summed into a byte (``1 + row``, or ``row``
with a zero row wrapping to byte 0) and a nested subtraction cascade lists
the zero rows; wider tables branch on the leading input into blocks.

Size:
    O(T) chars; parity and and are linear in n.  n=10 parity: 633 chars,
    n=10 and: 640 chars, n=10 random 1847: 5,211 chars.

Decisions:
    No call or goto (loops nest) and the stack hides all but its top, so a
    repeated block cannot be reached from a flag.  A node whose four
    quarters are two distinct blocks once classified its two prefix bits and
    wrote each block once; it was retired: it paid only on two-block tables
    ([ablations.two_block_classifier]).  The decoder lists the zero rows
    rather than folding a run: it has no range test, so each listed row is
    its own nested loop.  Listing the rarer value instead was retired: it
    pays only on sparse tables ([ablations.decoder_value_race]).  The eighth
    input wraps the byte; the row left at byte 0 never enters the decoder, so
    it must be a zero row ([ablations.eighth_input]).
"""

from functools import cache
from typing import Any

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.bfstack.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape


def _bfstack_encoder(weights: list[int], start: int = 1) -> str:
    """BFStack code turning the inputs into ``start + sum(bit*weight)``.

    ``,`` reads, 48 ``-``s normalize, ``[<+w>]`` adds the weight; an ignored
    input, weight 0, is read and popped.  A start of 1 keeps the result
    nonzero so the decoder's outer ``[`` always runs.
    """
    # Result cell (0) below the accumulator.
    prog = ">>" + "+" * start
    for weight in weights:
        if not weight:
            prog += ",<"
            continue
        prog += "," + "-" * _ASCII_ZERO + "[" + "<" + "+" * weight + ">" + "]" + "<"
    return prog


def _bfstack_cascade(rows: list[int], payload: str) -> str:
    """Nest subtractions over ``rows``, running ``payload`` off the list.

    Reaching zero on a listed row leaves that row's ``[`` unentered, so
    ``payload`` runs exactly when the encoded number is not in ``rows``.
    """
    if not rows:
        return payload
    prog = "["
    prev = 0
    for row in rows:
        prog += "-" * (row - prev) + "["
        prev = row
    return prog + payload + "]" * (len(rows) + 1)


#: Inputs a block holds with the start at 1: index 1 + 127 fits.  An eighth
#: wraps the byte; the row at byte 0 then skips the decoder (``_start``).
_BLOCK_INPUTS = 7


def _start(projected: str) -> int:
    """Return the accumulator's start: the byte is ``start + row``, mod 256.

    Under 256 rows it starts at 1, keeping the outer ``[`` entered.  At 256
    rows the byte wraps and the row at byte 0 skips the decoder, so it must be
    a zero row: the rule is the smallest start putting a zero row at byte 0
    (row 0, then the last rows up).
    """
    if len(projected) < 256:
        return 1
    return next(start for start in range(256) if projected[(256 - start) % 256] == "0")


def _bfstack_decoder(truth_table: str, start: int = 1) -> str:
    """Return the decoder: a cascade listing the zero rows, then ``[<+>]``.

    Listing the rarer value instead (ones, with a preset result cell) was
    retired ([ablations.decoder_value_race]).  The row whose byte wraps to 0
    is never listed: the outer ``[`` skips it.
    """
    zeros = sorted(
        v for k, ch in enumerate(truth_table) if ch == "0" and (v := (k + start) % 256)
    )
    return _bfstack_cascade(zeros, "[<+>]")


def _bfstack_small(
    truth_table: str, n: int, build: tuple[list[int], str] | None = None
) -> str:
    """Return a byte-indexed decoder over the essential inputs.

    At most ``_BLOCK_INPUTS`` essential inputs; an ignored input weighs nothing.
    """
    weights, projected = build or input_weights(truth_table, n)
    start = _start(projected)
    return (
        _bfstack_encoder(weights, start)
        + _bfstack_decoder(projected, start)
        + "<"
        + "+" * _ASCII_ZERO
        + "."
    )


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
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is None or len(symmetric[1]) > 255:
        return _bfstack_plain(truth_table)
    return _bfstack_small(truth_table, n, symmetric)


def _fits(truth_table: str, n: int) -> bool:
    """Whether one byte-indexed block holds the table's essential inputs."""
    return n <= _BLOCK_INPUTS or 0 < len(essential_inputs(truth_table, n)) <= 8


def _bfstack_plain(truth_table: str) -> str:
    """Build a BFStack program, routing wide tables into blocks.

    Prefix branches select blocks of up to eight essential inputs before the
    byte-indexed decoder runs.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _constant_leaf(n, truth_table[0])
    if _fits(truth_table, n):
        return _bfstack_small(truth_table, n)
    constant = constant_span_test(truth_table)

    @cache
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


def _payload(state: Any) -> Payload:
    """Split out the data stack, loop stack and pc; the cursor is I/O state."""
    data, control, pc, _cursor = state
    return data, control, pc, 0


LANGUAGE = Language(
    "BFStack",
    "bfstack",
    category="stack_based",
    payload=_payload,
    boolean=bfstack,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    proof_execution=(execution, True, (8, 9, 10)),
    proof_workspace=(workspace, False, (3, 6)),
)
