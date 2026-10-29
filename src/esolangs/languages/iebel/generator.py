"""IEBEL Boolean program generator: a shared decision diagram.

Two setup lines store 49 in register 1 and 48 in register 3.  Each
distinct subtable is one block, emitted once and reached by jumps: it
reads the next input into register 2 (``2 2 -3``), then ``2 1 Z`` falls
through on ``'1'`` and jumps to the zero block otherwise.  ``1 3 c``
compares 49 with 48, so it is an unconditional jump.  A leaf prints
register 1 or 3 (``1 3 -2`` / ``3 1 -2``) and halts (``0 0 -1``).

Size:
    O(T) lines: one block per distinct subtable; n=4 parity: 177 chars

Decisions:
    Jumps name line numbers, so a plain tree's jump fields cost T log T
    characters; sharing equal subtables (the reduced diagram) keeps parity
    and repeated tables to one block per level.
"""

from esolangs.generation.helpers import subtree_ids
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Register 1 holds '1' (49), register 3 holds '0' (48).
_SETUP = ["1 49 0", "3 48 0"]
_GOTO = "1 3 {}"


def iebel(truth_table: str) -> str:
    """Build an IEBEL program printing ``truth_table[row]`` for the inputs."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    lines: list[str | tuple[str, tuple[int, int]]] = list(_SETUP)
    at: dict[tuple[int, int], int] = {}
    todo: list[tuple[int, int]] = [(0, 0)]

    def emit(level: int, k: int) -> None:
        # Lays a block out, then falls into its one-child while that is new.
        while (level, ids[level][k]) not in at:
            at[level, ids[level][k]] = len(lines)
            if level == n:
                lines.extend(["1 3 -2" if ids[n][k] else "3 1 -2", "0 0 -1"])
                return
            lines.append("2 2 -3")
            zero, one = (level + 1, 2 * k), (level + 1, 2 * k + 1)
            if ids[zero[0]][zero[1]] != ids[one[0]][one[1]]:
                lines.append(("2 1 {}", (zero[0], ids[zero[0]][zero[1]])))
                todo.append(zero)
            level, k = one
        lines.append((_GOTO, (level, ids[level][k])))

    while todo:
        emit(*todo.pop())
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
