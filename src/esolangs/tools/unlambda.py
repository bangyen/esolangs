r"""Unlambda boolean program builder: a decision tree of promises.

Each half of a node is a ``d`` promise, forced by the ``?`` test that selects
it: Unlambda evaluates an argument before applying it, so a half spelled
inline would read twice a level and print both answers.  ``?c`` hands its
argument the spec's ``i`` on a match and ``v`` otherwise.  The ``?1`` flag is
computed *before* the zero half runs, since that half's read replaces the
character ``?`` looks at -- testing it afterwards asked about a deeper
level's character and fired both halves on ``0`` then ``1``.

Each node is a function of one argument, the *share*:
``` `@`d`k``s``?0i`dZ``?1i`dO ``` reads, takes both flags at once, and returns
``s`` over the two selected promises, so applying it to a share runs the
matching half on that same share.  A repeated subtree ``X`` is bound once,
``` `N`dX ``` runs node ``N`` on the promise of ``X``, and a half that is ``X``
is just ``i`` put first under ``s``: its ``i`` flag returns the share
unforced, and the other half's ``v`` forces it.  ``X`` itself is a ``d``
promise, so it reads only when one path forces it, once.  A ``λ``-bound ``X``
would not do: bracket abstraction through a ``d`` forces the promise the
moment the variable is supplied.
"""

from __future__ import annotations

from functools import cache

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    SubtreeDiagram,
    _validate_truth_table,
)
from esolangs.tools.wrap import _unlambda

#: ``@`` reads a character and applies its argument -- the promise of everything
#: after the read -- to ``i``, or to ``v`` at end of input.
_READ = "`@`d"
#: One unread input at a collapsed leaf: read a character, drop the flag.
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
#: How many levels below a node a bound subtree may sit; bounds the candidates
#: per node (2**4) so the build stays O(T).
_REACH = 4
#: One ``?`` test and one promise wrapper, shared by the size model and writer.
_TEST = "``?{}i"
_PROMISE = "`d"


def _leaf(n: int, level: int, bit: str) -> str:
    # ``v`` because every enclosing branch applies this value again; the
    # reads below a collapsed leaf are the interface and stay.
    printing = f"`.{bit}v"
    unread = n - level
    return printing if not unread else _INERT + _SKIP * unread + printing


def unlambda(truth_table: str) -> str:
    """Return an Unlambda program computing ``truth_table``.

    Reads ``n`` characters, one ``0``/``1`` per input in table order, and
    prints the answer digit.  The tree is of share-taking nodes; subtrees are
    named by :class:`~esolangs.tools.helpers.SubtreeDiagram`.
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
        return len(_BOUND) if key == share else len(_PROMISE) + size(level, key, share)

    @cache
    def node(key: int, share: int | None) -> int:
        zero, one = halves[key]
        level = level_of[key] + 1
        if zero == one:
            if zero == share:
                return len(_OPEN + _FORCE_BOUND)
            return len(_OPEN) + size(level, zero, share)
        tests = half(level, zero, share) + half(level, one, share)
        return len(_OPEN + _SPLIT) + 2 * len(_TEST.format(0)) + tests

    @cache
    def binding(key: int) -> tuple[int, int]:
        """Return the shortest ``` `N`dX ``` over the ``X`` worth binding."""
        # Unbound, a node is never longer than this, so it stays unbound.
        best: tuple[int, int] = (32 * len(truth_table), 0)
        for name in diagram.repeated_near(key, _REACH):
            bound = (
                len("`")
                + len(_PROMISE)
                + node(key, name)
                + size(level_of[name], name, None)
            )
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
        pieces.append(_PROMISE)
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
            pieces.append(_TEST.format(digit))
            if half_key == share:
                pieces.append(_BOUND)
            else:
                pieces.append(_PROMISE)
                write(level, half_key, share)

    root = diagram.ids[0][0]
    if root < 2:
        return _leaf(n, 0, str(root))
    # The root is applied to a share either way: ``v`` when nothing is bound.
    if binding(root)[0] < node(root, None) + len("`v"):
        write_bound(root)
    else:
        pieces.append("`")
        write_node(root, None)
        pieces.append("v")
    return "".join(pieces)


LANGUAGE = Language(
    "Unlambda",
    "other.unlambda",
    reader_checked=True,
    boolean=unlambda,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=_unlambda,
    eof="an exhausted '@' hands its argument v, the spec's branch",
    empty_program="an Unlambda program cannot be empty",
)
