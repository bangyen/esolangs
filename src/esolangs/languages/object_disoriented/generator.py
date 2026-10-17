"""Object disoriented Boolean program generator: a tree of conditional calls.

``main`` first prints ``0011000``, the answer byte's fixed bits; output is
buffered until the 8th, so nothing is printed before the inputs are read.
An input byte is ``0011000x``, MSB first: a node drops seven bits and keeps
the eighth in ``t`` (``iiiiiiicit``).  ``f t X`` runs ``X`` only on a 1, and
``N`` (``fpz cbs``) acts as a 1 until a 1 bit calls it and ``s`` becomes
``z``, so ``clN.afta`` leaves the negation in ``a`` and ``fan X0`` runs
``X0`` only on a 0.  Each branch is an object ``n ... rz zz``, so its ``t``
and ``a`` are its own.  A node whose halves agree drops its bit untested; a
constant subtable drops the rest and prints the last bit (``lI.``, the
input's own 1, or ``z``).  A branch written as an object twice or more is
a class ``dS. ... rzzz``, written once and used as ``lS.``.

Size:
    T-1 nodes at most: size and build time O(T); n=8 parity: 640 chars,
    n=10 majority: 1,417 chars, n=10 and: 789 chars.

Decisions:
    Shared branches, against the plain tree (8 seeded tables each): dense
    -58.1% at n=8, -68.1% at n=10; parity 9,748 -> 640 chars at n=8.
"""

from collections.abc import Callable, Iterator
from itertools import count, product
from string import ascii_letters, digits

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: ``I`` is the bit 1; ``N`` is 1 until a 1 bit calls it.
_HEADER = "dI.fpzrzzz dN.fpzcbsrzzz dmain.ozozolI.olI.ozozoz "

#: Class names for shared branches; ``I``, ``N`` and ``main`` are taken.
_NAME_CHARS = "".join(c for c in ascii_letters + digits if c not in "IN")


def _names() -> Iterator[str]:
    for size in count(1):
        for chars in product(_NAME_CHARS, repeat=size):
            if (name := "".join(chars)) != "main":
                yield name


def object_disoriented(truth_table: str) -> str:
    """Build an Object disoriented program printing ``truth_table[row]``.

    The shared build is kept only when shorter, so no table grows.
    """
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    plain = _program(ids, n, {})
    shared = _program(ids, n, _shared_names(ids, n))
    return min(plain, shared, key=len)


def _body(
    ids: list[list[int]],
    n: int,
    depth: int,
    k: int,
    obj: Callable[[int, int], str],
) -> str:
    """One node's code; ``obj(depth, k)`` writes a branch object."""
    if ids[depth][k] < 2:
        return "i" * 8 * (n - depth) + ("olI." if ids[depth][k] else "oz")
    zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
    if zero == one:
        return "iiiiiiii" + _body(ids, n, depth + 1, 2 * k, obj)
    return (
        " iiiiiiicitclN.afta ft"
        + obj(depth + 1, 2 * k + 1)
        + " fa"
        + obj(depth + 1, 2 * k)
    )


def _program(ids: list[list[int]], n: int, names: dict[tuple[int, int], str]) -> str:
    """The tree, each branch in ``names`` a class written once and used by name."""
    first: list[dict[int, int]] = [{} for _ in ids]
    for depth, level in enumerate(ids):
        for k, node in enumerate(level):
            first[depth].setdefault(node, k)
    out = [_HEADER]

    def obj(depth: int, k: int) -> str:
        key = (depth, ids[depth][k])
        if key in names:
            return f"l{names[key]}."
        return "n" + _body(ids, n, depth, k, obj) + "rzzz"

    out.append(_body(ids, n, 0, 0, obj))
    out.append(" rzzz")
    for (depth, node), name in names.items():
        out.append(
            f" d{name}." + _body(ids, n, depth, first[depth][node], obj) + "rzzz"
        )
    return "".join(out)


def _shared_names(ids: list[list[int]], n: int) -> dict[tuple[int, int], str]:
    """Name each branch written as an object at least twice, when shorter.

    Top-down, so a use counts once per text the parent's body is written in;
    a branch's own length is taken unshared (an estimate: the plain build
    competes).  ``m`` uses of a ``c``-character body save
    ``m (c + 5) - (c + |name| + 7) - m (|name| + 2)``.
    """
    plain = [dict[int, int]() for _ in ids]
    for depth in range(n, -1, -1):
        for k, node in enumerate(ids[depth]):
            if node in plain[depth]:
                continue
            if node < 2:
                plain[depth][node] = 8 * (n - depth) + (4 if node else 2)
                continue
            zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
            if zero == one:
                plain[depth][node] = 8 + plain[depth + 1][zero]
            else:
                plain[depth][node] = 35 + plain[depth + 1][one] + plain[depth + 1][zero]
    names: dict[tuple[int, int], str] = {}
    fresh = _names()
    candidate = next(fresh)
    # (as an object, inline) texts of each node at the level being decided.
    uses = {ids[0][0]: [0, 1]}
    for depth in range(n + 1):
        below: dict[int, list[int]] = {}
        seen: set[int] = set()
        for k, node in enumerate(ids[depth]):
            if node in seen or node not in uses:
                continue
            seen.add(node)
            as_obj, inline = uses[node]
            c = plain[depth][node]
            name = None
            size = len(candidate)
            if as_obj >= 2 and as_obj * (c + 5) > c + size + 7 + as_obj * (size + 2):
                name = names[depth, node] = candidate
                candidate = next(fresh)
            texts = inline + (1 if name else as_obj)
            if node < 2:
                continue
            zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
            if zero == one:
                below.setdefault(zero, [0, 0])[1] += texts
            else:
                below.setdefault(zero, [0, 0])[0] += texts
                below.setdefault(one, [0, 0])[0] += texts
        uses = below
    return names


LANGUAGE = Language(
    "Object disoriented",
    "object_disoriented",
    category="other",
    boolean=object_disoriented,
    contract=BooleanContract(
        input_shape="char_stream",
        note="Object disoriented reads input bits most significant first, so "
        "a program keeps each input byte's eighth bit and drops the seven before it",
    ),
    # Whitespace is ignored everywhere, class names included.
    wrap=wrap_chars,
    empty_program="Object disoriented program defines no 'main' class",
)
