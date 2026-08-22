"""Shared helpers for the boolean-function program generators.

The generators in this package build programs that read ``n`` boolean
inputs and print the result of a truth table; the helpers here are the
common input handling they all repeat.

A truth table's length determines its input count: a valid table has
``2**n`` entries, so ``n`` is recovered from the table alone and the
generators take no ``n`` parameter.
"""

from collections.abc import Callable


def _validate_truth_table(truth_table: str) -> int:
    """Validate a truth table and return its input count ``n``.

    A valid table has ``2**n`` binary entries, so ``n`` is recovered from
    the length (a power of two).
    """
    n = len(truth_table).bit_length() - 1
    if len(truth_table) != 2**n:
        raise ValueError(
            "truth table must have a power-of-two number of entries "
            f"(2**n), got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")
    return n


def _complement(truth_table: str) -> str:
    """Return the bitwise complement of ``truth_table``."""
    return "".join("1" if c == "0" else "0" for c in truth_table)


def _maybe_complement(truth_table: str) -> tuple[str, bool]:
    """Return the table (or its complement) and whether it was flipped.

    A table with more ones than zeros is cheaper to evaluate complemented
    and inverted, so generators flip when ones dominate.
    """
    if truth_table.count("1") > len(truth_table) // 2:
        return _complement(truth_table), True
    return truth_table, False


SetBit = Callable[[int, int], str]
SetComp = Callable[[int, int], str]


def instantiate(
    template: str,
    bits: list[int],
    set_bit: SetBit,
    set_comp: SetComp,
) -> str:
    """Substitute each ``{Xi}``/``{Ci}`` placeholder.

    ``{Xi}`` becomes ``set_bit(i, bit)`` (code that sets input ``i`` to the
    bit) and ``{Ci}`` becomes ``set_comp(i, bit)`` (code that sets it to the
    complement of the bit).  Since the bits are embedded constants, the
    complement is emitted directly rather than computed at runtime.
    """
    for i, bit in enumerate(bits):
        template = template.replace("{X" + str(i) + "}", set_bit(i, bit))
        template = template.replace("{C" + str(i) + "}", set_comp(i, bit))
    return template
