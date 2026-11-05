"""bit~ Boolean program generator: split planting and three-cell weighted jumps.

A block is a zero sentinel and the two cells ``e0``, ``e0 ^ e1`` of an entry
pair; the sentinel lane has stride 3, so the one-shot jump loops land on a
zero cell and each walk is 1.5 cells an entry, not 2 ([ablations.block_lane]).
The first essential input is read between planting the two table halves;
its one path skips the upper half. Later weighted jumps select a block, and
the last input clears the cell it does not select. The minority ``e0`` is
planted, the print windows swapped
when it is 0 ([ablations.minority_planting]).  An affine table XORs its inputs
into one window instead ([ablations.xor_window]). Constants drain that window
and print from the untouched next one.

Size:
    O(T) cells, three per entry pair; n=10 random 1847: 3,104 chars, n=10 and:
    2,610 chars. Constants: n+17+9b characters and commands,
    23+4b+bl(n+17+9b)+bl(n) written bits, b the answer.
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
from esolangs.runtime._definition import RuntimeSpec

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
#: Read the selector, clear the unselected difference, XOR both pair cells.
_SELECTOR = "~" + "<" * 7 + ")" + ">" * 7 + "{~<<{~}>>}<{~>~<}<{~>>~<<}>>"
#: Route the selected bit along the sentinel lane to its print window.
_FINISH = "{" + _BIT_TILDE_WALK + "}" + _BIT_TILDE_WALK + "<" * 17 + "("


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
    if truth_table == truth_table[0] * len(truth_table):
        # Reads share one window; the untouched next window holds the answer.
        flips = [2, 3] + ([7] if truth_table[0] == "1" else [])
        return ")" * n + ">" * 8 + _plant(flips) + "<" * max(flips) + "("
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
    """Return the projected block lookup, split while reading its first bit."""
    used = essential_inputs(truth_table, n)
    return _block_lookup(used, read_at(truth_table, used, n), n)


def _single_lookup(used: list[int], table: str, n: int) -> str:
    """Handle the base case with no non-selector bit to split on."""
    e0 = int(table[0])
    diff = int(table[0]) ^ int(table[-1])
    cells = [*(_BIT_TILDE_SWAPPED if e0 else _BIT_TILDE_PLANTED)]
    if diff:
        cells.append(31)
    prog = [_plant(cells), ">" * (33 - cells[-1])]
    prog.extend(_SELECTOR if i in used else ">)>>~<<<" for i in range(n))
    if not used:
        prog.append("<{~>~<}>")
    return "".join([*prog, _FINISH])


def _pair_cells(
    pairs: list[tuple[int, int]], start: int, begin: int, end: int, *, swapped: bool
) -> list[int]:
    """Return one half's planted cells in ascending order, without sorting."""
    cells = []
    for index in range(end - 1, begin - 1, -1):
        e0, diff = pairs[index]
        sentinel = start - 3 * index
        if diff:
            cells.append(sentinel - 2)
        if e0 != swapped:
            cells.append(sentinel - 1)
    return cells


def _split_head(cells: list[int], prefix: int) -> str:
    """Plant the lower half, folding preceding ignored reads into the walk."""
    if not prefix:
        return _plant(cells)
    # Prefix ASCII reads alter cells2/3 and7. Fold the fixed garbage into
    # planting; clear their unknown low bit en route, before the next window.
    if prefix % 2:
        cells[0] = 2  # cell3 already holds its planted one
    cells.insert(2, 7)
    return ")" * prefix + "".join(
        ">" * (b - a) + ("{~}" if b == 7 else "~") for a, b in pairwise([0, *cells])
    )


def _block_lookup(used: list[int], table: str, n: int) -> str:
    """Read the first bit between planting the lower and upper table halves."""
    width = len(used)
    if width < 2:
        return _single_lookup(used, table, n)
    pairs = [
        (int(table[i]), int(table[i]) ^ int(table[i + 1]))
        for i in range(0, len(table), 2)
    ]
    start = 3 * len(pairs) + 30
    half = len(pairs) // 2
    lower_top = start - 3 * half
    upper_top = start + 6
    swapped = 2 * sum(e0 for e0, _ in pairs) > len(pairs)
    lower = [
        *(_BIT_TILDE_SWAPPED if swapped else _BIT_TILDE_PLANTED),
        *_pair_cells(pairs, start, half, len(pairs), swapped=swapped),
    ]
    prog = [_split_head(lower, used[0]), ">" * (lower_top - 1 - lower[-1])]
    # [ablations.split_first_input_20261102]: the six-cell gap keeps read
    # garbage above the lower half. Both exits land on their own top sentinel.
    prog.append(")" + ">" * 7 + "~{~" + "<" * 5 + "~>~")
    upper = _pair_cells(pairs, upper_top, 0, half, swapped=swapped)
    pos = lower_top + 2
    for cell in upper:
        prog.append(">" * (cell - pos) + "~")
        pos = cell
    prog.append(">" * (upper_top + 6 - pos) + "}" + "<" * 6)
    depth = {stream: level for level, stream in enumerate(used)}
    for i in range(used[0] + 1, n):
        if i not in depth:
            prog.append(">)>>~<<<")
        elif depth[i] == width - 1:
            prog.append(_SELECTOR)
        else:
            weight = 3 << (width - 2 - depth[i])
            prog.append("<" * 7 + ")>>~>~>>>>{" + "<" * weight + "}")
    return "".join([*prog, _FINISH])


LANGUAGE = Language(
    "bit~",
    RuntimeSpec("bit_tilde", category="tape_based"),
    boolean=bit_tilde,
    # Not a tree: planted entries a Horner jump addresses.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
