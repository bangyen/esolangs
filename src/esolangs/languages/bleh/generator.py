"""Bleh Boolean program generator: a decision diagram of matching functions.

A node of the reduced diagram is a function ``fN`` whose argument is its
input's character, ``fN io::next()``; its branches match ``"0"`` and ``"1"``
and call the child with the next read.  A node whose halves agree, and a
constant above the last input, reads its input as a statement and goes on
(``{io::next();...}``), so every input is read once and in order; a leaf
prints its bit.  For AND:

    ^:std::io;main:=f3 io::next();f3:"0"=z1():"1"=f2 io::next();
    z1:={io::next();io::print"0"};f2:"0"=io::print"0":"1"=io::print"1";

Size:
    O(T) text: one function a shared node, one a constant a level;
    n=4 parity: 299 chars, n=10 random 1847: 9,557 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: a name or ``::``.
#: a name.
_TOKEN = r'"[^"]*"|::|\w+|[\s\S]'


def bleh(truth_table: str) -> str:
    """Build a Bleh program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    # Each level's nodes with their halves, in first-occurrence order.
    kids: list[dict[int, tuple[int, int]]] = []
    for level in range(n):
        below = ids[level + 1]
        kids.append({})
        for k, node in enumerate(ids[level]):
            kids[level].setdefault(node, (below[2 * k], below[2 * k + 1]))

    def ref(node: int, level: int) -> str:
        """Return the expression that reads on from ``level`` at ``node``."""
        if level == n:
            return f'io::print"{node}"'
        lo, hi = kids[level][node]
        return f"{_name(node, level)}{'()' if lo == hi else ' io::next()'}"

    defs = []
    for level in range(n):
        for node, (lo, hi) in kids[level].items():
            name = _name(node, level)
            if lo == hi:
                defs.append(f"{name}:={{io::next();{ref(lo, level + 1)}}};")
            else:
                zero, one = ref(lo, level + 1), ref(hi, level + 1)
                defs.append(f'{name}:"0"={zero}:"1"={one};')
    return f"^:std::io;main:={ref(ids[0][0], 0)};" + "".join(defs)


def _name(node: int, level: int) -> str:
    """Return a node's function: a constant's name carries its level."""
    return f"{'zo'[node]}{level}" if node < 2 else f"f{node}"


LANGUAGE = Language(
    "Bleh",
    "bleh",
    category="other",
    boolean=bleh,
    contract=BooleanContract(input_shape="char_stream"),
    wrap=TokenWrapper(_TOKEN),
    eof="an exhausted io::next() is the empty bitstring",
    underfed_raises=True,
    empty_program="a Bleh program needs a main function",
)
