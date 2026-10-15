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

from esolangs.generation.helpers import (
    SubtreeDiagram,
    _validate_truth_table,
)
from esolangs.generation.wrap import _unlambda
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

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
#: per node (2**4) so the build visits O(T) nodes.
_REACH = 4
#: One ``?`` test and one promise wrapper.
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
    named by :class:`~esolangs.generation.helpers.SubtreeDiagram`.
    A node whose halves agree reads and runs the half, and each node binds
    the one subtree within :data:`_REACH` levels that shortens it most, if
    any does; a bound node's subtree sees only its own share.
    """
    n = _validate_truth_table(truth_table)
    diagram = SubtreeDiagram(truth_table)
    halves, level_of, reaches = diagram.halves, diagram.level, diagram.reaches

    # Each candidate is built as text and the shortest kept, so the length
    # chosen by is the program.  A half is copied into every enclosing node:
    # O(T * n) characters, no slower than a cost model plus writer to n=18.
    @cache
    def tree(level: int, key: int, share: int | None) -> str:
        if key < 2:
            return _leaf(n, level, str(key))
        # A share the subtree never reaches is dropped, so it never splits the cache.
        if share is not None and not reaches(key, share):
            share = None
        return min((node(key, share), *bound(key)), key=len)

    @cache
    def node(key: int, share: int | None) -> str:
        zero, one = halves[key]
        level = level_of[key] + 1
        if zero == one:
            return _OPEN + (_FORCE_BOUND if zero == share else tree(level, zero, share))
        order = [("1", one), ("0", zero)] if one == share else [("0", zero), ("1", one)]
        return (
            _OPEN
            + _SPLIT
            + "".join(
                _TEST.format(digit)
                + (_BOUND if half == share else _PROMISE + tree(level, half, share))
                for digit, half in order
            )
        )

    @cache
    def bound(key: int) -> list[str]:
        """Return the shortest ``` `N`dX ``` over the ``X`` worth binding, if any."""
        candidates = (
            "`" + node(key, name) + _PROMISE + tree(level_of[name], name, None)
            for name in diagram.repeated_near(key, _REACH)
        )
        return sorted(candidates, key=len)[:1]  # stable: the first shortest

    root = diagram.ids[0][0]
    if root < 2:
        return _leaf(n, 0, str(root))
    # The root is applied to a share either way: ``v`` when nothing is bound.
    return min(("`" + node(root, None) + "v", *bound(root)), key=len)


LANGUAGE = Language(
    "Unlambda",
    "unlambda",
    category="other",
    reader_checked=True,
    boolean=unlambda,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=_unlambda,
    eof="an exhausted '@' hands its argument v, the spec's branch",
    empty_program="an Unlambda program cannot be empty",
)
