"""3x Boolean program generator: a last-wins decision tree over scaled bits.

Each ``?`` reads one bit, scaled to 3 or 0 and stored under a key from
``_constants``; the result variable carries the same encoding and the closing
``x`` divides it back to a digit.  A node writes its ``bit == 0`` half
unguarded and its ``bit == 1`` half inside ``( ... )``, so no branch tests a
complement; a constant subtree, or one equal to a bit under it, is one write.
3x has no call or goto, so a repeated block of at least ``_SHARE_MIN`` rows
sets a flag in the tree and is written once after it, guarded by that flag.

Size:
    O(T) for dense tables, O(n) for parity and and; n=10 parity: 2,462 chars,
    n=10 and: 472 chars, n=10 random 1847: 8,588 chars.

Decisions:
    At 4 rows a share pays in 46 of the 65,536 n=4 tables, by at most 5
    characters; 2 rows pay in none.  A greedy input order saves 2.2% at n=8,
    under the 10% bar.
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from functools import cache

from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    in_input_order,
    read_at,
)
from esolangs.generation.wrap import _bracket_literal
from esolangs.registry._language import Language

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


class _Kind(Enum):
    """The kind of one piece of the emit stream.

    Declared in the same order as the variable names these replace
    (``"bit" < "flag" < "not" < "result"``), so sorting names by
    ``kind.value`` keeps the cheapest-key assignment byte-identical.
    """

    BIT = auto()
    FLAG = auto()
    NOT = auto()
    RESULT = auto()
    TEXT = auto()


@dataclass(frozen=True)
class _Piece:
    """One unit of the emit stream: verbatim text or a named variable.

    ``text`` carries the literal for :attr:`_Kind.TEXT`; ``depth`` carries
    the variable's tree depth for the other kinds.
    """

    kind: _Kind
    text: str = ""
    depth: int = 0


#: The result variable's marker; the other variables are ``_Piece`` values
#: with kind BIT, NOT, or FLAG and their tree depth.
_RESULT = _Piece(_Kind.RESULT)


class _Top(Enum):
    """What the emitted code leaves on top of the 3x stack inside a guard.

    ``(`` does not pop its condition, and a nested guard's two exits both
    leave a zero; a write leaves the top alone, so it is always known -- and
    it is what closing the guard costs, nothing or ``33x``, against ``333x``
    from a clean stack.  Nothing is popped: every snippet pushes its own
    operands, so the left-over junk is never read.
    """

    CLEAN = auto()  # program start: nothing known is on top
    THREE = auto()  # the guard's own nonzero condition is on top
    ZERO = auto()  # a nested guard closed; both exits left a zero


#: Fewest rows of a block worth sharing.
_SHARE_MIN = 4


def three_x(truth_table: str) -> str:
    """Build a 3x program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  The tree splits in input order.
    """
    return in_input_order(truth_table, _three_x_ordered)


def _three_x_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's 3x program; see :func:`three_x`."""
    n = _validate_truth_table(truth_table)

    # A table that ignores some of its inputs is a smaller table: the tree
    # tests only the essential ones, and an ignored input is read and
    # dropped on the stack rather than stored.  The tree would fold an
    # ignored input anyway (identical output over 39 tables, n=2..8, on the
    # default, width and balance paths); reducing first is for build time,
    # 0.115 s against 0.972 s at n=12 with two ignored inputs.
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


class _Emitter:
    """Builds the tree's pieces; ``flag_of`` maps shared blocks to their flag."""

    def __init__(
        self, table: str, essential: list[int], shares: tuple[str, ...]
    ) -> None:
        self.table = table
        self.essential = essential
        self.width = len(essential)
        self.constant = constant_span_test(table)
        self.shares = shares
        self.flag_of = {block: i for i, block in enumerate(shares)}
        self.pieces: list[_Piece] = []
        self.patterns: dict[tuple[int, int], str] = {}
        self.top = _Top.CLEAN

    def pattern(self, rows: int, level: int) -> str:
        """Return the column a span of ``rows`` reads at its ``level``."""
        if (rows, level) not in self.patterns:
            half = rows >> (level + 1)
            self.patterns[rows, level] = ("0" * half + "1" * half) * (
                rows // (2 * half)
            )
        return self.patterns[rows, level]

    def write(self, value: str, var: _Piece = _RESULT) -> None:
        self.pieces.append(var)
        self.pieces.append(_Piece(_Kind.TEXT, ("3" if value == "1" else _ZERO) + "v"))

    def copy(self, level: int, *, complement: bool) -> None:
        self.pieces.append(_RESULT)
        self.pieces.append(
            _Piece(
                _Kind.NOT if complement else _Kind.BIT,
                depth=self.essential[level],
            )
        )
        self.pieces.append(_Piece(_Kind.TEXT, "^v"))

    def open(self) -> None:
        self.pieces.append(_Piece(_Kind.TEXT, "^("))
        self.top = _Top.THREE

    def close(self) -> None:
        self.pieces.append(
            _Piece(_Kind.TEXT, ("" if self.top is _Top.ZERO else "33x") + ")")
        )
        self.top = _Top.ZERO

    def settle(self, state: tuple[str, ...], keep: int = -1) -> tuple[str, ...]:
        """Clear every flag but ``keep``, writing only where it may be set."""
        out = list(state)
        for i in range(1, len(state)):
            want = "1" if i - 1 == keep else "0"
            if out[i] != want:
                self.write(want, _Piece(_Kind.FLAG, depth=i - 1))
                out[i] = want
        return tuple(out)

    def build(
        self, lo: int, hi: int, depth: int, state: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Emit rows ``[lo, hi)``; return the result's and flags' values after.

        ``""`` means a value depends on bits below, which only costs the
        caller's next sibling its skipped writes.  A node whose halves are
        equal is its first half.
        """
        table = self.table
        if self.flag_of:
            keep = self.flag_of.get(table[lo:hi], -1)
            if keep >= 0:
                return self.settle(state, keep)
        if self.constant(lo, hi):
            state = self.settle(state)
            if table[lo] != state[0]:
                self.write(table[lo])
            return (table[lo], *state[1:])
        span = table[lo:hi]
        for level in range(depth, self.width):
            column = self.pattern(hi - lo, level - depth)
            if span == column:
                self.copy(level, complement=False)
                return ("", *self.settle(state)[1:])
            if span == column.translate(_SWAP):
                self.copy(level, complement=True)
                return ("", *self.settle(state)[1:])

        mid = (lo + hi) // 2
        if table[lo:mid] == table[mid:hi]:
            return self.build(lo, mid, depth + 1, state)
        first = self.build(lo, mid, depth + 1, state)
        self.pieces.append(_Piece(_Kind.BIT, depth=self.essential[depth]))
        self.open()
        second = self.build(mid, hi, depth + 1, first)
        self.close()
        return tuple(x if x == y else "" for x, y in zip(first, second, strict=True))

    def emit_all(self) -> list[_Piece]:
        """Return the tree, each shared block under its flag, then the output."""
        table, shares = self.table, self.shares
        # Every flag starts set, as an unset variable reads 3.
        self.build(0, 2**self.width, 0, ("1",) * (1 + len(shares)))
        self.flag_of.clear()
        for i, block in enumerate(shares):
            size = len(block)
            lo = next(
                at
                for at in range(0, len(table), size)
                if table[at : at + size] == block
            )
            self.pieces.append(_Piece(_Kind.FLAG, depth=i))
            self.open()
            self.build(lo, lo + size, self.width - size.bit_length() + 1, ("",))
            self.close()
        self.pieces.append(_Piece(_Kind.TEXT, "3" + _ZERO))
        self.pieces.append(_RESULT)
        self.pieces.append(_Piece(_Kind.TEXT, "^x!"))
        return self.pieces


def _read_head(pieces: list[_Piece], perm: tuple[int, ...], n: int) -> list[_Piece]:
    """Return the input reads, storing a complement only where the tree copies one.

    The reads run in stream order and only the store target moves: stream
    input ``i`` goes into the name the tree tests at depth ``perm.index(i)``.
    """
    named = {piece for piece in pieces if piece.kind is not _Kind.TEXT}
    depth_of = {stream: depth for depth, stream in enumerate(perm)}
    head: list[_Piece] = []
    for i in range(n):
        head.append(_Piece(_Kind.TEXT, "?"))
        depth = depth_of[i]
        bit = _Piece(_Kind.BIT, depth=depth)
        mark = _Piece(_Kind.NOT, depth=depth)
        if bit in named or mark in named:
            head.append(_Piece(_Kind.TEXT, _SCALE))
            if mark in named:
                head.extend(
                    [
                        _Piece(_Kind.TEXT, _COMPLEMENT),
                        mark,
                        _Piece(_Kind.TEXT, "#v"),
                        mark,
                        _Piece(_Kind.TEXT, "^" + _COMPLEMENT),
                    ]
                )
            head.extend([bit, _Piece(_Kind.TEXT, "#v")])
    return head


def _key_pieces(pieces: list[_Piece]) -> str:
    """Render ``pieces``, giving the cheapest key to the most-read name.

    Every use pays its key's length, so this is a rearrangement, and the deep
    tree levels -- read exponentially more often -- take the short end on
    their own.
    """
    uses = Counter(piece for piece in pieces if piece.kind is not _Kind.TEXT)
    order = sorted(uses, key=lambda name: (-uses[name], name.kind.value, name.depth))
    keys = dict(zip(order, _constants(len(order)), strict=True))
    return "".join(
        keys[piece] if piece.kind is not _Kind.TEXT else piece.text for piece in pieces
    )


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
    body = _Emitter(table, essential, shares).emit_all()
    return _key_pieces(_read_head(body, perm, n) + body)


LANGUAGE = Language(
    "3x",
    "three_x",
    category="stack_based",
    boolean=three_x,
    wrap=_bracket_literal,
)
