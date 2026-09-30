"""FALSE boolean program builder: a decision tree of nested lambdas.

A node reads with ``^``, keeps the bit with ``1&``, and runs the matching
half as a ``[...]?`` lambda; a leaf prints its bit with ``.`` after reading
the inputs below it with ``^%``, which a caller's next program would
otherwise be handed.  A node over two constant halves is its own literal.
The reduced diagram (:func:`_shared`) shares repeated halves.
"""

from __future__ import annotations

from string import ascii_lowercase

from esolangs.tools.helpers import (
    _validate_truth_table,
    subtree_ids,
)

#: ``'0`` and ``'1`` differ in their low bit, so ``1&`` is the bit and ``?``
#: takes any nonzero flag; ``$`` leaves a copy under it for the ``0`` test.
_TEST_ONE = "^1&$["
_SKIP = "^%"
#: The printed bit of a node whose halves are the constants ``0`` and ``1``,
#: and of one whose halves are ``1`` and ``0``: ``'0=`` is ``-1`` on a zero.
_SAME = "^1&"
_FLIPPED = "^'0=_"


def false(truth_table: str, width: int | None = None) -> str:
    """Return a FALSE program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    n = _validate_truth_table(truth_table)
    program = _shared(truth_table, n)
    # The only two-character atom is the ASCII-zero push; multiplication
    # spells that value with single-character operands when width is one.
    if width is None:
        return program
    from esolangs.tools.wrap import wrap_program

    if width == 1:
        program = program.replace("'0", "6 8*")
    return wrap_program(program, "false", width)


Key = tuple[int, int]

#: A node around its two halves, whether written ``[...]`` or fetched ``x;``.
_NODE = (_TEST_ONE[:-1], "?0=", "?")


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
    kids: dict[Key, tuple[Key, Key]] = {}
    pairs: dict[Key, str] = {}
    folds: dict[Key, Key] = {}
    uses: dict[Key, int] = {}
    inner: dict[Key, int] = {}  # of those uses, the ones that are a body
    found: list[list[Key]] = [[] for _ in range(n + 1)]
    for depth in range(n):
        for place, node in enumerate(ids[depth]):
            key = (depth, node)
            if node < 2 or key in kids or key in pairs or key in folds:
                continue  # a leaf, or a node already seen at this level
            zero = (depth + 1, ids[depth + 1][2 * place])
            one = (depth + 1, ids[depth + 1][2 * place + 1])
            if zero[1] < 2 and one[1] < 2:  # a literal: no lambda halves
                read = _SAME if one[1] == 1 else _FLIPPED
                pairs[key] = read + _SKIP * (n - depth - 1) + "."
                continue
            if zero == one:  # the test changes nothing: drop the bit, run it
                folds[key] = zero
                inner[zero] = inner.get(zero, 0) + 1
                if zero not in uses:
                    found[depth + 1].append(zero)
                uses[zero] = uses.get(zero, 0) + 1
                continue
            kids[key] = (zero, one)
            for child in (zero, one):
                if child not in uses:
                    found[depth + 1].append(child)
                uses[child] = uses.get(child, 0) + 1

    size: dict[Key, int] = {}
    names: dict[Key, str] = {}
    free = iter(ascii_lowercase)
    # Deepest first, so a half's length already counts its stored children.
    for key in (key for level in reversed(found) for key in level):
        level, node = key
        if node < 2:
            size[key] = 2 * (n - level) + 2
        elif key in pairs:
            size[key] = len(pairs[key])
        elif key in folds:
            child = folds[key]
            size[key] = len(_SKIP) + (3 if child in names else size[child])
        else:
            halves = (2 if k in names else size[k] + 2 for k in kids[key])
            size[key] = len("".join(_NODE)) + sum(halves)
        # A ``[text]`` use becomes ``x;`` and a bare one ``x;!``.
        gain = uses[key] * size[key] - 3 * inner.get(key, 0) - size[key] - 4
        if gain > 0 and (name := next(free, None)):
            names[key] = name

    def body(key: Key, out: list[str]) -> None:
        level, node = key
        if node < 2:
            out.append(_SKIP * (n - level) + str(node) + ".")
        elif key in pairs:
            out.append(pairs[key])
        elif key in folds:
            out.append(_SKIP)
            if folds[key] in names:
                out.append(names[folds[key]] + ";!")
            else:
                body(folds[key], out)
        else:
            zero, one = kids[key]
            out.append(_NODE[0])
            half(one, out)
            out.append(_NODE[1])
            half(zero, out)
            out.append(_NODE[2])

    def half(key: Key, out: list[str]) -> None:
        if key in names:
            out.append(names[key] + ";")
            return
        out.append("[")
        body(key, out)
        out.append("]")

    out: list[str] = []
    for key, name in names.items():
        out.append("[")
        body(key, out)
        out.append("]" + name + ":")
    body((0, ids[0][0]), out)
    return "".join(out)
