"""BASICER Boolean program generator: a shared decision diagram of menus.

Each node is one ``GOTO a b`` line: the menu reads the input's
choice (``1`` for 0, ``2`` for 1) and jumps to the zero or one child in a
single step.  Equal subtables at a level share one line, so the program is
the quasi-reduced diagram; a node whose children match still reads its
input, as ``GOTO a a``.  The leaves come last: ``PRINT 0`` then ``GOTO 0``,
a missing line that halts, and ``PRINT 1``, which halts by falling off.

Size:
    O(T) lines, fewer when subtables repeat; n=4 parity: 108 chars

Decisions:
    Every line is numbered by its position.  Unnumbered lines would save
    the number, but the page never says what ``GOTO`` targets without
    them, so the interpreter's positional reading would carry the program.
"""

from esolangs.generation.helpers import subtree_ids
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language


def basicer(truth_table: str) -> str:
    """Build a BASICER program printing ``truth_table[row]`` for the inputs."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    # Each level's ids, in first-seen order, mapped to their first subtable.
    first: list[dict[int, int]] = [{} for _ in range(n)]
    for d in range(n):
        for k, i in enumerate(ids[d]):
            first[d].setdefault(i, k)
    order = [(d, i) for d in range(n) for i in first[d]]
    used = sorted(set(ids[n]))
    line = {key: num for num, key in enumerate(order, 1)}
    leaf = len(order) + 1
    for bit in used:
        line[n, bit] = leaf
        leaf += 2 if bit == 0 else 1
    rows = []
    for d, i in order:
        k = first[d][i]
        zero, one = ids[d + 1][2 * k], ids[d + 1][2 * k + 1]
        rows.append(f"GOTO {line[d + 1, zero]} {line[d + 1, one]}")
    for bit in used:
        rows += ["PRINT 0", "GOTO 0"] if bit == 0 else ["PRINT 1"]
    return "\n".join(f"{num} {row}" for num, row in enumerate(rows, 1))


LANGUAGE = Language(
    "BASICER",
    "basicer",
    category="program_based",
    boolean=basicer,
    contract=BooleanContract(alphabet=("1", "2")),
    example=Example(expected="0\n"),
    no_wrap="each line is one instruction and a break splits it",
)
