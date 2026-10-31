"""bit~ Boolean program generator: three-cell blocks addressed by Horner jumps.

A block is a zero sentinel and the two cells ``e0``, ``e0 ^ e1`` of an entry
pair; the sentinel lane has stride 3, so the one-shot jump loops land on a
zero cell and each walk is 1.5 cells an entry, not 2 ([ablations.block_lane]).
The last essential input is read into the sentinel and clears the cell it
does not select; up to five essential inputs the stride-2 lane races it
and the shorter wins.  The minority ``e0`` is planted, the print windows swapped
when it is 0 ([ablations.minority_planting]).  An affine table XORs its inputs
into one window instead ([ablations.xor_window]).

Size:
    O(T) cells, three per entry pair; n=10 random 1847: 3,856 chars, n=10 and:
    3,362 chars.
"""

from itertools import pairwise

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

#: Step three cells left and flip, which runs forever over a zero lane and
#: stops on the planted 1 it clears.
_BIT_TILDE_WALK = "<<<~{<<<~}"
#: Essential inputs up to which the stride-2 build races the block one.  With
#: T entries it is 4T + 18w + 75 chars + minority marks P_s against the
#: block's 3T + 19w + 99 + P_b; P_b - P_s <= T/4 (a differing pair holds a one
#: and a zero), so it wins only if 3T/4 <= 24 + w: never at w >= 6.
_RACE_WIDTH = 5
#: The same walk on the stride-2 lane; the leading ``<~`` primes the loop.
_STRIDE_WALK = "<~{<<~}"


def bit_tilde(truth_table: str) -> str:
    """Return a bit~ program for a binary, MSB-first ``2**n`` truth table.

    Entry pairs occupy blocks ``[e0 ^ e1, e0, sentinel]`` on a lane of stride
    3; the sentinels stay zero so weighted conditional left jumps run once.
    Each read XORs its bit into the sentinel; Horner-weighted jumps select the
    block, the last input selects within it, and the sentinel then holds the
    entry. Its bit selects one of two walks, whose final positions print
    distinct eight-cell windows planted as ASCII zero and one in the prologue.
    """
    return _program(truth_table)


def _program(truth_table: str) -> str:
    """Build the planted lookup, or the XOR window for an affine table."""
    n = _validate_truth_table(truth_table)
    lookup = _lookup(truth_table, n)
    if (form := affine_form(truth_table, n)) is None:
        return lookup
    return min(lookup, _xor_window(*form), key=len)


def _plant(cells: list[int]) -> str:
    """Walk right to each ascending cell and flip it with ``~``."""
    return "".join(">" * (b - a) + "~" for a, b in pairwise([0, *cells]))


def _xor_window(bias: int, coefficients: list[int]) -> str:
    """XOR every counted input into one window and fix it up to ASCII.

    k digits XOR to ``0011000b`` for odd k and ``0000000b`` for even, so an
    even count flips cells 2 and 3 back; the bias flips cell 7.  An ignored
    input is read into a scratch window ([ablations.xor_window]).
    """
    reads = "".join(")" if c else ">" * 8 + ")" + "<" * 8 for c in coefficients)
    flips = ([2, 3] if sum(coefficients) % 2 == 0 else []) + ([7] if bias else [])
    return reads + _plant(flips) + "<" * max(flips, default=0) + "("


def _lookup(truth_table: str, n: int) -> str:
    """Return the block lookup, or the shorter of it and the stride-2 build.

    The block build loses to the stride-2 one on small tables and is strictly
    shorter from six essential inputs ([ablations.block_lane]).
    """
    used = essential_inputs(truth_table, n)
    table = read_at(truth_table, used, n)
    block = _block_lookup(used, table, n)
    if len(used) > _RACE_WIDTH:
        return block
    return min(block, _stride_lookup(used, table, n), key=len)


def _stride_lookup(used: list[int], table: str, n: int) -> str:
    """Build the planted lookup, two cells an entry, including a constant."""
    width = len(used)
    # Above the planted region (max 27, lowest entry 32) and even, so that the
    # reads stay in the lane whose jumps land in the zero one.
    start = 2 * len(table) + 34

    # A planted entry costs a ``~`` more than a skipped one: plant the minority.
    swapped = 2 * table.count("1") > len(table)
    planted = set(_BIT_TILDE_SWAPPED if swapped else _BIT_TILDE_PLANTED)
    mark = "0" if swapped else "1"
    planted.update(
        start - 2 * index - 2 for index, bit in enumerate(table) if bit == mark
    )

    cells = sorted(planted)
    prog = [_plant(cells), ">" * (start - cells[-1])]

    depth = {stream: level for level, stream in enumerate(used)}
    for i in range(n):
        # ``)`` XORs; the flip three along, in the jump lane, is undone. A jump
        # sends later reads below this bit; an unused input reads one up.
        if i in depth:
            weight = 2 << (width - 1 - depth[i])
            prog.append(")>>>~>>>>{" + "<" * weight + "}" + "<" * 7)
        else:
            prog.append(">)>>~<<<")

    prog.append("<<{" + _STRIDE_WALK + "}" + _STRIDE_WALK)
    prog.append("<" * 17 + "(")
    return "".join(prog)


def _block_lookup(used: list[int], table: str, n: int) -> str:
    """Build the block lookup, including a one-entry constant table."""
    width = len(used)
    if not width:
        table += table
    pairs = [
        (int(table[i]), int(table[i]) ^ int(table[i + 1]))
        for i in range(0, len(table), 2)
    ]
    # Sentinels at multiples of 3 from 33 up; the block's cells sit just below.
    start = 3 * len(pairs) + 30

    # A planted ``e0`` costs a ``~`` more than a skipped one: plant the minority.
    swapped = 2 * sum(e0 for e0, _ in pairs) > len(pairs)
    planted = set(_BIT_TILDE_SWAPPED if swapped else _BIT_TILDE_PLANTED)
    for index, (e0, diff) in enumerate(pairs):
        sentinel = start - 3 * index
        if e0 != swapped:
            planted.add(sentinel - 1)
        if diff:
            planted.add(sentinel - 2)

    cells = sorted(planted)
    prog = [_plant(cells), ">" * (start - cells[-1])]

    depth = {stream: level for level, stream in enumerate(used)}
    for i in range(n):
        if i not in depth:
            # Scratch window above the pointer; ``~`` undoes the flip at +3.
            prog.append(">)>>~<<<")
        elif depth[i] == width - 1:
            # Pre-flipped, the sentinel reads ``not x``: clear ``e0 ^ e1``
            # for x = 0, then XOR both cells into the sentinel.
            prog.append("~" + "<" * 7 + ")" + ">" * 7 + "{~<<{~}>>}<{~>~<}<{~>>~<<}>>")
        else:
            # The window's b lands on the sentinel; its flips at -5 and -4
            # are undone before the jump.
            weight = 3 << (width - 2 - depth[i])
            prog.append("<" * 7 + ")>>~>~>>>>{" + "<" * weight + "}")

    if not width:
        prog.append("<{~>~<}>")  # a constant: copy ``e0`` into the sentinel
    prog.append("{" + _BIT_TILDE_WALK + "}" + _BIT_TILDE_WALK)
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
