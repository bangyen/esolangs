"""Replay the algebraic first-step proof against a shortest-path oracle."""

from collections import deque
from collections.abc import Callable
from functools import cache
from itertools import product

from esolangs.languages.malbolge.generator.isa import _ALL2, _WORDS

BAND = "ci"
COST = 0.2


def first_step(
    start: int,
    target: int,
    ceiling: int,
    read: Callable[[int], int],
) -> str | None:
    """Evaluate the fixed-depth term with invalid moves replaced by self-loops."""

    @cache
    def moves(position: int) -> tuple[int, int]:
        walk = position + 1
        jump = (read(position) + 1) % _WORDS
        return (
            walk if walk < ceiling else position,
            jump if 0 < jump < ceiling else position,
        )

    @cache
    def distance(position: int, depth: int) -> int:
        if position == target:
            return 0
        if depth == 0:
            return ceiling
        walk, jump = moves(position)
        return min(
            ceiling, 1 + distance(walk, depth - 1), 1 + distance(jump, depth - 1)
        )

    if start == target:
        return ""
    walk, jump = moves(start)
    walk_cost = distance(walk, ceiling - 2)
    jump_cost = distance(jump, ceiling - 2)
    if min(walk_cost, jump_cost) == ceiling:
        return None
    return "o" if walk_cost <= jump_cost else "j"


def _oracle(
    start: int, target: int, landings: tuple[int, ...]
) -> tuple[str | None, set[int]]:
    """Return the BFS first step and every position reachable from start."""
    queue = deque([start])
    first = {start: ""}
    while queue:
        position = queue.popleft()
        for move, next_position in (("o", position + 1), ("j", landings[position])):
            if 0 < next_position < len(landings) and next_position not in first:
                first[next_position] = first[position] or move
                queue.append(next_position)
    return first.get(target), set(first)


def main() -> int:
    """Check all four-cell graphs, including ties, cycles, and unreachable cells."""
    ceiling = 4
    # Landing 0 models an absent word. Landing at the ceiling is invalid too.
    for landings in product(range(ceiling + 1), repeat=ceiling):
        for start, target in product(range(ceiling), repeat=2):
            expected, reachable = _oracle(start, target, landings)

            def read(
                position: int,
                reachable: set[int] = reachable,
                landings: tuple[int, ...] = landings,
            ) -> int:
                assert position in reachable
                return landings[position] - 1 if landings[position] else _ALL2

            assert first_step(start, target, ceiling, read) == expected

    print("10,000 first-step and derived-read checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
