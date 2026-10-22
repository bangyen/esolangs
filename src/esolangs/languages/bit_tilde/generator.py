"""bit~ Boolean program generator: planted table entries addressed by Horner jumps.

Entries are planted left to right, so a skip loop has no terminator ahead of
it: a constant or repeated span costs a ``>`` per cell.  The minority value
is planted, the print windows swapped when it is 0
([ablations.minority_planting]).  An affine table XORs its inputs into one
window instead ([ablations.xor_window]).

Size:
    O(T) cells, two per entry; n=10 random 1847: 4,863 chars, n=10 and: 4,352
    chars.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    affine_form,
    essential_inputs,
    read_at,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Shape

__all__ = ["bit_tilde"]


#: Cells the prologue plants below the table: the ``0`` window at 10..17,
#: the ``1`` window at 1..8, and the two walk terminators at 18 and 27.
_BIT_TILDE_PLANTED = (3, 4, 8, 12, 13, 18, 27)
#: The windows swapped (``0`` at 1..8, ``1`` at 10..17) for a table planted
#: by its zeros, when ones are the majority ([ablations.minority_planting]).
_BIT_TILDE_SWAPPED = (3, 4, 12, 13, 17, 18, 27)

#: Step two cells left and flip, which runs forever over a zero lane and
#: stops on the planted 1 it clears.  The leading ``<~`` primes the loop.
_BIT_TILDE_WALK = "<~{<<~}"


def bit_tilde(truth_table: str) -> str:
    """Return a bit~ program for a binary, MSB-first ``2**n`` truth table.

    Entries occupy every other cell; the intervening lane stays zero so
    weighted conditional left jumps run once. Each read lands the next bit
    at the current pointer; Horner-weighted jumps select the table entry.
    Its bit selects one of two walks, whose final positions print distinct
    eight-cell windows planted as ASCII zero and one in the prologue.
    """
    return _program(truth_table)


def _program(truth_table: str) -> str:
    """Build the planted lookup, or the XOR window for an affine table."""
    n = _validate_truth_table(truth_table)
    lookup = _lookup(truth_table, n)
    if (form := affine_form(truth_table, n)) is None:
        return lookup
    return min(lookup, _xor_window(*form), key=len)


def _xor_window(bias: int, coefficients: list[int]) -> str:
    """XOR every counted input into one window and fix it up to ASCII.

    k digits XOR to ``0011000b`` for odd k and ``0000000b`` for even, so an
    even count flips cells 2 and 3 back; the bias flips cell 7.  An ignored
    input is read into a scratch window ([ablations.xor_window]).
    """
    reads = "".join(")" if c else ">" * 8 + ")" + "<" * 8 for c in coefficients)
    flips = ([2, 3] if sum(coefficients) % 2 == 0 else []) + ([7] if bias else [])
    out, pos = [reads], 0
    for cell in flips:
        out.append(">" * (cell - pos) + "~")
        pos = cell
    return "".join([*out, "<" * pos, "("])


def _lookup(truth_table: str, n: int) -> str:
    """Build the planted lookup, including a one-entry constant table."""
    used = essential_inputs(truth_table, n)
    table = read_at(truth_table, used, n)
    width = len(used)
    # Two cells an entry, above the planted region (max 27, lowest entry 32),
    # and even so that the reads stay in the lane whose jumps land in the zero one.
    start = 2 * len(table) + 34

    # A planted entry costs a ``~`` more than a skipped one: plant the minority.
    swapped = 2 * table.count("1") > len(table)
    planted = set(_BIT_TILDE_SWAPPED if swapped else _BIT_TILDE_PLANTED)
    mark = "0" if swapped else "1"
    planted.update(
        start - 2 * index - 2 for index, bit in enumerate(table) if bit == mark
    )

    prog: list[str] = []
    pos = 0
    for cell in sorted(planted):
        prog.append(">" * (cell - pos) + "~")
        pos = cell
    prog.append(">" * (start - pos))

    depth = {stream: level for level, stream in enumerate(used)}
    for i in range(n):
        # ``)`` XORs; the flip three along, in the jump lane, is undone. A jump
        # sends later reads below this bit; an unused input reads one up.
        if i in depth:
            weight = 2 << (width - 1 - depth[i])
            prog.append(
                ")>>>~>>>>{" + "<" * weight + "}" + "<" * 7
            )  # undo the 7 cells advanced
        else:
            prog.append(">)>>~<<<")

    prog.append("<<{" + _BIT_TILDE_WALK + "}" + _BIT_TILDE_WALK)
    prog.append("<" * 17 + "(")
    return "".join(prog)


LANGUAGE = Language(
    "bit~",
    "bit_tilde",
    category="tape_based",
    boolean=bit_tilde,
    # Not a tree: planted entries a Horner jump addresses.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
