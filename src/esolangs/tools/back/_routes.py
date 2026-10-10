"""Conservative admission of one forward Back bend."""

from collections.abc import Callable

_Node = tuple[int, int]
_Grid = dict[tuple[int, int], str]


def _back_walk(grid: _Grid, height: int, width: int) -> int | None:
    """Bound both outcomes of every skip; reject a reachable beam cycle."""
    start = (0, 1, 0, 1)
    costs: dict[tuple[int, int, int, int], int] = {}
    active: set[tuple[int, int, int, int]] = set()
    stack = [(start, False)]

    def successors(state: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
        row, col, dy, dx = state
        char = grid.get((row, col), " ")
        if char == "*":
            return []
        if char == "\\":
            dy, dx = dx, dy
        elif char == "/":
            dy, dx = -dx, -dy
        steps = (1, 2) if char == "+" else (1,)
        return [
            ((row + step * dy) % height, (col + step * dx) % width, dy, dx)
            for step in steps
        ]

    while stack:
        state, returning = stack.pop()
        if state in costs:
            continue
        children = successors(state)
        if returning:
            costs[state] = 1 + max((costs[child] for child in children), default=0)
            active.remove(state)
        else:
            if state in active:
                return None
            active.add(state)
            stack.append((state, True))
            stack.extend((child, False) for child in children if child not in costs)
    return costs[start]


def _back_bend(
    grid: _Grid,
    positions: dict[_Node, tuple[int, int]],
    shared: set[_Node],
    ids: list[list[int]],
    draw: Callable[[set[_Node]], tuple[_Grid, dict[_Node, tuple[int, int]]]],
) -> _Grid | None:
    """Route the first nonadjacent repeat through column one, if unobstructed."""
    route = None
    for level in range(len(ids) - 1):
        order = [node for node in positions if node[0] == level]
        owners: dict[int, list[_Node]] = {}
        for index in range(len(order) - 1, -1, -1):
            node = order[index]
            if node not in shared:
                matching = owners.get(ids[level + 1][2 * node[1] + 1], [])
                if matching and matching[-1] != order[index + 1]:
                    route = node, matching[-1]
            owners.setdefault(ids[level + 1][2 * node[1]], []).append(node)
        if route is not None:
            break
    if route is None:
        return None
    node, owner = route
    candidate, where = draw(shared | {node})
    if node not in where or owner not in where:
        return None
    sy, col = where[node]
    ty, _ = where[owner]
    sy += 1
    ty -= 1
    if sy >= ty:
        return None
    path = [(sy, c) for c in range(1, col + 1)]
    path += [(r, 1) for r in range(sy + 1, ty + 1)]
    path += [(ty, c) for c in range(2, col + 1)]
    if any(cell in candidate for cell in path):
        return None
    turns = {(sy, col): "/", (sy, 1): "/", (ty, 1): "\\", (ty, col): "\\"}

    def falls(
        cells: _Grid, nodes: dict[_Node, tuple[int, int]]
    ) -> dict[_Node, _Node | None]:
        height = max(r for r, _ in cells) + 1
        by_cell = {cell: key for key, cell in nodes.items()}
        targets = {}
        for key in shared:
            if key not in nodes:
                continue
            row, column = nodes[key]
            row = (row + 1) % height
            while (row, column) not in cells:
                row = (row + 1) % height
            targets[key] = by_cell.get((row, column))
        return targets

    candidate.update(turns)
    before = falls(grid, positions)
    if any(target is None for target in before.values()):
        return None
    after = falls(candidate, where)
    if any(after.get(key) != target for key, target in before.items() if key in where):
        return None
    return candidate
