"""FALSE boolean program builder: a decision tree of nested lambdas.

A node reads with ``^``, keeps the bit with ``1&``, and runs the matching
half as a ``[...]?`` lambda; a leaf prints its bit with ``.`` after reading
the inputs below it with ``^%``, which a caller's next program would
otherwise be handed.  A node over two constant halves is its own literal.
The reduced diagram (:func:`_shared`) shares repeated halves.
"""

from __future__ import annotations

import re
from string import ascii_lowercase
from typing import NamedTuple

from esolangs.generation.helpers import (
    _validate_truth_table,
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
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``'0`` and ``'1`` differ in their low bit, so ``1&`` is the bit and ``?``
#: takes any nonzero flag; ``$`` leaves a copy under it for the ``0`` test.
_TEST_ONE = "^1&$["
_SKIP = "^%"
#: The printed bit of a node whose halves are the constants ``0`` and ``1``,
#: and of one whose halves are ``1`` and ``0``: ``'0=`` is ``-1`` on a zero.
_SAME = "^1&"
_FLIPPED = "^'0=_"
Key = tuple[int, int]  # (level, subtable id)


class _Literal(NamedTuple):
    """A node over two constants: its whole text."""

    text: str


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
    # The only two-character atom is the ASCII-zero push; multiplication
    # spells that value with single-character operands when width is one.
    if width is None:
        return program
    if width == 1:
        program = program.replace("'0", "6 8*")
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
    nodes: dict[Key, _Literal | _Fold | _Split] = {}
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
            if zero[1] < 2 and one[1] < 2:  # a literal: no lambda halves
                read = _SAME if one[1] == 1 else _FLIPPED
                nodes[key] = _Literal(read + _SKIP * (n - depth - 1) + ".")
                continue
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
            case _Literal(literal):
                return literal
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
    return stores + render((0, ids[0][0]))


def _balance(table: str, default: str) -> str:
    """Compare ordinary token fits above width one and the alternate zero push."""
    tokens = re.findall(_FALSE_COMMAND, default)
    width = balanced_token_width(tokens, minimum=2)
    return min(
        default, _join_tokens(tokens, width, ""), false(table, 1), key=balance_score
    )


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
)
