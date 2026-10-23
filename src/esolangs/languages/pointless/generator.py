"""Pointless Boolean program generator: a shared decision diagram of functions.

The one ``!`` makes cell 0 a 1, so ``+`` turns cells 1..51+2n from 0 to 1
(the wiki's Hello world setup); with ``tape[v]`` = 1, ``+`` is then an
increment, which builds ``0`` (48) in cell 50 and ``1`` (49) in cell 51
before ``tape[48]`` and cell 0 go back to 0.  Level ``d`` reads its
character into ``X = 52 + 2d`` and ``=`` maps it to its bit; ``[`` tests
``tape[bit]``, so ``[>-<->>"one"<<]`` runs only on 1, clearing ``X`` and
the flag ``X + 1``, and ``>[->"zero"<]<`` runs on the flag left at 1.  Each
distinct subtable (``subtree_ids``) is one function entered and left at its
``X``; equal halves skip the branch, and a constant subtable descends
level by level to a leaf that prints from cell 50 or 51.

A function stays declared only where that is shorter than pasting its body
at each call (:func:`_inlined`).

Size:
    O(T) size and build time, 26n + 309 steps at most; n=10 parity: 1,060
    chars, n=10 random 1847: 6,253 chars (8,558 declaring every function;
    26% less over five random tables at n=10, 11% at n=3, no added steps).
"""

import re

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

_OUT = 50  # cell 50 holds "0", cell 51 holds "1"
_X = 52  # level d's character and bit cell is 52 + 2d, its flag 53 + 2d


def _setup(n: int) -> str:
    """Fill cells 1..51+2n with 1, build the two digits, clear 48 and 0."""
    top = _X + 2 * n - 1
    return (
        "!"
        + ">+" * top
        + "<" * (top - _OUT)
        + "+" * 47
        + ">"
        + "+" * 48
        + "<" * (_OUT + 1 - 48)
        + "-"
        + "<" * 48
        + "-"
        + ">" * _X
    )


#: Break anywhere but inside a quoted name, which a newline would rename.
_wrap = TokenWrapper(r'"[^"]*"|[\s\S]')


class _Functions:
    """The body of every distinct subtable, children named before parents."""

    def __init__(self, ids: list[list[int]], n: int) -> None:
        self._ids = ids
        self._n = n
        self.bodies: dict[str, str] = {}

    def constant(self, sub: int, depth: int) -> str:
        """Name the constant function for ``sub`` at ``depth``, building it once.

        Built like any other node: both children are the same constant one
        level down, so the body is the skip spelling, until the last level,
        whose leaf moves to the print cell, prints, and returns. The descent
        pays the away-and-back moves once, at the leaf; a read-all body paid
        them at every depth where a constant subtable occurred.
        """
        key = f"c{sub}d{depth}"
        if key not in self.bodies:
            self.bodies[key] = ""  # reserve: children are named first
            if depth == self._n:
                away = _X + 2 * depth - _OUT - sub
                body = "<" * away + "." + ">" * away
            else:
                body = f',>>"{self.constant(sub, depth + 1)}"<<'
            self.bodies[key] = body
        return key

    def build(self, depth: int, k: int) -> None:
        """Fill in the body of the subtable at ``depth``, index ``k``."""
        sub = self._ids[depth][k]
        self.bodies[str(sub)] = ""  # reserve: children are named first
        zero, one = (self.child(depth + 1, 2 * k + b) for b in (0, 1))
        if zero == one:
            body = f',>>"{zero}"<<'
        else:
            body = f',=[>-<->>"{one}"<<]>[->"{zero}"<]<'
        self.bodies[str(sub)] = body

    def child(self, depth: int, k: int) -> str:
        """Return the function name for the subtable at ``depth``, index ``k``."""
        sub = self._ids[depth][k]
        if sub < 2:
            return self.constant(sub, depth)
        if str(sub) not in self.bodies:
            self.build(depth, k)
        return str(sub)


def pointless(truth_table: str) -> str:
    """Build a Pointless program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    functions = _Functions(subtree_ids(truth_table), n)
    root = functions.child(0, 0)
    return _setup(n) + _inlined(functions.bodies, root)


def _inlined(functions: dict[str, str], root: str) -> str:
    """Return the root's call then the declarations, inlining where shorter.

    A call runs the body and returns, so pasting the body in its place is
    equivalent.  Callees first, a function stays declared only when its
    uses times its length beat the declaration plus the uses of its call.
    """
    calls = {key: _CALL.findall(body) for key, body in functions.items()}
    uses = dict.fromkeys(functions, 0)
    uses[root] = 1
    for names in calls.values():
        for name in names:
            uses[name] += 1
    size: dict[str, int] = {}
    declared: set[str] = set()
    # Callees first: a callee shared by two callers can be declared between
    # them, so declaration order is not enough.  Depth is at most n + 1.
    for key in _callees_first(calls, root):
        size[key] = len(functions[key]) + sum(
            size[name] - len(name) - 2 for name in calls[key] if name not in declared
        )
        call = len(key) + 2
        if uses[key] * size[key] > call + 2 + size[key] + uses[key] * call:
            declared.add(key)
    main = f'"{root}"' if root in declared else _expand(functions, declared, root)
    return main + "".join(
        f'"{key}"{{{_expand(functions, declared, key)}}}'
        for key in functions
        if key in declared
    )


def _callees_first(calls: dict[str, list[str]], root: str) -> list[str]:
    """Return the functions reachable from ``root``, each after its callees."""
    order: list[str] = []
    seen = {root}
    stack: list[tuple[str, bool]] = [(root, False)]
    while stack:
        key, expanded = stack.pop()
        if expanded:
            order.append(key)
            continue
        stack.append((key, True))
        for name in reversed(calls[key]):
            if name not in seen:
                seen.add(name)
                stack.append((name, False))
    return order


def _expand(functions: dict[str, str], declared: set[str], key: str) -> str:
    """Return ``key``'s body with every undeclared call pasted in, recursively."""
    return _CALL.sub(
        lambda m: m[0] if m[1] in declared else _expand(functions, declared, m[1]),
        functions[key],
    )


#: A call in a body, ``"name"``; names hold no quote.
_CALL = re.compile(r'"([^"]*)"')


LANGUAGE = Language(
    "Pointless",
    "pointless",
    category="tape_based",
    boolean=pointless,
    contract=BooleanContract(input_shape="char_stream"),
    # Whitespace is a comment, so a newline anywhere outside a name is harmless.
    wrap=_wrap,
)
