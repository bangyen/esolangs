"""Object disoriented Boolean program generator: a tree of conditional calls.

``main`` first prints ``0011000``, the answer byte's fixed bits; output is
buffered until the 8th, so nothing is printed before the inputs are read.
An input byte is ``0011000x``, MSB first: a node drops seven bits and keeps
the eighth in ``t``. Class ``B`` reads that bit, writes its negation through
the caller's ``a`` place, and returns the bit; each node calls ``cflB.at``.
``f t X`` runs ``X`` only on a 1. ``N`` (``fpz cbs``) is 1 until the 1 bit
calls it and its ``s`` becomes ``z``, so ``fa X0`` runs only on a 0.
Each branch is an object ``n ... rz zz``, so its ``t``
and ``a`` are its own.  A constant subtable drops the rest and prints the
last bit (``lI.``, the input's own 1, or ``z``).  A branch written as an
object twice or more is a class ``dS. ... rzzz``, written once and used as
``lS.``.

Size:
    T-1 nodes at most: size and build time O(T); n=8 parity: 439 chars,
    n=10 majority: 999 chars, n=10 and: 671 chars.
    Constants: 8n+28 chars, 16n+28 commands, 48+2bl(n) written bits.

Decisions:
    Reader B replaces an 18-character read/negation prefix with a seven-char
    call. B is reserved from shared names. A final space keeps compact
    class code from being mistaken for a path by the API.
"""

from collections.abc import Callable, Iterator
from itertools import count, product
from string import ascii_letters, digits

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

#: ``I`` is the bit 1; ``N`` is 1 until a 1 bit calls it.
_HEADER = "dI.fpzrzzzdN.fpzcbsrzzzdB.iiiiiiicitclN.pftprtzzdmain.ozozolI.olI.ozozoz"

#: Class names for shared branches; ``I``, ``N``, ``B`` and ``main`` are taken.
_NAME_CHARS = "".join(c for c in ascii_letters + digits if c not in "INB")


def _names() -> Iterator[str]:
    for size in count(1):
        for chars in product(_NAME_CHARS, repeat=size):
            if (name := "".join(chars)) != "main":
                yield name


def object_disoriented(truth_table: str) -> str:
    """Build an Object disoriented program printing ``truth_table[row]``."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        # The third MSB-first bit of either ASCII input digit is one.
        reads = "iicit" + "i" * (8 * n - 3)
        return (
            "dmain."
            + reads
            + "ozozototozozoz"
            + ("ot" if truth_table[0] == "1" else "oz")
            + "rzzz"
        )
    ids = subtree_ids(truth_table)
    return _program(ids, n, _shared_names(ids, n))


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
    return "cflB.atft" + obj(depth + 1, 2 * k + 1) + "fa" + obj(depth + 1, 2 * k)


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
    out.append("rzzz")
    for (depth, node), name in names.items():
        out.append(f"d{name}." + _body(ids, n, depth, first[depth][node], obj) + "rzzz")
    return "".join(out) + " "


def _shared_names(ids: list[list[int]], n: int) -> dict[tuple[int, int], str]:
    """Name each branch written as an object at least twice, when shorter.

    Top-down, so a use counts once per text the parent's body is written in;
    a branch's own length is taken unshared (an estimate).  ``m`` uses of a
    ``c``-character body save ``m (c + 5) - (c + |name| + 6) - m (|name| + 2)``.
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
            plain[depth][node] = 21 + plain[depth + 1][one] + plain[depth + 1][zero]
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
            if as_obj >= 2 and as_obj * (c + 5) > c + size + 6 + as_obj * (size + 2):
                name = names[depth, node] = candidate
                candidate = next(fresh)
            texts = inline + (1 if name else as_obj)
            if node < 2:
                continue
            zero, one = ids[depth + 1][2 * k], ids[depth + 1][2 * k + 1]
            below.setdefault(zero, [0, 0])[0] += texts
            below.setdefault(one, [0, 0])[0] += texts
        uses = below
    return names


LANGUAGE = Language(
    "Object disoriented",
    RuntimeSpec(
        "object_disoriented",
        category="other",
        empty_program="Object disoriented program defines no 'main' class",
    ),
    boolean=object_disoriented,
    contract=BooleanContract(
        input_shape="char_stream",
        note="Object disoriented reads input bits most significant first, so "
        "a program keeps each input byte's eighth bit and drops the seven before it",
    ),
    # Whitespace is ignored everywhere, class names included.
    wrap=wrap_chars,
)
