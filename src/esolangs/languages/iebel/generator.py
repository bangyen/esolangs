"""IEBEL Boolean program generator: a shared decision diagram in chains.

Two setup lines store 49 in register 1 and 48 in register 3.  Each
distinct subtable is one block, emitted once: it reads the next input into
register 2 (``2 2 -3``), then one jump line sends one child elsewhere and the
block falls into the other: ``2 1 Z`` jumps on ``'0'``, ``2 3 O`` on ``'1'``.
``1 3 c`` compares 49 with 48, so it is an unconditional jump.  A leaf prints
register 1 or 3 (``1 3 -2`` / ``3 1 -2``) and halts (``0 0 -1``).

Size:
    O(T) lines: one block per distinct subtable; n=4 parity: 137 chars

Decisions:
    Jumps name line numbers, so a plain tree's jump fields cost T log T
    characters; sharing equal subtables (the reduced diagram) keeps parity
    and repeated tables to one block per level.  Each level greedily lets
    every block fall into one still-unclaimed child, either polarity,
    one-child blocks first: a path cover that drops most ``1 3 c`` lines.
"""

from esolangs.generation.helpers import subtree_ids
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Register 1 holds '1' (49), register 3 holds '0' (48).
_SETUP = ["1 49 0", "3 48 0"]
_GOTO = "1 3 {}"

type _Node = tuple[int, int]  # (level, subtable id)


def iebel(truth_table: str) -> str:
    """Build an IEBEL program printing ``truth_table[row]`` for the inputs."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    root: _Node = (0, ids[0][0])
    rep: dict[_Node, int] = {root: 0}  # reachable node -> one position of it
    kids: dict[_Node, tuple[_Node, _Node]] = {}
    by_level: list[list[_Node]] = [[root]]
    for level in range(n):
        below: list[_Node] = []
        for parent in by_level[level]:
            k = rep[parent]
            pair = (
                (level + 1, ids[level + 1][2 * k]),
                (level + 1, ids[level + 1][2 * k + 1]),
            )
            kids[parent] = pair
            for j, child in enumerate(pair):
                if child not in rep:
                    rep[child] = 2 * k + j
                    below.append(child)
        by_level.append(below)
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
            if zero == one:
                if nxt is None:
                    lines.append((_GOTO, one))
            elif nxt == one:
                lines.append(("2 1 {}", zero))
            elif nxt == zero:
                lines.append(("2 3 {}", one))
            else:
                lines.extend([("2 1 {}", zero), (_GOTO, one)])
            cur = nxt
    return "\n".join(
        line if isinstance(line, str) else line[0].format(at[line[1]]) for line in lines
    )


LANGUAGE = Language(
    "IEBEL",
    "iebel",
    category="register_based",
    boolean=iebel,
    contract=BooleanContract(input_shape="char_stream"),
    no_wrap="each line is one instruction; a break splits its fields",
)
