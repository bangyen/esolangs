"""Movement geometry shared by runs of one normalized Piet image."""

from functools import cached_property
from typing import NamedTuple

from esolangs.raster import Pixel, Rows
from esolangs.runtime.codels import (
    BLACK,
    COLOURS,
    DIRECTIONS,
    WHITE,
    Point,
    find_block,
    slide,
)

_STANDARD = frozenset({*COLOURS, WHITE, BLACK})


def colour(pixel: Pixel) -> Pixel:
    """Interpret every nonstandard colour as white."""
    return pixel if pixel in _STANDARD else WHITE


class _Block(NamedTuple):
    size: int
    edges: tuple[Point, ...]

    def exit(self, current: Point, dp: int, cc: int) -> Point:
        """Select the exit; a singleton leaves from its entry in all eight cases."""
        return self.edges[2 * dp + (cc == 1)] if self.edges else current


_SINGLE = _Block(1, ())


def _block(points: set[Point]) -> _Block:
    if len(points) == 1:
        return _SINGLE
    # At each extreme retain both ends, in left/right chooser order.
    west = min(x for x, _ in points)
    east = max(x for x, _ in points)
    north = min(y for _, y in points)
    south = max(y for _, y in points)
    left = [p for p in points if p[0] == west]
    right = [p for p in points if p[0] == east]
    top = [p for p in points if p[1] == north]
    bottom = [p for p in points if p[1] == south]
    return _Block(
        len(points),
        (
            min(right),
            max(right),
            max(bottom),
            min(bottom),
            max(left),
            min(left),
            min(top),
            max(top),
        ),
    )


type Move = tuple[Point | None, int, int, int, tuple[int, int] | None]


class Image:
    """Rows and their lazily discovered blocks, white paths and exact snapshot key."""

    def __init__(self, rows: Rows) -> None:
        self.rows = rows
        self.blocks: dict[Point, _Block] = {}
        self.slides: dict[tuple[Point, int], tuple[Point, int, int] | None] = {}

    @cached_property
    def key(self) -> tuple[int, int, bytes]:
        """Pack the original RGB channels, including nonstandard colours."""
        rows = self.rows
        return (
            len(rows[0]),
            len(rows),
            bytes(c for row in rows for pixel in row for c in pixel),
        )

    def _white(self, start: Point, dp: int, cc: int) -> Move:
        key = start, dp
        if key not in self.slides:
            # The chooser flips at each turn but never selects a white path.
            self.slides[key] = slide(self.rows, start, dp, 1, colour)
        outcome = self.slides[key]
        if outcome is None:
            return None, dp, cc, 0, None
        target, direction, sign = outcome
        return target, direction, cc * sign, 0, None

    def move(self, current: Point, dp: int, cc: int) -> Move:
        """Resolve an exit, retaining its final orientation even when trapped."""
        rows = self.rows
        source = colour(rows[current[1]][current[0]])
        if source == WHITE:
            return self._white(current, dp, cc)
        block = self.blocks.get(current)
        if block is None:
            points = find_block(rows, current, colour)
            block = _block(points)
            for point in points:
                self.blocks[point] = block
        for attempt in range(8):
            x, y = block.exit(current, dp, cc)
            dx, dy = DIRECTIONS[dp]
            x, y = x + dx, y + dy
            if 0 <= y < len(rows) and 0 <= x < len(rows[0]):
                target = colour(rows[y][x])
                if target == WHITE:
                    return self._white((x, y), dp, cc)
                if target != BLACK:
                    hue, light = COLOURS[source]
                    next_hue, next_light = COLOURS[target]
                    return (
                        (x, y),
                        dp,
                        cc,
                        block.size,
                        ((next_hue - hue) % 6, (next_light - light) % 3),
                    )
            if attempt % 2 == 0:
                cc = -cc
            else:
                dp = (dp + 1) % 4
        return None, dp, cc, 0, None
