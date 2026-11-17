"""Flipscript Boolean program generator: a shared decision diagram of computed jumps.

Each distinct subtable (the quasi-reduced diagram, ``subtree_ids``) is one
node of two lines, ``num X = input`` then ``jump X*A+B``: the input bit
picks the jump length, landing on the zero or one child's first line.
Nodes are laid out root first, a level at a time, so every child lies below
its parent and every jump runs down.  A constant answer is a run of
``num X = input`` lines ending in its ``output``: a constant child lands as
many lines into the run as inputs remain, so every input is read once.

Size:
    two lines per diagram node, whose O(T/n) count each carry O(n) digits,
    and at most n reads per answer run: O(T) characters; n=4 parity:
    218 chars, n=10 random 1847: 6,547 chars

Decisions:
    The screening probe's tree (zero child down, one child up through a
    flip) cannot share a subtree: its two entry directions fix one parent
    side.  Downward computed jumps let any parent reach a shared node.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def _jump(zero: int, one: int) -> str:
    """Return ``jump`` landing ``zero`` lines on for X=0 and ``one`` for X=1."""
    if one > zero:
        return f"jump X*{one - zero}+{zero}"
    return f"jump 0-{zero - one}*X+{zero}"


def flipscript(truth_table: str) -> str:
    """Build a Flipscript program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    # Diagram nodes in layout order: their depth and children; line 0 is start.
    nodes: list[tuple[int, int, int]] = []
    entry: dict[int, int] = {}
    # Reads each constant answer's run must still supply, at most.
    owed = {key: n for key in ids[0] if key < 2}
    for depth in range(n):
        below = ids[depth + 1]
        for block, key in enumerate(ids[depth]):
            if key >= 2 and key not in entry:
                entry[key] = 1 + 2 * len(nodes)
                zero, one = below[2 * block], below[2 * block + 1]
                nodes.append((depth, zero, one))
                for child in (zero, one):
                    if child < 2:
                        owed[child] = max(owed.get(child, 0), n - depth - 1)
    run = {}  # constant -> its run's first line
    line = 1 + 2 * len(nodes)
    for key in sorted(owed):
        run[key] = line
        line += owed[key] + 1 + (key == 0 and 1 in owed)

    def land(child: int, depth: int) -> int:
        if child >= 2:
            return entry[child]
        return run[child] + owed[child] - (n - depth - 1)

    lines = ["start(0)"]
    for ind, (depth, zero, one) in enumerate(nodes):
        at = 2 + 2 * ind
        jump = _jump(land(zero, depth) - at, land(one, depth) - at)
        lines += ["num X = input", jump]
    for key in sorted(owed):
        lines += ["num X = input"] * owed[key] + [f'output("{key}")']
        if key == 0 and 1 in owed:
            lines.append("stop")
    return "\n".join(lines)


def flipscript_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return flipscript(request.table)
