"""Boolean program generator for BFStack.

No call or goto (loops nest) and the stack hides all but its top, so a repeated
block cannot be reached from a flag.  A node whose four quarters are two
distinct blocks instead classifies its two prefix bits and branches once, so
each block is written once.  Two bits only: a classifier's weights sum to
``2**d - 1``, so wider ones make the worst run exponential, not ``poly n``.
The byte-indexed decoder lists the rarer value rather than folding a run: it
has no range test, so each listed row is its own nested loop.
"""

from functools import cache
from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    input_weights,
)
from esolangs.tools.wrap import wrap_chars


def _bfstack_encoder(weights: list[int], *, preset: bool) -> str:
    """BFStack code turning the inputs into the number ``1 + sum(bit*weight)``.

    ``,`` reads, 48 ``-``s normalize, ``[<+w>]`` adds the weight; an ignored
    input, weight 0, is read and popped.  The ``+1`` keeps the result nonzero
    so the decoder's outer ``[`` always runs, and ``preset`` starts it at 1
    for the subtracting decoder.
    """
    # Result cell (0, or 1 when the decoder subtracts) below the accumulator.
    prog = ">+>+" if preset else ">>+"
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


#: Most inputs one byte-indexed block holds: index 1 + 127 fits, 8 inputs wrap.
_BLOCK_INPUTS = 7


def _bfstack_decoder(truth_table: str) -> tuple[str, bool]:
    """Return the decoder, and whether the result must start at 1.

    Lists the rarer value (the inverted form lists ones); ties keep direct.
    Listing zeros for a mostly-zero table cost 17,091 characters at twelve
    inputs against 4,801 for the all-one table.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    ones = [k + 1 for k, ch in enumerate(truth_table) if ch == "1"]
    direct = _bfstack_cascade(zeros, "[<+>]")
    # +1 pays the encoder's preset ``+``.
    inverted = _bfstack_cascade(ones, "[<->]")
    if len(inverted) + 1 < len(direct):
        return inverted, True
    return direct, False


def _bfstack_small(truth_table: str, n: int) -> str:
    """Return a byte-indexed decoder over the essential inputs.

    At most ``_BLOCK_INPUTS`` essential inputs; an ignored input weighs nothing.
    """
    weights, projected = input_weights(truth_table, n)
    decoder, preset = _bfstack_decoder(projected)
    encoder = _bfstack_encoder(weights, preset=preset)
    return encoder + decoder + "<" + "+" * _ASCII_ZERO + "."


def _bfstack_class(prefix: str, bits: int) -> str:
    """Return the classifier: ``prefix`` read as a table, left as 0/1 on top."""
    weights, projected = input_weights(prefix, bits)
    decoder, preset = _bfstack_decoder(projected)
    return _bfstack_encoder(weights, preset=preset) + decoder + "<"


def bfstack(truth_table: str) -> str:
    """Build a BFStack program, routing wide tables into blocks.

    The byte index is ``1 + row``; eight inputs wrap its nonzero sentinel
    (``_BLOCK_INPUTS`` = 7).
    Prefix branches select blocks before the byte-indexed decoder runs.
    A node whose four quarters are two distinct blocks instead classifies its
    two prefix bits once and writes each block once, when that is shorter.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return ",<" * n + ">" + "+" * (_ASCII_ZERO + int(truth_table[0])) + ".<"
    if n <= _BLOCK_INPUTS or 0 < len(essential_inputs(truth_table, n)) <= _BLOCK_INPUTS:
        return _bfstack_small(truth_table, n)
    constant = constant_span_test(truth_table)

    def classified(level: int, lo: int, hi: int) -> str | None:
        """Return the node classifying two distinct quarters of ``[lo, hi)``, if any."""
        if n - level < 3:
            return None
        size = (hi - lo) >> 2
        slots = [truth_table[lo + k * size : lo + (k + 1) * size] for k in range(4)]
        kinds = sorted(set(slots))
        if len(kinds) != 2:
            return None
        codes = []
        for one, zero in (kinds, kinds[::-1]):
            prefix = "".join("1" if slot == one else "0" for slot in slots)
            at_one, at_zero = (lo + slots.index(k) * size for k in (one, zero))
            codes.append(
                ">+"
                + _bfstack_class(prefix, 2)
                + "[<-"
                + build(level + 2, at_one, at_one + size)
                + ">]<[<"
                + build(level + 2, at_zero, at_zero + size)
                + ">]<"
            )
        return min(codes, key=len)

    @cache
    def build(level: int, lo: int, hi: int) -> str:
        remaining = n - level
        if constant(lo, hi):
            return (
                ",<" * remaining
                + ">"
                + "+" * (_ASCII_ZERO + int(truth_table[lo]))
                + ".<"
            )
        if remaining <= _BLOCK_INPUTS:
            plain = _bfstack_small(truth_table[lo:hi], remaining) + "<"
        else:
            mid = (lo + hi) // 2
            if truth_table[lo:mid] == truth_table[mid:hi]:
                # An input this subtree ignores is read and popped, not branched.
                return ",<" + build(level + 1, lo, mid)
            zero, one = build(level + 1, lo, mid), build(level + 1, mid, hi)
            # The one arm clears the sentinel below the bit. Both arms restore
            # their stack depth, so the zero arm runs only when the bit was zero.
            plain = ">+," + "-" * _ASCII_ZERO + "[<-" + one + ">]<[<" + zero + ">]<"
        shared = classified(level, lo, hi)
        return plain if shared is None or len(plain) <= len(shared) else shared

    return build(0, 0, len(truth_table))


def _payload(state: Any) -> Payload:
    """Split out the data stack, loop stack and pc; the cursor is I/O state."""
    data, control, pc, _cursor = state
    return data, control, pc, 0


LANGUAGE = Language(
    "BFStack",
    "stack_based.bfstack",
    payload=_payload,
    boolean=bfstack,
    # A sum, not a tree: a lookup over the essential inputs only.
    shape=Shape.REDUCING,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
