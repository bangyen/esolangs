"""IEBEL Boolean program generator: a shared decision diagram in chains.

Two setup lines store 49 in register 1 and 48 in register 3.  Each
distinct subtable is one block, emitted once: it reads the next input into
register 2 (``2 2 -3``), then one jump line sends one child elsewhere and the
block falls into the other: ``2 1 Z`` jumps on ``'0'``, ``2 3 O`` on ``'1'``.
``1 3 c`` compares 49 with 48, so it is an unconditional jump.  A leaf prints
register 1 or 3 (``1 3 -2`` / ``3 1 -2``) and halts (``0 0 -1``).

Size:
    O(T) lines: one block per distinct subtable; n=4 parity: 130 chars.
    Constants: 8n+6 chars through n=7, 7n+13 thereafter; n+1/n+2 commands.

Decisions:
    Jumps name line numbers, so a plain tree's jump fields cost T log T
    characters; sharing equal subtables (the reduced diagram) keeps parity
    and repeated tables to one block per level.  Each level greedily lets
    every block fall into one still-unclaimed child, either polarity,
    one-child blocks first: a path cover that drops most ``1 3 c`` lines.
"""

from esolangs.generation.decision import decision_layers
from esolangs.generation.helpers import _validate_truth_table

#: Register 1 holds '1' (49), register 3 holds '0' (48).
_SETUP = ["1 49 0", "3 48 0"]
_GOTO = "1 3 {}"

type _Node = tuple[int, int]  # (level, subtable id)


def iebel(truth_table: str) -> str:
    """Build an IEBEL program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        value = 48 + int(truth_table[0])
        if n <= 7:
            # The read also initializes r0; later equal loads restore that same literal.
            return "\n".join([*[f"0 {value} -3"] * n, "0 1 -2"])
        return "\n".join([*["0 0 -3"] * n, f"1 {value} 0", "1 2 -2"])
    diagram = decision_layers(truth_table)
    by_level = [
        [(depth, node) for node in layer]
        for depth, layer in enumerate(diagram.children)
    ]
    kids = {
        (depth, node): ((depth + 1, zero), (depth + 1, one))
        for depth, layer in enumerate(diagram.children)
        for node, (zero, one) in layer.items()
    }
    leaves = dict.fromkeys(
        child for pair in diagram.children[-1].values() for child in pair
    )
    by_level.append([(n, leaf) for leaf in leaves])
    # Greedy path cover: a block falls into a child no other block falls into.
    fall: dict[_Node, _Node] = {}
    for level in range(n):
        claimed: set[_Node] = set()
        for node in sorted(by_level[level], key=lambda v: len(set(kids[v]))):
            zero, one = kids[node]
            for child in dict.fromkeys((one, zero)):
                if child not in claimed:
                    claimed.add(child)
                    fall[node] = child
                    break
    lines: list[str | tuple[str, _Node]] = list(_SETUP)
    at: dict[_Node, int] = {}
    falls_into = set(fall.values())
    for head in [v for level in by_level for v in level if v not in falls_into]:
        cur: _Node | None = head
        while cur is not None:
            at[cur] = len(lines)
            if cur[0] == n:
                lines.extend(["1 3 -2" if cur[1] else "3 1 -2", "0 0 -1"])
                break
            lines.append("2 2 -3")
            zero, one = kids[cur]
            nxt = fall.get(cur)
            # Singleton-child nodes sort first; distinct nodes cannot share
            # the same equal pair, so each always falls into its sole child.
            if zero != one:
                if nxt == one:
                    lines.append(("2 1 {}", zero))
                elif nxt == zero:
                    lines.append(("2 3 {}", one))
                else:
                    lines.extend([("2 1 {}", zero), (_GOTO, one)])
            cur = nxt
    # A final leaf can halt by falling off the program; no jump targets its halt.
    if lines[-1] == "0 0 -1":
        lines.pop()
    return "\n".join(
        line if isinstance(line, str) else line[0].format(at[line[1]]) for line in lines
    )
