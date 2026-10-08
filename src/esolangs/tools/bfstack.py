"""Boolean program generator for BFStack."""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    input_weights,
)


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


def _bfstack_decoder(truth_table: str) -> tuple[str, bool]:
    """Return the decoder, and whether the result must start at 1.

    A listed row costs the gap to the one before it and two brackets, so
    listing the *zero* rows made a mostly-zero table the expensive case --
    backwards: at twelve inputs it cost 17,091 characters against 4,801 for
    the all-one table.  Listing the one rows inverts the cascade, which
    starting the result at 1 and subtracting undoes; ties keep the direct form.
    """
    zeros = [k + 1 for k, ch in enumerate(truth_table) if ch == "0"]
    ones = [k + 1 for k, ch in enumerate(truth_table) if ch == "1"]
    direct = _bfstack_cascade(zeros, "[<+>]")
    # One character dearer than it looks: the preset ``+`` in the encoder.
    inverted = _bfstack_cascade(ones, "[<->]")
    if len(inverted) + 1 < len(direct):
        return inverted, True
    return direct, False


def _bfstack_small(truth_table: str, n: int) -> str:
    """Return a byte-indexed decoder over the essential inputs.

    At most seven fit its sentinel; an ignored input weighs nothing.
    """
    weights, projected = input_weights(truth_table, n)
    decoder, preset = _bfstack_decoder(projected)
    encoder = _bfstack_encoder(weights, preset=preset)
    return encoder + decoder + "<" + "+" * _ASCII_ZERO + "."


def bfstack(truth_table: str) -> str:
    """Build a BFStack program, routing wider tables into seven-input blocks.

    The byte index is ``1 + row``; eight inputs wrap its nonzero sentinel.
    Prefix branches select blocks before the byte-indexed decoder runs.
    """
    n = _validate_truth_table(truth_table)
    if n <= 7 or 0 < len(essential_inputs(truth_table, n)) <= 7:
        return _bfstack_small(truth_table, n)
    constant = constant_span_test(truth_table)

    def build(level: int, lo: int, hi: int) -> str:
        remaining = n - level
        if constant(lo, hi):
            return (
                ",<" * remaining
                + ">"
                + "+" * (_ASCII_ZERO + int(truth_table[lo]))
                + ".<"
            )
        if remaining <= 7:
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
