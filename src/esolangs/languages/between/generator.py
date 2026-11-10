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
    n=4 parity: 193 chars, n=10 random 1847: 4,333 chars.
    Constants use 6n+11 chars, n+2 commands and 16+bl(n+2)+bl(2n) written bits.

Decisions:
    The input is compared as the string ``'0'``/``'1'``; converting it with
    ``c`` first costs a line an input and saves nothing per node.
"""

from string import ascii_letters

from esolangs.generation.decision import DecisionNode, reduced_diagram
from esolangs.generation.helpers import (
    _validate_truth_table,
    short_name,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def _layout(root: int, nodes: list[DecisionNode]) -> list[tuple[int, str]]:
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
    if len(set(truth_table)) == 1:
        return "\n".join(["'a'v.", *["[a]i."] * n, f"|{truth_table[0]}|p."])
    nodes, root = reduced_diagram(truth_table, n)
    order = _layout(root, nodes)
    tested = {node.level for node in nodes[2:]}
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


def between_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return between(request.table)
