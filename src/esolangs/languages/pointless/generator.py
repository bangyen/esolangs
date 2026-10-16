"""Pointless Boolean program generator: a shared decision diagram of functions.

The one ``!`` makes cell 0 a 1, so ``+`` turns cells 1..51+2n from 0 to 1
(the wiki's Hello world setup); with ``tape[v]`` = 1, ``+`` is then an
increment, which builds ``0`` (48) in cell 50 and ``1`` (49) in cell 51
before ``tape[48]`` and cell 0 go back to 0.  Level ``d`` reads its
character into ``X = 52 + 2d`` and ``=`` maps it to its bit; ``[`` tests
``tape[bit]``, so ``[>-<->>"one"<<]`` runs only on 1, clearing ``X`` and
the flag ``X + 1``, and ``>[->"zero"<]<`` runs on the flag left at 1.  Each
distinct subtable (``subtree_ids``) is one function entered and left at its
``X``; equal halves skip the branch, and a constant subtable reads its
remaining characters and prints from cell 50 or 51.

A function stays declared only where that is shorter than pasting its body
at each call (:func:`_inlined`).

Size:
    O(T) size and build time, 26n + 311 steps at most; n=10 parity: 1,060
    chars, n=10 random 1847: 6,388 chars (8,558 declaring every function;
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


def pointless(truth_table: str) -> str:
    """Build a Pointless program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    functions: dict[str, str] = {}

    def constant(sub: int, depth: int) -> str:
        key = f"c{sub}d{depth}"
        if key not in functions:
            away = _X + 2 * depth - _OUT - sub
            functions[key] = "," * (n - depth) + "<" * away + "." + ">" * away
        return key

    def build(depth: int, k: int) -> None:
        sub = ids[depth][k]
        functions[str(sub)] = ""  # reserve: children are named first
        zero, one = (child(depth + 1, 2 * k + b) for b in (0, 1))
        if zero == one:
            body = f',>>"{zero}"<<'
        else:
            body = f',=[>-<->>"{one}"<<]>[->"{zero}"<]<'
        functions[str(sub)] = body

    def child(depth: int, k: int) -> str:
        sub = ids[depth][k]
        if sub < 2:
            return constant(sub, depth)
        if str(sub) not in functions:
            build(depth, k)
        return str(sub)

    root = child(0, 0)
    return _setup(n) + _inlined(functions, root)


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
    order: list[str] = []

    def visit(key: str) -> None:
        if key not in size:
            size[key] = 0
            for name in calls[key]:
                visit(name)
            order.append(key)

    visit(root)
    for key in order:
        size[key] = len(functions[key]) + sum(
            size[name] - len(name) - 2 for name in calls[key] if name not in declared
        )
        call = len(key) + 2
        if uses[key] * size[key] > call + 2 + size[key] + uses[key] * call:
            declared.add(key)

    def text(key: str) -> str:
        return _CALL.sub(
            lambda m: m[0] if m[1] in declared else text(m[1]), functions[key]
        )

    main = f'"{root}"' if root in declared else text(root)
    return main + "".join(
        f'"{key}"{{{text(key)}}}' for key in functions if key in declared
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
