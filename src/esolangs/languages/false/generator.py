"""FALSE Boolean program generator: a decision diagram raced with a formula.

A node of the diagram reads with ``^``, keeps the bit with ``1&``, and
runs the matching half as a ``[...]?`` lambda; a leaf prints its bit
with ``.`` after reading the inputs below it with ``^%``, which a
caller's next program would otherwise be handed; the leaf a fold
chain reaches from the root prints first and reads bare ``^``.
The reduced diagram (:func:`_shared`) shares repeated halves.

The second build (:func:`_expression`) stores each essential input
and evaluates a Boolean formula over the stored bits, built by
Shannon decomposition.  It wins where few halves repeat -- on a
random table the diagram pays some twelve characters a node to
share halves that never recur -- and the diagram keeps the tables
whose halves do repeat.  The shorter text wins per table, ties to
the diagram, so no table grows.  A formula is evaluated whole,
where the diagram executes one path.  A combine can leave FALSE's
-1 true value on the stack where the answer is 1, so the value is
masked with ``1&`` before the print: the printed digit is exactly
the answer bit.

Size:
    O(n) for parity, O(T) for random tables; n=10 parity: 100 chars,
    n=10 random 1847: 2,161 chars.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from string import ascii_lowercase
from sys import maxsize
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import (
    _FALSE_COMMAND,
    _false,
    _join_tokens,
    balance_score,
    wrap_program,
)
from esolangs.languages.false.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``'0`` and ``'1`` differ in their low bit, so ``1&`` is the bit and ``?``
#: takes any nonzero flag; ``$`` leaves a copy under it for the ``0`` test.
_TEST_ONE = "^1&$["
_SKIP = "^%"
Key = tuple[int, int]  # (level, subtable id)


class _Fold(NamedTuple):
    """A node with equal halves: the one half, run bare."""

    child: Key


class _Split(NamedTuple):
    """A node over two different halves."""

    zero: Key
    one: Key


def false(truth_table: str, width: int | None = None) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` characters, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)
    program = _shared(truth_table, n)
    ess = essential_inputs(truth_table, n)
    # The expression build names its variables by input position, and
    # FALSE variables are a-z: past the alphabet it cannot be built.
    if not ess or ess[-1] < len(ascii_lowercase):
        expression = _expression(truth_table, n, ess)
        if len(expression) < len(program):
            program = expression
    if width is None:
        return program
    return wrap_program(program, "false", width)


#: A node around its two halves, whether written ``[...]`` or fetched ``x;``.
_OPEN, _BETWEEN, _CLOSE = _TEST_ONE[:-1], "?0=", "?"


def _shared(truth_table: str, n: int) -> str:
    """Return the tree with repeated halves stored in variables and fetched.

    A half is a lambda either way, so ``[text]`` becomes ``x;`` wherever it
    repeats and ``[text]x:`` runs once up front; ``?`` pops a fetched lambda
    as it does a written one, and the reads stay in the lambdas, in order.
    A half is keyed by (level, subtable id) -- a leaf's text depends on its
    level -- and stored bottom-up while its in-degree in the diagram pays for
    the store: ``k`` uses save ``k * len(text)`` against ``len(text) + 4``.
    Every use in the text is an edge of the diagram, so a store only gains.
    A node with equal halves drops its bit with ``^%`` and runs the half
    bare, fetched as ``x;!``; the read still happens where the tree had it.
    26 variables, handed out deepest first, cap the stores.
    """
    ids = subtree_ids(truth_table)
    nodes: dict[Key, _Fold | _Split] = {}
    uses: dict[Key, int] = {}
    inner: dict[Key, int] = {}  # of those uses, the ones that are a body
    found: list[list[Key]] = [[] for _ in range(n + 1)]

    def use(child: Key, depth: int) -> None:
        if child not in uses:
            found[depth].append(child)
        uses[child] = uses.get(child, 0) + 1

    for depth in range(n):
        for place, node in enumerate(ids[depth]):
            key = (depth, node)
            if node < 2 or key in nodes:
                continue  # a leaf, or a node already seen at this level
            zero = (depth + 1, ids[depth + 1][2 * place])
            one = (depth + 1, ids[depth + 1][2 * place + 1])
            if zero == one:  # the test changes nothing: drop the bit, run it
                nodes[key] = _Fold(zero)
                inner[zero] = inner.get(zero, 0) + 1
                use(zero, depth + 1)
                continue
            nodes[key] = _Split(zero, one)
            use(zero, depth + 1)
            use(one, depth + 1)

    text: dict[Key, str] = {}
    names: dict[Key, str] = {}
    free = iter(ascii_lowercase)

    def half(key: Key) -> str:
        return names[key] + ";" if key in names else "[" + text[key] + "]"

    def render(key: Key) -> str:
        level, node = key
        if node < 2:
            return _SKIP * (n - level) + str(node) + "."
        match nodes[key]:
            case _Fold(child):
                return _SKIP + (names[child] + ";!" if child in names else text[child])
            case _Split(zero, one):
                return _OPEN + half(one) + _BETWEEN + half(zero) + _CLOSE

    # Deepest first, so a half's text already fetches its stored children.
    for key in (key for level in reversed(found) for key in level):
        text[key] = render(key)
        size = len(text[key])
        # Each ``[text]`` use becomes ``x;`` (saves size - 2), a bare one
        # ``x;!`` (saves size - 3); the store ``[text]x:`` costs size + 4.
        gain = uses[key] * size - 3 * inner.get(key, 0) - size - 4
        if gain > 0 and (name := next(free, None)):
            names[key] = name

    stores = "".join("[" + text[key] + "]" + name + ":" for key, name in names.items())
    return stores + _root_text((0, ids[0][0]), nodes, names, render, n)


def _root_text(
    key: Key,
    nodes: dict[Key, _Fold | _Split],
    names: dict[Key, str],
    render: Callable[[Key], str],
    n: int,
) -> str:
    """Render the root, draining bare at the end of a fold chain.

    A leaf reached from the root through folds only is the
    last text the program runs, so it prints first and reads the
    remaining inputs with bare ``^`` instead of ``^%`` (a constant
    table: 2n+2 -> n+2, measured n = 2..8).  Under a split the same end
    stays stack-neutral: the split's ``?0=`` plumbing resumes above it
    and expects its bit back on top.
    """
    parts: list[str] = []
    while key[1] >= 2:
        node = nodes[key]
        if not isinstance(node, _Fold) or node.child in names:
            break
        parts.append(_SKIP)
        key = node.child
    level, sub = key
    parts.append(str(sub) + "." + "^" * (n - level) if sub < 2 else render(key))
    return "".join(parts)


def _cofactor(table: str, j: int) -> tuple[str, str]:
    """Split ``table`` on its j-th remaining input (0 = MSB)."""
    rows = len(table)
    vars_left = rows.bit_length() - 1
    stride = 1 << (vars_left - 1 - j)
    zero = "".join(table[i : i + stride] for i in range(0, rows, 2 * stride))
    one = "".join(
        table[i + stride : i + 2 * stride] for i in range(0, rows, 2 * stride)
    )
    return zero, one


def _complement(table: str) -> str:
    return table.translate(str.maketrans("01", "10"))


def _splits(table: str, positions: tuple[int, ...]) -> range | tuple[int, ...]:
    """Split variables worth trying at this node.

    Trying every split variable is exponential in the number of
    distinct (subtable, split-set) states on random tables; it pays
    only where subtables are small or structured.  Above 512 rows
    split the first remaining variable (random tables are
    split-order-insensitive in expectation).
    """
    if len(table) <= 512 or len(positions) <= 6:
        return range(len(positions))
    return (0,)


def _expression(truth_table: str, n: int, ess: list[int]) -> str:
    """Return the expression-form build: stored inputs, a formula, a print.

    Each essential input is read, bit-extracted and stored
    (``^1&x:``, 5 chars); each remaining input is drained (``^%``,
    2 chars).  The body is a Boolean formula over the stored bits,
    built by memoized Shannon decomposition over the table projected
    onto its essential inputs: at each node the cheapest combine
    wins -- a dropped input when the halves agree, the xor collapse
    (``+b&``) for complementary halves, a one-char ``&`` or ``|``
    step (or its 5-char negated form, ``a=|`` / ``a=&``) when a
    cofactor is constant, else the mux sum (``$`` ... ``+b&`` ...
    ``&+b&``, 10 chars over the two halves).  Variable letters are
    the inputs' own positions.  In the combines a bare letter is a
    variable reference, whose integer is its index -- ``a`` is the
    constant 0 and ``b`` the constant 1 -- so ``a=`` tests a fetched
    bit against 0 and ``+b&`` folds a fetch into a sum's parity.

    A formula is evaluated whole, where the diagram executes one
    path; the race in :func:`false` keeps whichever text is shorter.
    The body's value can be -1 where the answer is 1 (a combine's
    true value), so ``1&`` masks it to the bit before ``.`` prints:
    +2 chars on every expression-form program.
    """
    # Project the table onto its essential inputs, in original order.
    sub = read_at(truth_table, ess, n)
    letters = {pos: chr(ord("a") + pos) for pos in ess}

    search = _ExpressionSearch(letters)
    prologue = "".join(f"^1&{letters[i]}:" if i in letters else "^%" for i in range(n))
    return prologue + search.text(sub, tuple(ess)) + "1&."


class _ExpressionSearch:
    """One projected table's memoized Shannon decomposition.

    ``size`` prices each (subtable, remaining inputs) state once and
    ``text`` materialises the cheapest body over the same states.
    The caches live on the instance: one search serves one table
    and is dropped with it.
    """

    def __init__(self, letters: dict[int, str]) -> None:
        self._letters = letters
        self._sizes: dict[tuple[str, tuple[int, ...]], int] = {}
        self._texts: dict[tuple[str, tuple[int, ...]], str] = {}

    def size(self, table: str, positions: tuple[int, ...]) -> int:
        """The cheapest body length for ``table`` over ``positions``."""
        key = (table, positions)
        if key not in self._sizes:
            self._sizes[key] = self._price(table, positions)
        return self._sizes[key]

    def _price(self, table: str, positions: tuple[int, ...]) -> int:
        if table == "0" * len(table) or table == "1" * len(table):
            return 1
        if len(positions) == 1:
            return 2 if table == "01" else 4  # fetch; or 1<fetch>-
        best = maxsize
        for j in _splits(table, positions):
            rest = positions[:j] + positions[j + 1 :]
            a, b = _cofactor(table, j)
            if a == b:
                best = min(best, self.size(a, rest))
                continue
            if b == _complement(a):
                best = min(best, self.size(a, rest) + 5)
            if a == "0" * len(a):
                best = min(best, self.size(b, rest) + 3)
            elif a == "1" * len(a):
                best = min(best, self.size(b, rest) + 5)
            if b == "0" * len(b):
                best = min(best, self.size(a, rest) + 5)
            elif b == "1" * len(b):
                best = min(best, self.size(a, rest) + 3)
            best = min(best, self.size(a, rest) + self.size(b, rest) + 10)
        return best

    def text(self, table: str, positions: tuple[int, ...]) -> str:
        """The cheapest body text for ``table`` over ``positions``."""
        key = (table, positions)
        if key not in self._texts:
            self._texts[key] = self._build(table, positions)
        return self._texts[key]

    def _build(self, table: str, positions: tuple[int, ...]) -> str:
        if table == "0" * len(table):
            return "0"
        if table == "1" * len(table):
            return "1"
        if len(positions) == 1:
            fetch = self._letters[positions[0]] + ";"
            return fetch if table == "01" else "1" + fetch + "-"
        options: list[tuple[int, str]] = []
        for j in _splits(table, positions):
            rest = positions[:j] + positions[j + 1 :]
            a, b = _cofactor(table, j)
            fetch = self._letters[positions[j]] + ";"
            if a == b:
                options.append((self.size(a, rest), self.text(a, rest)))
                continue
            if b == _complement(a):
                text = self.text(a, rest) + fetch + "+b&"
                options.append((self.size(a, rest) + 5, text))
            if a == "0" * len(a):
                options.append(
                    (self.size(b, rest) + 3, self.text(b, rest) + fetch + "&")
                )
            elif a == "1" * len(a):
                # f = 1 when x=0, B when x=1: B | (x==0 ? -1 : 0)
                options.append(
                    (self.size(b, rest) + 5, self.text(b, rest) + fetch + "a=|")
                )
            if b == "0" * len(b):
                options.append(
                    (self.size(a, rest) + 5, self.text(a, rest) + fetch + "a=&")
                )
            elif b == "1" * len(b):
                options.append(
                    (self.size(a, rest) + 3, self.text(a, rest) + fetch + "|")
                )
            text = (
                self.text(a, rest) + "$" + self.text(b, rest) + "+b&" + fetch + "&+b&"
            )
            options.append((self.size(a, rest) + self.size(b, rest) + 10, text))
        return min(options, key=lambda pair: pair[0])[1]


def _balance(_table: str, default: str) -> str:
    """Compare the default with its balanced token fit."""
    tokens = re.findall(_FALSE_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(default, _join_tokens(tokens, width, ""), key=balance_score)


LANGUAGE = Language(
    "FALSE",
    "false",
    category="stack_based",
    reader_checked=True,
    boolean=false,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # ``'x`` and ``.x``/``?x`` take the character after them.
    wrap=_false,
    balance=_balance,
    eof="an exhausted '^' is the spec's -1",
    proof_execution=(execution, False, (3, 6)),
)
