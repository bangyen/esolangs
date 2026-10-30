"""Unlambda Boolean program generator: a decision tree of promises.

A node, ``` `@`d`k``s``?0i`dZ``?1i`dO ```, reads, takes both ``?`` flags at
once (the zero half's read would replace the character tested), and returns
``s`` over its halves' ``d`` promises; ``?c`` gives ``i`` on a match, else
``v``.  A repeated subtree ``X`` is bound once, ``` `N`dX ```; a half that is
``X`` is ``i`` first under ``s``, so ``X`` is forced, and reads, once.
Subtrees are named by :class:`~esolangs.generation.helpers.SubtreeDiagram`;
each node binds the one within ``_REACH`` levels that shortens it most, if
any does, and a bound node's subtree sees only its own share.

Size:
    ~4x per two inputs, ``and`` ~n**2; n=10 random 1847: 15,159 chars.

Decisions:
    Inline halves read twice a level (arguments evaluate first); ``?1``
    tested after the zero half fired both; a ``λ``-bound ``X`` forces on supply.
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
#: A last-level node over leaves ``0`` and ``1`` is the input itself: ``|``
#: hands ``.c`` for the character read; ``s i (k v)`` prints it and keeps ``v``.
_ECHO = "`|``si`kv"
#: Over ``1`` and ``0`` it is the complement: on a ``0`` read print ``1`` and
#: exit (safe, the read is the last), else print ``0``.
_NOT = "``s``?0i``s.1e.0"
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
    """Return an Unlambda program: ``n`` ``0``/``1`` characters in, the answer out."""
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
        if level == n and zero + one == 1:
            return _OPEN + (_ECHO if zero == 0 else _NOT)
        if zero == one:
            # Halves agree: read, then run the one half.
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
        # Race kept: against the first candidate only it saves 33-34% on majority
        # (n=8,10), 14-20% on threshold-3, 8-15% on a 3-block pool, 2% on random.
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
