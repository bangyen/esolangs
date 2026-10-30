"""Between Boolean program generator: a shared decision diagram of gotos.

Each input is read into a variable of its own, in order; an input the table
ignores is read into one shared scratch variable.  The diagram is the table's
reduced decision diagram, so a constant span is a leaf and a test whose two
sides agree is skipped.  A node is ``|zero|f([x]='0')`` and falls through to
its one-child; when that child is already placed the fall-through takes the
zero-child under ``f([x]='1')``, and only a node with both placed spends a
second line, ``|one|f.``.  A leaf is ``|b|p.`` then ``.x.``, and a diagram
node and a leaf are each placed once however many branches reach them.

Size:
    O(T) lines, one per diagram node plus a goto when both children were
    placed before, each line's address O(log T) digits;
    n=4 parity: 193 chars, n=10 random 1847: 4,333 chars

Decisions:
    The input is compared as the string ``'0'``/``'1'``; converting it with
    ``c`` first costs a line an input and saves nothing per node.
"""

from string import ascii_letters

from esolangs.generation.helpers import (
    _validate_truth_table,
    short_name,
    subtree_ids,
)
from esolangs.registry._language import Language


def _diagram(ids: list[list[int]]) -> tuple[int, dict[int, tuple[int, int, int]]]:
    """Return the root and ``{node: (depth, zero, one)}`` of the reduced diagram.

    Leaves are the ids 0 and 1 with depth ``len(ids) - 1``.  A node whose
    children coincide is replaced by that child, so every test matters.
    """

    def reduce(depth: int, k: int) -> tuple[int, int]:
        while (
            depth < len(ids) - 1 and ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]
        ):
            depth, k = depth + 1, 2 * k
        return depth, k

    nodes: dict[int, tuple[int, int, int]] = {}
    start = reduce(0, 0)
    todo = [start]
    while todo:
        depth, k = todo.pop()
        node = ids[depth][k]
        if node in nodes:
            continue
        if node < 2:
            nodes[node] = (depth, node, node)
            continue
        below = [reduce(depth + 1, 2 * k), reduce(depth + 1, 2 * k + 1)]
        (d0, k0), (d1, k1) = below
        nodes[node] = (depth, ids[d0][k0], ids[d1][k1])
        todo.extend(below)
    return ids[start[0]][start[1]], nodes


def _layout(root: int, nodes: dict[int, tuple[int, int, int]]) -> list[tuple[int, str]]:
    """Return the placement order as ``(node, mode)``, mode ``o``, ``z`` or ``b``.

    The mode names the child that follows the node (``b``: neither does).
    """
    placed: set[int] = set()
    order: list[tuple[int, str]] = []
    todo = [root]
    while todo:
        node = todo.pop()
        while node not in placed:
            placed.add(node)
            _, zero, one = nodes[node]
            if node < 2:
                order.append((node, "b"))
            elif one not in placed:
                order.append((node, "o"))
                todo.append(zero)
                node = one
                continue
            elif zero not in placed:
                order.append((node, "z"))
                node = zero
                continue
            else:
                order.append((node, "b"))
            break
    return order


def between(truth_table: str) -> str:
    """Build a Between program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    root, nodes = _diagram(ids)
    order = _layout(root, nodes)
    tested = {depth for node, (depth, _, _) in nodes.items() if node > 1}
    names = [short_name(i, ascii_letters) for i in range(n + 1)]
    scratch = names[n]
    header = []
    seen_scratch = False
    for depth in range(n):
        name = names[depth] if depth in tested else scratch
        if name != scratch or not seen_scratch:
            header.append(f"'{name}'v.")
        seen_scratch |= name == scratch
        header.append(f"[{name}]i.")
    start: dict[int, int] = {}
    address = len(header)
    for node, mode in order:
        start[node] = address
        address += 2 if node < 2 or mode == "b" else 1
    lines = header
    for node, mode in order:
        depth, zero, one = nodes[node]
        if node < 2:
            lines += [f"|{node}|p.", ".x."]
            continue
        var = names[depth]
        if mode == "z":
            lines.append(f"|{start[one]}|f([{var}]='1')")
            continue
        lines.append(f"|{start[zero]}|f([{var}]='0')")
        if mode == "b":
            lines.append(f"|{start[one]}|f.")
    return "\n".join(lines)


LANGUAGE = Language(
    "Between",
    "between",
    category="register_based",
    boolean=between,
    no_wrap="each line is one instruction and a break splits it",
)
