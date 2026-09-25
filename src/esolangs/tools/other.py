"""Boolean-function generators for languages in the ``other`` category."""

# Every language whose construction is large enough to read on its own owns
# a file; what is left here is three_x and bit_tilde, which are not.  The
# rest are re-exported so this module stays the import site the package and
# tests already use.

from collections import Counter
from fractions import Fraction
from itertools import pairwise

from esolangs.tools.clockwise import clockwise as clockwise

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.container import (
    _container_threshold as _container_threshold,
)
from esolangs.tools.container import container as container
from esolangs.tools.flowchart import (
    _flowchart_cells as _flowchart_cells,
)
from esolangs.tools.flowchart import (
    _flowchart_render as _flowchart_render,
)
from esolangs.tools.flowchart import (
    _flowchart_stacked as _flowchart_stacked,
)
from esolangs.tools.flowchart import flowchart as flowchart
from esolangs.tools.forbin import (
    _FORBIN_RESERVED as _FORBIN_RESERVED,
)
from esolangs.tools.forbin import (
    _forbin_name as _forbin_name,
)
from esolangs.tools.forbin import forbin as forbin
from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    essential_inputs,
    read_at,
)
from esolangs.tools.laserfuck import laserfuck as laserfuck
from esolangs.tools.streetcode import streetcode as streetcode
from esolangs.tools.taglate import taglate as taglate

__all__ = [
    "bit_tilde",
    "clockwise",
    "container",
    "forbin",
    "laserfuck",
    "streetcode",
    "taglate",
    "three_x",
]


# 3x's only literal is ``3`` and its only arithmetic is ``x`` (replace the
# top three items ``a, b, c`` with the exact rational ``(c - b) / a``), so a
# constant is a program of the grammar ``C ::= 3 | C C C x``.  Enumerated by
# length that grammar gives the cheapest *distinct* rationals -- one at 1
# character, one at 4, two at 7, four at 10 -- and a variable key only has to
# be distinct, so the keys are that enumeration rather than 0, 1, 2, ...
# Keys are 64% of an emitted program, and base-3 integer names cost 4 to 45
# characters for the first ten; nineteen of these fit in 13.  The values stay
# small on their own -- the widest at 300 names is 364/243 -- so nothing has
# to bound them.
_CONSTS: list[str] = ["3"]


_CONST_VALUES: set[Fraction] = {Fraction(3)}


_CONST_BY_LEN: dict[int, dict[Fraction, str]] = {1: {Fraction(3): "3"}}


def _constants(count: int) -> list[str]:
    """Return the ``count`` shortest constant programs, distinct values.

    Cached across calls: lengths are only ever appended.
    """
    while len(_CONSTS) < count:
        length = max(_CONST_BY_LEN) + 1
        fresh: dict[Fraction, str] = {}
        for first, divisors in _CONST_BY_LEN.items():
            for second, subtracted in _CONST_BY_LEN.items():
                tops = _CONST_BY_LEN.get(length - 1 - first - second)
                if tops is None:
                    continue
                for a, code_a in divisors.items():
                    if a == 0:  # ``x`` divides by the third item down
                        continue
                    for b, code_b in subtracted.items():
                        for c, code_c in tops.items():
                            value = (c - b) / a
                            if value in _CONST_VALUES or value in fresh:
                                continue
                            fresh[value] = code_a + code_b + code_c + "x"
        _CONST_BY_LEN[length] = fresh
        _CONST_VALUES.update(fresh)
        _CONSTS.extend(fresh.values())
    return _CONSTS[:count]


_ZERO = "333x"  # (3 - 3) / 3


_ONE = "3333x3x"  # (3 - 0) / 3


_NEG_ONE = "33333xx"  # (0 - 3) / 3


#: From ``[b]``, leave ``3b``.  A set bit is stored as 3 so that copying a
#: bit into the result lands on the result's own 3-or-0 encoding.
_SCALE = "3" + _ZERO + _ONE + "x#" + _ZERO + "#x"


#: From ``[v]``, leave ``3 - v``: a scaled bit's complement.
_COMPLEMENT = _NEG_ONE + "#3#x"


#: From ``[v]``, leave ``1 - v``: undoes an inverted result encoding.
_INVERT = _NEG_ONE + "#" + _ONE + "#x"


#: What a complemented column reads as.
_SWAP = str.maketrans("01", "10")


#: The result variable's marker; the others are ``("bit" | "not", depth)``.
_RESULT = ("result", 0)


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).

    Each ``?`` reads one bit, scaled to 3 or 0 and stored under a key from
    :func:`_constants`; the result variable carries the same 3-or-0 encoding
    and the closing ``x`` divides it back to a digit.  A decision tree writes
    it last-wins: a node emits its ``bit == 0`` half unguarded and its
    ``bit == 1`` half inside ``( ... )``, which overwrites -- so no branch
    ever tests a complement, and a subtree that is constant, or that *is* one
    of the bits still under it, collapses to a single write.  Nothing is
    popped off the stack: the interpreter leaves a tested condition where it
    is, and every snippet pushes its own operands, so the junk is never read.

    **The tree splits in whichever order emits the shortest program**
    (:func:`~esolangs.tools.helpers.best_input_order`), spelled in the store
    targets: stream input ``i`` is stored into the name tested at depth
    ``perm.index(i)``.  The screen fires on 17.2% of tables at n=3 (44 of
    256) and 31.9% at n=4 -- unlike Circlefuck (over-estimate) or
    S*bleq/BrainIf (under-estimate).
    """
    return best_input_order(truth_table, _three_x_ordered)


def _three_x_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's 3x program; see :func:`three_x`."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of its inputs is a smaller table: the tree
    # tests only the essential ones, and an ignored input is read and
    # dropped on the stack rather than stored.
    essential = essential_inputs(truth_table, n) or [0]
    table = truth_table
    if len(essential) < n:
        table = read_at(truth_table, essential, n)

    # Two free choices, both worth a build: which table value the stored 3
    # stands for (writing the other costs 3 characters more), and whether the
    # result starts at the unset key's own 3 or at an opening write.
    return min(
        (
            _three_x_build(table, perm, essential, n, true_bit, ambient)
            for true_bit in "10"
            for ambient in "10"
        ),
        key=len,
    )


def _three_x_build(
    table: str,
    perm: tuple[int, ...],
    essential: list[int],
    n: int,
    true_bit: str,
    ambient: str,
) -> str:
    """One build of the tree; see :func:`three_x`.

    ``true_bit`` is the table value the stored 3 stands for and ``ambient``
    the result's value on entry -- free when it is ``true_bit``, since an
    unset key reads as 3, and an opening write otherwise.
    """
    width = len(essential)
    pieces: list[str | tuple[str, int]] = []
    constant = constant_span_test(table)
    patterns: dict[tuple[int, int], str] = {}
    # What the stack top holds inside the guard being emitted: 3 from the
    # guard's own condition (``(`` does not pop it), or 0 once a nested guard
    # has closed (both of its exits leave one).  A write leaves it alone, so
    # it is always known -- and it is what the closing zero costs, nothing or
    # ``33x``, against ``333x`` from a clean stack.
    top = ""

    def pattern(rows: int, level: int) -> str:
        """Return the column a span of ``rows`` reads at its ``level``."""
        if (rows, level) not in patterns:
            half = rows >> (level + 1)
            patterns[rows, level] = ("0" * half + "1" * half) * (rows // (2 * half))
        return patterns[rows, level]

    def write(value: str) -> None:
        pieces.append(_RESULT)
        pieces.append(("3" if value == true_bit else _ZERO) + "v")

    def copy(level: int, *, complement: bool) -> None:
        pieces.append(_RESULT)
        pieces.append(("not" if complement else "bit", essential[level]))
        pieces.append("^v")

    def build(lo: int, hi: int, depth: int, ambient: str) -> str:
        """Emit rows ``[lo, hi)``; return the result's value afterwards.

        ``""`` means the value depends on bits below, which only costs the
        caller's next sibling its skipped writes.
        """
        if constant(lo, hi):
            if table[lo] != ambient:
                write(table[lo])
            return table[lo]
        span = table[lo:hi]
        for level in range(depth, width):
            column = pattern(hi - lo, level - depth)
            if span == column:
                copy(level, complement=true_bit == "0")
                return ""
            if span == column.translate(_SWAP):
                copy(level, complement=true_bit == "1")
                return ""

        nonlocal top
        mid = (lo + hi) // 2
        first = build(lo, mid, depth + 1, ambient)
        pieces.append(("bit", essential[depth]))
        pieces.append("^(")
        top = "3"
        second = build(mid, hi, depth + 1, first)
        pieces.append(("" if top == "0" else "33x") + ")")
        top = "0"
        return first if first == second else ""

    if ambient != true_bit:
        write(ambient)
    build(0, 2**width, 0, ambient)
    pieces.append("3" + _ZERO)
    pieces.append(_RESULT)
    pieces.append("^x!" if true_bit == "1" else "^x" + _INVERT + "!")

    # The reads run in stream order and only the store target moves: stream
    # input ``i`` goes into the name the tree tests at depth ``perm.index(i)``.
    # A complement is stored only where the tree copies one.
    named = {piece for piece in pieces if isinstance(piece, tuple)}
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    head: list[str | tuple[str, int]] = []
    for i in range(n):
        head.append("?")
        depth = depth_of[i]
        if ("bit", depth) in named or ("not", depth) in named:
            head.append(_SCALE)
            if ("not", depth) in named:
                mark = ("not", depth)
                head.extend([_COMPLEMENT, mark, "#v", mark, "^" + _COMPLEMENT])
            head.extend([("bit", depth), "#v"])
    pieces = head + pieces

    # The cheapest key to the most-read name: every use pays its key's
    # length, so this is a rearrangement, and the deep tree levels -- read
    # exponentially more often -- take the short end on their own.
    uses = Counter(piece for piece in pieces if isinstance(piece, tuple))
    order = sorted(uses, key=lambda name: (-uses[name], name))
    keys = dict(zip(order, _constants(len(order)), strict=True))
    return "".join(
        keys[piece] if isinstance(piece, tuple) else piece for piece in pieces
    )


def bit_tilde(truth_table: str) -> str:
    """Build a bit~ program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Each node copies its input into two
    indicators, complements one, and runs both as one-shot ``{``/``}``
    branch loops that clear themselves.

    A read lands a byte on eight cells but only its low bit is consulted,
    so reads *descend* three at a time: a later window stops three below
    the previous low bit and cannot clobber it.  Three is the floor -- a
    level's two flags stay live for its whole subtree, so it owns two
    cells above its bit -- and the pitch is what the constant buys, the
    walk being four fifths of the program at eight.  The third cell, the
    copy temporary, is dead before either branch runs, so it is borrowed
    from the level above.  The tree tests the essential inputs in reverse,
    putting its busiest level beside the result cell.
    """
    n = _validate_truth_table(truth_table)

    used = essential_inputs(truth_table, n) or [0]
    order = used[::-1]
    table = read_at(truth_table, order, n)
    width = len(order)

    prog: list[str] = []
    pos = 0

    def move(dst: int) -> None:
        nonlocal pos
        while pos < dst:
            prog.append(">")
            pos += 1
        while pos > dst:
            prog.append("<")
            pos -= 1

    def copy2(src: int, d1: int, d2: int) -> None:
        """Copy ``src`` to ``d1`` and ``d2``, zeroing ``src``."""
        move(src)
        prog.append("{")
        move(d1)
        prog.append("~")
        move(d2)
        prog.append("~")
        move(src)
        prog.append("~")
        prog.append("}")

    def bit_cell(i: int) -> int:
        """Return the cell holding stream input ``i``'s low bit."""
        return 3 * (n - 1 - i) + 7

    for i in range(n):
        move(bit_cell(i) - 7)
        prog.append(")")

    # One past the deepest level's temporary, so leaf writes are a step away.
    result = bit_cell(order[-1]) + 2

    def set_result() -> None:
        move(result)
        prog.append("~")

    def clear(cell: int) -> None:
        move(cell)
        prog.append("{~}")

    def roles(depth: int) -> tuple[int, int, int]:
        """Level ``depth``'s two flags, under its bit, and its temporary.

        The temporary is borrowed from above (see :func:`bit_tilde`).
        """
        source = bit_cell(order[depth])
        return source - 1, source - 2, source + 1

    # Every node hands its scratch back at zero and a node jumped over
    # never touches it, so one prologue replaces the per-node clears that
    # were a fifth of the source.  A set: a temporary is also a flag.
    for cell in sorted({cell for depth in range(width) for cell in roles(depth)}):
        clear(cell)
    clear(result)

    changes = [0]
    for previous, current in pairwise(table):
        changes.append(changes[-1] + (previous != current))

    def node(start: int, end: int, depth: int) -> None:
        if changes[start] == changes[end - 1]:
            if table[start] == "1":
                set_result()
            return
        half = (start + end) // 2
        source = bit_cell(order[depth])
        zero, one, temp = roles(depth)
        copy2(source, one, temp)
        copy2(temp, source, zero)
        move(zero)
        prog.append("~{")
        node(start, half, depth + 1)
        move(zero)
        prog.append("~}")
        move(one)
        prog.append("{")
        node(half, end, depth + 1)
        move(one)
        prog.append("~}")

    node(0, 1 << width, 0)

    # Copies preserve their source: cell 7 is still the last input byte.
    clear(7)
    move(result)
    prog.append("{")
    move(7)
    prog.append("~")
    move(result)
    prog.append("~")
    prog.append("}")
    move(0)
    prog.append("(")
    return "".join(prog)
