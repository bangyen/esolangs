"""Bleh Boolean program generator: a decision diagram of matching functions.

A node of the reduced diagram is a function whose argument is its input's
character, ``f 2()``; its branches match ``"0"`` and ``"1"`` and call
the child with the next read.  A node whose halves agree, and a constant
above the last input, reads its input as a statement and goes on
(``{2();...}``), so every input is read once and in order; a leaf
prints its bit.  Functions are named by id in letters (``b`` ... ``Z``,
``aa`` ...: the low ids, the most called, take the shortest), and ``io`` is
imported as ``a``; the nullary ``2`` aliases ``a::next``. For AND:

    ^:std::io=a;2:=a::next();main:=c 2();c:"0"=z1():"1"=b 2();
    z1:={2();a::print"0"};b:"0"=a::print"0":"1"=a::print"1";

Size:
    O(T) text: one function a shared node, one a constant a level;
    n=8 constant zero: 77 chars; n=4 parity: 215 chars, n=10 random 1847: 5,545 chars.
"""

from itertools import pairwise
from string import ascii_letters

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.bleh.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: a name or ``::``.
#: a name.
_TOKEN = r'"[^"]*"|::|\w+|[\s\S]'

#: ``io``'s import name: the first letter name, which no function takes.
_IO = "a"
#: A legal non-bit word, disjoint from letter and level-qualified function names.
_NEXT = "2"
_HEADER = f"^:std::io={_IO};{_NEXT}:={_IO}::next();"


def _constant(n: int, bit: str) -> str:
    """Force all inputs in one short-call block, then print the fixed bit."""
    # The short-call AST costs 16n+256+max(1,bl(n-1))+bl(n) written bits,
    # below the generic envelope; full io::next calls previously required chunks.
    reads = f"{_NEXT}();" * n
    return f'{_HEADER}main:={{{reads}{_IO}::print"{bit}"}};'


def bleh(truth_table: str) -> str:
    """Build a Bleh program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return _constant(n, truth_table[0])
    ids = subtree_ids(truth_table)
    # Each level's nodes with their halves, in first-occurrence order.
    kids = [
        {node: (below[2 * k], below[2 * k + 1]) for k, node in enumerate(above)}
        for above, below in pairwise(ids)
    ]

    def ref(node: int, level: int) -> str:
        """Return the expression that reads on from ``level`` at ``node``."""
        if level == n:
            return f'{_IO}::print"{node}"'
        lo, hi = kids[level][node]
        return f"{_name(node, level)}{'()' if lo == hi else f' {_NEXT}()'}"

    defs = []
    for level in range(n):
        for node, (lo, hi) in kids[level].items():
            name = _name(node, level)
            if lo == hi:
                defs.append(f"{name}:={{{_NEXT}();{ref(lo, level + 1)}}};")
            else:
                zero, one = ref(lo, level + 1), ref(hi, level + 1)
                defs.append(f'{name}:"0"={zero}:"1"={one};')
    return f"{_HEADER}main:={ref(ids[0][0], 0)};" + "".join(defs)


def _name(node: int, level: int) -> str:
    """Return a node's function: a constant's name carries its level.

    A shared node is its id in bijective base 52 over the letters (id 2 is
    ``b``, 52 ``Z``, 53 ``aa``); ids ascend from the leaves, which are
    called most.
    """
    if node < 2:
        return f"{'zo'[node]}{level}"
    index, letters = node, []
    while index:
        index, digit = divmod(index - 1, len(ascii_letters))
        letters.append(ascii_letters[digit])
    return "".join(reversed(letters))


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
    proof_workspace=(workspace, False, (3, 4, 5, 6, 7)),
    proof_execution=(execution, True, (1, 2, 3, 6)),
)
