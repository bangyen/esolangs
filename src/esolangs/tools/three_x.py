"""Boolean generator for three x."""

from collections import Counter
from fractions import Fraction
from functools import cache

from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    in_input_order,
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

    Pure and memoized per length.
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


#: Fewest rows of a block worth sharing.
_SHARE_MIN = 4


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

    3x has no call or goto, so a repeated block is deferred instead: the tree
    sets the block's flag where it would sit and the block is written once
    after the tree, guarded by that flag; a node whose halves are equal is
    its first half.  Greedy over aligned blocks of at least ``_SHARE_MIN``
    rows, kept only where the program shrinks.  At 4 rows a share pays in
    46 of the 65,536 n=4 tables, by at most 5 characters; 2 rows pay in none.

    The tree splits in input order (a greedy order saves 2.2% at n=8,
    under the 10% bar).
    """
    return in_input_order(truth_table, _three_x_ordered)


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
    """Return the shorter of the plain tree and the tree sharing blocks.

    A block that repeats is shared when deferring it pays: see
    :func:`_three_x_emit`.  Candidates are the non-constant aligned blocks
    of at least ``_SHARE_MIN`` rows seen twice or more; the greedy loop adds
    the one that shrinks the program most until none does.
    """
    width = len(essential)
    shares: tuple[str, ...] = ()
    best = _three_x_emit(table, perm, essential, n, shares)
    candidates: set[str] = set()
    seen: set[str] = set()
    for rows in (2**k for k in range(_SHARE_MIN.bit_length() - 1, width)):
        for lo in range(0, 2**width, rows):
            block = table[lo : lo + rows]
            if "0" in block and "1" in block:
                if block in seen:
                    candidates.add(block)
                seen.add(block)
    while True:
        trial = min(
            (
                (_three_x_emit(table, perm, essential, n, (*shares, block)), block)
                for block in candidates
                if block not in shares
            ),
            key=lambda pair: len(pair[0]),
            default=None,
        )
        if trial is None or len(trial[0]) >= len(best):
            return best
        best = trial[0]
        shares = (*shares, trial[1])


def _three_x_emit(
    table: str,
    perm: tuple[int, ...],
    essential: list[int],
    n: int,
    shares: tuple[str, ...],
) -> str:
    """Emit the tree with stored 3 and an unset result both meaning one.

    Each block in ``shares`` is written once, after the tree, under its own
    flag; the tree only sets that flag where the block would sit.  A flag is
    unset (3) at the start and any other leaf clears it, so the last write
    wins as it does for the result.
    """
    width = len(essential)
    pieces: list[str | tuple[str, int]] = []
    constant = constant_span_test(table)
    patterns: dict[tuple[int, int], str] = {}
    flag_of = {block: i for i, block in enumerate(shares)}
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

    def write(value: str, var: tuple[str, int] = _RESULT) -> None:
        pieces.append(var)
        pieces.append(("3" if value == "1" else _ZERO) + "v")

    def copy(level: int, *, complement: bool) -> None:
        pieces.append(_RESULT)
        pieces.append(("not" if complement else "bit", essential[level]))
        pieces.append("^v")

    def settle(state: tuple[str, ...], keep: int = -1) -> tuple[str, ...]:
        """Clear every flag but ``keep``, writing only where it may be set."""
        out = list(state)
        for i in range(1, len(state)):
            want = "1" if i - 1 == keep else "0"
            if out[i] != want:
                write(want, ("flag", i - 1))
                out[i] = want
        return tuple(out)

    def build(lo: int, hi: int, depth: int, state: tuple[str, ...]) -> tuple[str, ...]:
        """Emit rows ``[lo, hi)``; return the result's and flags' values after.

        ``""`` means a value depends on bits below, which only costs the
        caller's next sibling its skipped writes.
        """
        nonlocal top
        if flag_of:
            keep = flag_of.get(table[lo:hi], -1)
            if keep >= 0:
                return settle(state, keep)
        if constant(lo, hi):
            state = settle(state)
            if table[lo] != state[0]:
                write(table[lo])
            return (table[lo], *state[1:])
        span = table[lo:hi]
        for level in range(depth, width):
            column = pattern(hi - lo, level - depth)
            if span == column:
                copy(level, complement=False)
                return ("", *settle(state)[1:])
            if span == column.translate(_SWAP):
                copy(level, complement=True)
                return ("", *settle(state)[1:])

        mid = (lo + hi) // 2
        if table[lo:mid] == table[mid:hi]:
            return build(lo, mid, depth + 1, state)
        first = build(lo, mid, depth + 1, state)
        pieces.append(("bit", essential[depth]))
        pieces.append("^(")
        top = "3"
        second = build(mid, hi, depth + 1, first)
        pieces.append(("" if top == "0" else "33x") + ")")
        top = "0"
        return tuple(x if x == y else "" for x, y in zip(first, second, strict=True))

    # Every flag starts set, as an unset variable reads 3.
    build(0, 2**width, 0, ("1",) * (1 + len(shares)))
    flag_of.clear()
    for i, block in enumerate(shares):
        size = len(block)
        lo = next(
            at for at in range(0, len(table), size) if table[at : at + size] == block
        )
        pieces.append(("flag", i))
        pieces.append("^(")
        top = "3"
        build(lo, lo + len(block), width - len(block).bit_length() + 1, ("",))
        pieces.append(("" if top == "0" else "33x") + ")")
        top = "0"
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


LANGUAGE = Language(
    "3x",
    "stack_based.three_x",
    boolean=three_x,
)
