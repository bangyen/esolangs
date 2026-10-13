"""Codel traversal shared by raster interpreters: blocks, exits and white slides."""

from __future__ import annotations

from collections.abc import Callable, Sequence

Pixel = tuple[int, int, int]
Point = tuple[int, int]

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

#: Piet colour cycles: each of the 18 command colours to its
#: ``(hue, lightness)`` position in the hue and lightness cycles.
COLOURS: dict[Pixel, tuple[int, int]] = {
    (255, 192, 192): (0, 0),
    (255, 255, 192): (1, 0),
    (192, 255, 192): (2, 0),
    (192, 255, 255): (3, 0),
    (192, 192, 255): (4, 0),
    (255, 192, 255): (5, 0),
    (255, 0, 0): (0, 1),
    (255, 255, 0): (1, 1),
    (0, 255, 0): (2, 1),
    (0, 255, 255): (3, 1),
    (0, 0, 255): (4, 1),
    (255, 0, 255): (5, 1),
    (192, 0, 0): (0, 2),
    (192, 192, 0): (1, 2),
    (0, 192, 0): (2, 2),
    (0, 192, 192): (3, 2),
    (0, 0, 192): (4, 2),
    (192, 0, 192): (5, 2),
}

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


def exit_step(
    rows: Sequence[Sequence[Pixel]],
    block: set[Point],
    dp: int,
    cc: int,
    colour: Callable[[Pixel], Pixel],
) -> tuple[Point, int, int, Pixel] | None:
    """Return the first non-black codel past ``block``, the dp and cc, and its colour.

    The eight attempts alternately toggle cc and rotate dp clockwise; None
    means every exit is black or off the image, with dp and cc back at the start.
    """
    width, height = len(rows[0]), len(rows)
    for attempt in range(8):
        x, y = leave(block, dp, cc)
        dx, dy = DIRECTIONS[dp]
        tx, ty = x + dx, y + dy
        if 0 <= tx < width and 0 <= ty < height:
            seen = colour(rows[ty][tx])
            if seen != BLACK:
                return (tx, ty), dp, cc, seen
        if attempt % 2 == 0:
            cc *= -1
        else:
            dp = (dp + 1) % 4
    return None


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
