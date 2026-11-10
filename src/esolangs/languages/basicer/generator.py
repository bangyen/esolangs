"""BASICER Boolean program generator: a shared decision diagram of menus.

Each node is one ``GOTO a b`` line: the menu reads the input's
choice (``1`` for 0, ``2`` for 1) and jumps to the zero or one child in a
single step.  Equal subtables at a level share one line, so the program is
the quasi-reduced diagram; a node whose children match still reads its
input, as ``GOTO a a``.  The leaves come last: ``PRINT 0`` then ``GOTO 0``,
a missing line that halts, and ``PRINT 1``; the last leaf halts by falling
off.

Size:
    O(T) lines, fewer when subtables repeat; n=4 parity: 108 chars

Decisions:
    Every line is numbered by its position.  Unnumbered lines would save
    the number, but the page never says what ``GOTO`` targets without
    them, so the interpreter's positional reading would carry the program.
"""

from esolangs.generation.decision import decision_layers
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def basicer(truth_table: str) -> str:
    """Build a BASICER program printing ``truth_table[row]`` for the inputs."""
    layers = decision_layers(truth_table).children
    n = len(layers)
    order = [(depth, node) for depth, layer in enumerate(layers) for node in layer]
    used = sorted({child for pair in layers[-1].values() for child in pair})
    line = {key: num for num, key in enumerate(order, 1)}
    leaf = len(order) + 1
    for bit in used:
        line[n, bit] = leaf
        leaf += 2 if bit < used[-1] else 1
    rows = []
    for d, i in order:
        zero, one = layers[d][i]
        rows.append(f"GOTO {line[d + 1, zero]} {line[d + 1, one]}")
    for bit in used:
        rows.append(f"PRINT {bit}")
        if bit < used[-1]:  # the last leaf halts by falling off
            rows.append("GOTO 0")
    return "\n".join(f"{num} {row}" for num, row in enumerate(rows, 1))


def basicer_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return basicer(request.table)
