"""Boolean generator for three x."""

from collections import Counter
from fractions import Fraction
from functools import cache

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    essential_inputs,
    read_at,
)

__all__ = ["three_x"]


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
@cache
def _level(length: int) -> dict[Fraction, str]:
    """Return the constants whose shortest program is ``length`` characters.

    Pure and memoized: a level depends only on the levels below it, so
    concurrent first calls agree instead of racing a shared growing table.
    """
    if length == 1:
        return {Fraction(3): "3"}
    lower = {size: _level(size) for size in range(1, length)}
    seen = set().union(*lower.values())
    fresh: dict[Fraction, str] = {}
    for first, divisors in lower.items():
        for second, subtracted in lower.items():
            tops = lower.get(length - 1 - first - second)
            if tops is None:
                continue
            for a, code_a in divisors.items():
                if a == 0:  # ``x`` divides by the third item down
                    continue
                for b, code_b in subtracted.items():
                    for c, code_c in tops.items():
                        value = (c - b) / a
                        if value in seen or value in fresh:
                            continue
                        fresh[value] = code_a + code_b + code_c + "x"
    return fresh


def _constants(count: int) -> list[str]:
    """Return the ``count`` shortest constant programs, distinct values."""
    codes: list[str] = []
    length = 0
    while len(codes) < count:
        length += 1
        codes.extend(_level(length).values())
    return codes[:count]


_ZERO = "333x"  # (3 - 3) / 3


_ONE = "3333x3x"  # (3 - 0) / 3


_NEG_ONE = "33333xx"  # (0 - 3) / 3


#: From ``[b]``, leave ``3b``.  A set bit is stored as 3 so that copying a
#: bit into the result lands on the result's own 3-or-0 encoding.
_SCALE = "3" + _ZERO + _ONE + "x#" + _ZERO + "#x"


#: From ``[v]``, leave ``3 - v``: a scaled bit's complement.
_COMPLEMENT = _NEG_ONE + "#3#x"


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

    return _three_x_build(table, perm, essential, n)


def _three_x_build(
    table: str,
    perm: tuple[int, ...],
    essential: list[int],
    n: int,
) -> str:
    """Emit the tree with stored 3 and an unset result both meaning one."""
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
        pieces.append(("3" if value == "1" else _ZERO) + "v")

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
                copy(level, complement=False)
                return ""
            if span == column.translate(_SWAP):
                copy(level, complement=True)
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

    build(0, 2**width, 0, "1")
    pieces.append("3" + _ZERO)
    pieces.append(_RESULT)
    pieces.append("^x!")

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
