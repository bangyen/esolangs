"""Bleh Boolean program generator: a decision diagram of matching functions.

A node of the reduced diagram is a function whose argument is its input's
character, ``f 2()``; its branches match ``"0"`` and ``"1"`` and call
the child with the next read.  A node whose halves agree, and a constant
above the last input, reads its input as a statement and goes on
(``{2();...}``), so every input is read once and in order; a leaf
prints its bit.  Functions are named by id in letters (``b`` ... ``Z``,
``aa`` ...: the low ids, the most called, take the shortest), and ``io`` is
imported as ``a``; the nullary ``2`` reads through a Boolean validator, so
skipped inputs also reject EOF. For AND:

    ^:std::io=a;2:=3 a::next();3:"0"="0":"1"="1";
    main:=c 2();c:"0"=z1():"1"=b 2();
    z1:={2();a::print"0"};b:"0"=a::print"0":"1"=a::print"1";

Size:
    O(T) text: one function a shared node, one a constant a level;
    n=8 constant zero: 97 chars; n=4 parity: 235 chars, n=10 random 1847: 5,565 chars.
"""

from string import ascii_letters

from esolangs.generation.decision import decision_layers
from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.bleh.descriptor import _TOKEN as _TOKEN
from esolangs.languages.bleh.descriptor import LANGUAGE as LANGUAGE

#: a name or ``::``.
#: a name.

#: ``io``'s import name: the first letter name, which no function takes.
_IO = "a"
#: A legal non-bit word, disjoint from letter and level-qualified function names.
_NEXT = "2"
# Matching before a read returns also protects statement reads at skipped nodes.
_HEADER = f'^:std::io={_IO};{_NEXT}:=3 {_IO}::next();3:"0"="0":"1"="1";'


def _constant(n: int, bit: str) -> str:
    """Force all inputs in one short-call block, then print the fixed bit."""
    # The flat block avoids retaining a continuation per remaining read;
    # its smaller heap pays for its O(n) statement AST within the generic cap.
    reads = f"{_NEXT}();" * n
    return f'{_HEADER}main:={{{reads}{_IO}::print"{bit}"}};'


def bleh(truth_table: str) -> str:
    """Build a Bleh program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        return _constant(n, truth_table[0])
    diagram = decision_layers(truth_table)
    kids = diagram.children

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
    return f"{_HEADER}main:={ref(diagram.root, 0)};" + "".join(defs)


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
    name = "".join(reversed(letters))
    return "mai0" if name == "main" else name
