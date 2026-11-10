"""Forbin Boolean program generator: painted blocks behind a branch tree.

Nonconstant tables read all ``8n`` input bits in one multi-assignment and
keep each low bit. The last ``b`` inputs address literal entries through a
shift register in ``table``; the rest pick the block with range-loop ifs, and a
constant span collapses to a call to a printer.  Repeated blocks or subtrees
become one function nested in ``main``.  ``b`` is the width in 3..7 that
gives the shortest program.

Size:
    Two characters per painted entry, O(T);
    n=8 constant zero: 80 chars; n=10 random 1847: 3,111 chars,
    n=12 random 1847: 10,224 chars.

Decisions:
    Constants drain bytes through one function once its cost amortizes;
    the return value is discarded ([ablations.constant_reader_20261102]).

    Sharing a repeated block or subtree: tables tiled from two random
    128-entry blocks shrink, random tables are unchanged
    ([ablations.subtree_sharing]).  Names go out in order of first use
    ([ablations.name_ordering]); the balanced spelling is the only candidate
    ([ablations.balance_race]).  The block width is raced per table
    ([ablations.block_width_race]); the balanced spelling takes the same race.
    The balanced spelling keeps a space only between two word tokens
    ([ablations.balance_word_spaces]).
"""

import re
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from itertools import count, islice
from string import ascii_letters

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    grid_width,
    input_weights,
    short_name,
    subtree_ids,
)
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _join_tokens, wrap_space_delimited
from esolangs.runtime._program import Program

_FORBIN_ALPHABET = ascii_letters
_FORBIN_RESERVED = {"for", "in", "main", "out", "return"}


#: Inputs the shift register answers, raced by length per table.  A block
#: costs two characters an entry against a tree leaf's twenty-odd, but the
#: register's prologue doubles per bit and a narrow block lets distinct
#: subtrees repeat: random tables prefer 5 at n<=9 and 7 from n=12, structured
#: ones 3-5 at every n.  Seven stays the widest -- at eight the block outgrows
#: the whole table at ``n = 7``, a rung ``tests/proofs/deep/linearity.py``
#: fits a line through ([ablations.block_width_race]).
_BLOCK_WIDTHS = (3, 4, 5, 6, 7)


def _forbin_names() -> Iterator[str]:
    """Yield shortest non-keyword identifiers without restarting enumeration."""
    for candidate in count():
        name = short_name(candidate, _FORBIN_ALPHABET)
        if name not in _FORBIN_RESERVED:
            yield name


class _Names:
    """The identifiers one program uses, shortest first in order of use."""

    def __init__(self, n: int, block: int) -> None:
        self._names = _forbin_names()

        def take(size: int) -> list[str]:
            return list(islice(self._names, size))

        # Names go out in the order the program first uses them
        # ([ablations.name_ordering]).
        (self.junk,) = take(1)
        self.bits = take(n)
        (self.table,) = take(1)
        self.cells = take(block)
        self.zero, self.one = take(2)

    def fresh(self) -> str:
        """Return a name no other part of the program uses."""
        return next(self._names)


def _byte(bit: int) -> str:
    """Return an ``out`` argument list printing the digit ``bit``."""
    return ",".join(format(_ASCII_ZERO + bit, "08b"))


def forbin(truth_table: str, width: int | None = None) -> str:
    """Build a Forbin program computing the given truth table.

    A supplied width keeps early returns when they fit; otherwise it uses
    disjoint guards and grammar-token wrapping, with a four-column floor
    for ``main``.
    The shortest block width in ``_BLOCK_WIDTHS`` is kept
    ([ablations.block_width_race]).

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.
    """
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        # [ablations.constant_table_audit_20261101]: no printer closure.
        # The fixed helper amortizes from two bytes; its result is discarded.
        if n >= 2:
            reads = "r{a,a,a,a,a,a,a,a=(in 0)}" + ",".join(["a"] * n) + "=(r 0);"
        else:
            reads = ",".join(["a"] * (8 * n)) + "=(in 0);"
        program = "main{" + reads + f"return(out {_byte(int(truth_table[0]))})" + "}"
        if width is None or grid_width(program) <= width:
            return program
        # The default needs return to keep its two-step bound; narrow out falls off.
        narrow = program.replace("return(out ", "out ").removesuffix(")}") + ";}"
        return _wrapped(narrow, width)
    weights, table = input_weights(truth_table, n)
    retained = len(table).bit_length() - 1
    widths = dict.fromkeys(min(retained, bits) for bits in _BLOCK_WIDTHS)
    return min(
        (_build_projected(weights, table, width, bits) for bits in widths), key=len
    )


def _build_projected(
    weights: Sequence[int], table: str, width: int | None, bits: int
) -> str:
    """Build one register size, reusing the projection across the race."""
    if width is not None:
        natural = _build_projected(weights, table, None, bits)
        if grid_width(natural) <= width:
            return natural
    # Ignored inputs are read into scratch; only retained bits enter the tree.
    n = len(table).bit_length() - 1
    low = min(n, bits)
    high = n - low
    block = 1 << low
    names = _Names(n, block)

    used: set[str] = set()
    defs, tree = _tree(table, n, high, names, used, narrow=width is not None)
    lines = ["main{", _reads(weights, names)]
    # The projected suffix inputs are essential, so some leaf paints a block.
    # Its register reads main's bits and must be nested for lexical scope.
    lines.append(_register(names, block, high, n))
    lines += [*defs, *tree, "}"]
    for bit, name in ((0, names.zero), (1, names.one)):
        if name in used:
            lines.append(f"{name}{{out {_byte(bit)};}}")
    program = "\n".join(lines)
    if width is None:
        return program
    return _wrapped(program, width)


def _wrapped(program: str, width: int) -> str:
    """Wrap grammar tokens, preserving identifiers and range punctuation."""
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\.\.|[^\s]", program)
    return wrap_space_delimited(" ".join(tokens), width)


def _reads(weights: Sequence[int], names: _Names) -> str:
    """Return the one assignment that reads every input's low bit.

    An input of weight 0 is ignored: its low bit goes to the scratch name.
    ``in`` reads one bit, most significant first, so each input byte is 8
    reads and only the last (the LSB, which tells ``'0'`` from ``'1'``) is
    kept.  A single right-hand side is re-evaluated once per target, so
    ``a,a,a,a,a,a,a,b=(in 0)`` drops seven bits into a scratch name.
    """
    targets: list[str] = []
    bits = iter(names.bits)
    for weight in weights:
        targets.extend([names.junk] * 7)
        targets.append(next(bits) if weight else names.junk)
    return f"{','.join(targets)}=(in 0);"


def _tree(
    truth_table: str,
    n: int,
    high: int,
    names: _Names,
    used: set[str],
    *,
    narrow: bool = False,
) -> tuple[list[str], list[str]]:
    """Return the shared functions and the block-selecting branch tree.

    A subtree repeated at its level becomes one function, called from each
    place; the functions nest in ``main``, which holds the input bits.  The
    high inputs pick the block with a range-loop if (``for _:1..b`` runs
    once when ``b`` is 1, not at all when 0; every leaf returns), and a
    constant span collapses to a call to one of the two printers.
    """
    return _TreeBuilder(truth_table, n, high, names, used, narrow=narrow).build()


class _TreeBuilder:
    """Build one branch tree, holding the state its steps share.

    The repeat tally, the shared-function map, the definitions emitted
    so far and the caller's ``used`` set are read and mutated by the
    tally, the emitter and the branch builder alike, so they live on
    ``self`` instead of in closures over the enclosing function.
    """

    def __init__(
        self,
        truth_table: str,
        n: int,
        high: int,
        names: _Names,
        used: set[str],
        *,
        narrow: bool = False,
    ) -> None:
        self.truth_table = truth_table
        self.n = n
        self.high = high
        self.names = names
        self.used = used
        self.narrow = narrow
        self.constant: Callable[[int, int], bool] = constant_span_test(truth_table)
        # A constant table is one entry, which has no levels to name.
        self.ids = subtree_ids(truth_table) if n else []
        self.count: Counter[int] = Counter()
        self.shared: dict[int, str] = {}
        self.defs: list[str] = []

    def _tally(self, level: int, row: int) -> None:
        span = 2 ** (self.n - level)
        if self.constant(row, row + span):
            return
        key = self.ids[level][row // span]
        self.count[key] += 1
        # A repeat's insides are one copy, wherever it ends up.
        if level < self.high and self.count[key] == 1:
            self._tally(level + 1, row)
            self._tally(level + 1, row + span // 2)

    def _call(self, name: str) -> str:
        # The 0 is the wiki's: "something has to be passed to call it".
        return f"{name} 0;" if self.narrow else f"return({name} 0)"

    def _emit(self, level: int, row: int) -> list[str]:
        span = 2 ** (self.n - level)
        if self.constant(row, row + span):
            name = self.names.one if self.truth_table[row] == "1" else self.names.zero
            self.used.add(name)
            return [self._call(name)]
        key = self.ids[level][row // span]
        if key in self.shared:
            return [self._call(self.shared[key])]
        lines = self._branch(level, row, span)
        if self.count[key] > 1:
            name = self.names.fresh()
            self.shared[key] = name
            self.defs.extend([f"{name}{{", *lines, "}"])
            return [self._call(name)]
        return lines

    def _branch(self, level: int, row: int, span: int) -> list[str]:
        names = self.names
        if level == self.high:
            # The literal block starts on its own line; commas let the
            # wrapper split its digits when the block exceeds the width.
            self.used.add(names.table)
            block = ",".join(self.truth_table[row : row + span])
            if self.narrow:
                return [f"{names.table} {block};"]
            return [f"return({names.table}", f"{block})"]
        lower = self._emit(level + 1, row)
        if self.narrow:
            # Both guards run at most once, so a leaf needs no early return.
            lower = [f"for _:1..!{names.bits[level]}{{", *lower, "}"]
        return [
            f"for _:1..{names.bits[level]}{{",
            *self._emit(level + 1, row + span // 2),
            "}",
            *lower,
        ]

    def build(self) -> tuple[list[str], list[str]]:
        """Tally the repeats, then emit the tree from its root."""
        self._tally(0, 0)
        return self.defs, self._emit(0, 0)


def _register(names: _Names, block: int, high: int, n: int) -> str:
    """Return the ``table`` function: a shift register over one block.

    For each low input in turn, one multi-assignment slides the upper half
    of the live window over the lower half when the bit is 1, so the first
    parameter ends up holding the addressed entry, which is printed.
    """
    cells = names.cells
    body: list[str] = []
    live = block
    for level in range(high, n):
        half = live // 2
        slide = f"{','.join(cells[:half])}={','.join(cells[half:live])}"
        body.append(f"for _:1..{names.bits[level]}{{{slide}}}")
        live = half
    body.append(f"out 0,0,1,1,0,0,0,{cells[0]};")
    return f"{names.table} {','.join(cells)}{{{''.join(body)}}}"


def _is_word(char: str) -> bool:
    """Whether ``char`` can continue an identifier, keyword or number."""
    return char.isalnum() or char == "_"


def _balance(table: str, default: str) -> str:
    """Return the token-balanced disjoint-guard spelling.

    A space stays only between two adjacent word tokens; any other token pair
    is already separated, and a row break separates the rest.
    """
    tokens = forbin(table, 1).split()
    # The space rides on the earlier token: a row's last one is trimmed.
    spaced = [
        token + " " if _is_word(token[-1]) and _is_word(following[0]) else token
        for token, following in zip(tokens, [*tokens[1:], "+"], strict=True)
    ]
    width = balanced_token_width(
        spaced, maximum=grid_width(default) - 1, rstrip_rows=True
    )
    rows = _join_tokens(spaced, width, "").split("\n")
    return "\n".join(row.rstrip() for row in rows)


def forbin_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    if request.width is not None:
        return forbin(request.table, request.width)
    return forbin(request.table)


def forbin_balance_request(request: BalanceRequest) -> Program:
    """Lay out source through the declared balance request interface."""
    return _balance(request.table, request.text_source())
