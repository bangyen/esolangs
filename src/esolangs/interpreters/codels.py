"""Codel traversal shared by raster interpreters: blocks, exits and white slides."""

from __future__ import annotations

from collections.abc import Callable, Sequence

Pixel = tuple[int, int, int]
Point = tuple[int, int]

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# right, down, left, up
DIRECTIONS: tuple[Point, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


def find_block(
    rows: Sequence[Sequence[Pixel]],
    start: Point,
    colour: Callable[[Pixel], Pixel],
) -> set[Point]:
    """Return the four-connected ``colour`` block containing ``start``."""
    width, height = len(rows[0]), len(rows)
    wanted = colour(rows[start[1]][start[0]])
    found = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for dx, dy in DIRECTIONS:
            point = x + dx, y + dy
            px, py = point
            if (
                0 <= px < width
                and 0 <= py < height
                and point not in found
                and colour(rows[py][px]) == wanted
            ):
                found.add(point)
                pending.append(point)
    return found


def leave(block: set[Point], dp: int, cc: int) -> Point:
    """Choose the block exit codel for the direction pointer and chooser."""
    dx, dy = DIRECTIONS[dp]
    edge = max(x * dx + y * dy for x, y in block)
    candidates = [point for point in block if point[0] * dx + point[1] * dy == edge]
    # Image y grows downward: left of travel is (dy, -dx).
    lx, ly = -cc * dy, cc * dx
    return max(candidates, key=lambda point: point[0] * lx + point[1] * ly)


def slide(
    rows: Sequence[Sequence[Pixel]],
    start: Point,
    dp: int,
    cc: int,
    colour: Callable[[Pixel], Pixel],
) -> tuple[Point, int, int] | None:
    """Slide from a white codel until colour or a repeated white state."""
    width, height = len(rows[0]), len(rows)
    point = start
    seen: set[tuple[Point, int]] = set()
    while True:
        state = point, dp
        if state in seen:
            return None
        seen.add(state)
        dx, dy = DIRECTIONS[dp]
        target = point[0] + dx, point[1] + dy
        x, y = target
        if 0 <= x < width and 0 <= y < height:
            seen_colour = colour(rows[y][x])
            if seen_colour == WHITE:
                point = target
                continue
            if seen_colour != BLACK:
                return target, dp, cc
        cc *= -1
        dp = (dp + 1) % 4
