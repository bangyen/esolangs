"""Boolean-function generators via input-by-substitution.

A normal boolean generator produces one program that *reads* its inputs.
Some languages have no input mechanism but still have enough computation
power (output, constant construction, and a value-testable branch) to
evaluate a boolean function from *embedded* constants.  For those, a
parameterized generator emits a **template** with ``{X0}``.. placeholders
for the input bits; :func:`instantiate` replaces each placeholder with the
language's code that sets that input cell to the bit value.  The harness
instantiates the template once per input and runs it, so the program is a
decision tree over constants rather than a reader of input.

This is a separate class from the input-reading generators: it is useful
exactly for the no-input languages, and it does not make them read input —
the harness performs the injection.
"""

from collections.abc import Callable

__all__ = ["bio", "instantiate"]

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


def _validate(truth_table: str, n: int) -> None:
    if len(truth_table) != 2**n:
        raise ValueError(
            f"truth table must have {2**n} entries for {n} inputs, "
            f"got {len(truth_table)}",
        )
    if not all(c in "01" for c in truth_table):
        raise ValueError("truth table must contain only '0' and '1'")


def bio(truth_table: str, n: int) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first), and ``n`` is the number of inputs.

    BIO has three registers (``x``, ``y``, ``z``).  ``{Xi}`` is replaced by
    ``0ox`` (increment ``x``) when bit ``i`` is one and by nothing when it
    is zero, so the raw bit lands in ``x``; ``{Ci}`` is the program's
    *runtime* computation of the complement (``0oy 0ix 1oy 1ox }``, which
    sets ``y = 1 - x`` and clears ``x``).  A node tests ``0iy`` for the
    zero-side and reloads ``{Xi}`` for the one-side, clearing each register
    before its loop exits.  Every leaf clears ``x`` and ``y`` so the
    ancestor loops unwind, and builds the result in ``z`` before printing
    it with ``1iz``.
    """
    _validate(truth_table, n)

    def set_bit(_i: int, bit: int) -> str:
        return "0ox" * bit

    def set_comp(_i: int, _bit: int) -> str:
        # y = 1 - x, computed at runtime from the raw bit in x (x cleared)
        return "0oy" + "0ix" + "1oy" + "1ox" + "}"

    def leaf(value: str) -> str:
        # build the result in z, print it, then clear x and y so every
        # ancestor loop (which checks x or y) unwinds cleanly
        return "0oz" * (48 + int(value)) + "1iz" + "0ix" + "1ox" + "}0iy" + "1oy" + "}"

    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if len(results) == 1:
            return leaf(results.pop())
        zero = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 0]
        one = [r for r in rows if ((r >> (n - 1 - i)) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # x = bit, y = 1 - bit; test y for the zero-side, then reload x for
        # the one-side
        return (
            "{X"
            + str(i)
            + "}"
            + "{C"
            + str(i)
            + "}"
            + "0iy"
            + "1oy"
            + sub0
            + "}"
            + "{X"
            + str(i)
            + "}"
            + "0ix"
            + "1ox"
            + sub1
            + "}"
        )

    return node(0, list(range(2**n)))

    return node(0, list(range(2**n)))
