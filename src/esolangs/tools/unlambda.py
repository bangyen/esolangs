r"""Unlambda boolean program builder: a decision tree of promises.

Each half of a node is a ``d`` promise, forced by the ``?`` test that selects
it: Unlambda evaluates an argument before applying it, so a half spelled
inline would read twice a level and print both answers.  ``?c`` hands its
argument the spec's ``i`` on a match and ``v`` otherwise, which is the whole
conditional and makes a node 25 characters, ``29T - 25`` in all.  The ``?1``
flag is computed *before* the zero half runs, since that half's read replaces
the character ``?`` looks at -- testing it afterwards asked about a deeper
level's character and fired both halves on ``0`` then ``1``.

The shipped build turns each node into a function of one argument, the
*share*: ``` `@`d`k``s``?0i`dZ``?1i`dO ``` reads, takes both flags at once,
and returns ``s`` over the two selected promises, so applying it to a share
runs the matching half on that same share.  Every half is handed the share
for free, so a repeated subtree ``X`` is bound once, ``` `N`dX ``` runs node
``N`` on the promise of ``X``, and a half that is ``X`` is just ``i`` put
first under ``s``: its ``i`` flag returns the share unforced, and the
other half's ``v`` forces it.  ``X`` itself is still a ``d`` promise, so it
reads only when one path forces it, once.  A ``λ``-bound ``X`` would not
do: bracket abstraction through a ``d`` forces the promise the moment the
variable is supplied.
"""

from __future__ import annotations

from functools import cache

from esolangs.tools.helpers import (
    SubtreeDiagram,
    _validate_truth_table,
    separated_tree_text,
)

#: ``@`` reads a line and applies its argument -- the promise of everything
#: after the read -- to ``i``, or to ``v`` at end of input.
_READ = "`@`d"
#: ``` ``flag half v ``: on ``i`` the half is forced, on ``v`` both are eaten.
_FORCE = "``"
#: Compute the ``?1`` flag, run the term after it, return the flag anyway.
_FLAG_ONE = "``k`?1i"
_IF_ZERO = _FORCE + "`?0i`d"
_HEAD = _READ + _FORCE + _FLAG_ONE + _IF_ZERO
_ELSE = "v`d"
_CLOSE = "v"
#: One unread input at a collapsed leaf: read a line, drop the flag.
_SKIP = "``k`@i"
#: Keep a collapsed leaf's value ``v``, not the read's flag.
_INERT = "``kv"
#: A shared node: read, then return a function of the share that ``k``
#: keeps from the read's flag.
_OPEN = _READ + "`k"
#: ``s`` hands the share to both selected halves, the unselected one ``v``.
_SPLIT = "``s"
#: A half that is the share: ``i``, placed first so the other half's ``v``
#: result forces it.
_BOUND = "i"
#: A skip's half that is the share, which nothing else would force.
_FORCE_BOUND = "``si`kv"
#: How many levels below a node a bound subtree may sit: 2**4 candidates a
#: node keeps the build O(T).
_REACH = 4


def _leaf(n: int, level: int, bit: str) -> str:
    # ``v`` because every enclosing branch applies this value again; the
    # reads below a collapsed leaf are the interface and stay.
    printing = f"`.{bit}v"
    unread = n - level
    return printing if not unread else _INERT + _SKIP * unread + printing


def _plain(truth_table: str) -> str:
    """Return the unshared tree of forced promises, ``29T - 25`` at most."""
    n = _validate_truth_table(truth_table)
    return separated_tree_text(
        truth_table,
        lambda level, row: _leaf(n, level, truth_table[row]),
        head=_HEAD,
        between=_ELSE,
        close=_CLOSE,
    )


def _shared(truth_table: str) -> str:
    """Return the tree of share-taking nodes, binding repeated subtrees.

    Subtrees are named by :class:`~esolangs.tools.helpers.SubtreeDiagram`.
    A node whose halves agree reads and runs the half, and each node binds
    the one subtree within :data:`_REACH` levels that shortens it most, if
    any does; a bound node's subtree sees only its own share.
    """
    n = _validate_truth_table(truth_table)
    diagram = SubtreeDiagram(truth_table)
    halves, level_of, reaches = diagram.halves, diagram.level, diagram.reaches

    @cache
    def size(level: int, key: int, share: int | None) -> int:
        if key < 2:
            return len(_leaf(n, level, str(key)))
        if share is not None and not reaches(key, share):
            share = None
        return min(node(key, share), binding(key)[0])

    def half(level: int, key: int, share: int | None) -> int:
        return len(_BOUND) if key == share else 2 + size(level, key, share)

    @cache
    def node(key: int, share: int | None) -> int:
        zero, one = halves[key]
        level = level_of[key] + 1
        if zero == one:
            if zero == share:
                return len(_OPEN + _FORCE_BOUND)
            return len(_OPEN) + size(level, zero, share)
        tests = half(level, zero, share) + half(level, one, share)
        return len(_OPEN + _SPLIT) + 2 * len("``?0i") + tests

    @cache
    def binding(key: int) -> tuple[int, int]:
        """Return the shortest ``` `N`dX ``` over the ``X`` worth binding."""
        # Unbound, a node is never longer than this, so it stays unbound.
        best: tuple[int, int] = (32 * len(truth_table), 0)
        for name in diagram.repeated_near(key, _REACH):
            bound = 3 + node(key, name) + size(level_of[name], name, None)
            if bound < best[0]:
                best = (bound, name)
        return best

    pieces: list[str] = []

    def write(level: int, key: int, share: int | None) -> None:
        if key < 2:
            pieces.append(_leaf(n, level, str(key)))
            return
        if share is not None and not reaches(key, share):
            share = None
        if binding(key)[0] < node(key, share):
            write_bound(key)
        else:
            write_node(key, share)

    def write_bound(key: int) -> None:
        bound = binding(key)[1]
        pieces.append("`")
        write_node(key, bound)
        pieces.append("`d")
        write(level_of[bound], bound, None)

    def write_node(key: int, share: int | None) -> None:
        zero, one = halves[key]
        level = level_of[key] + 1
        pieces.append(_OPEN)
        if zero == one:
            if zero == share:
                pieces.append(_FORCE_BOUND)
            else:
                write(level, zero, share)
            return
        pieces.append(_SPLIT)
        order = [("1", one), ("0", zero)] if one == share else [("0", zero), ("1", one)]
        for digit, half_key in order:
            pieces.append(f"``?{digit}i")
            if half_key == share:
                pieces.append(_BOUND)
            else:
                pieces.append("`d")
                write(level, half_key, share)

    root = diagram.ids[0][0]
    if root < 2:
        return _leaf(n, 0, str(root))
    # The root is applied to a share either way: ``v`` when nothing is bound.
    if binding(root)[0] < node(root, None) + 2:
        write_bound(root)
    else:
        pieces.append("`")
        write_node(root, None)
        pieces.append("v")
    return "".join(pieces)


def unlambda(truth_table: str) -> str:
    """Return an Unlambda program computing ``truth_table``.

    Reads ``n`` lines, one ``0``/``1`` per input in table order, and prints
    the answer digit.
    """
    shared, plain = _shared(truth_table), _plain(truth_table)
    return shared if len(shared) < len(plain) else plain
